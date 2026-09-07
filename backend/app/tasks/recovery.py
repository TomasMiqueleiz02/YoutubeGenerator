import json
import logging
from typing import Optional, Set, Tuple

logger = logging.getLogger(__name__)


def _busy_task_ids(app, timeout: float = 15.0) -> Optional[Set[str]]:
    """
    Task ids the live workers are holding: running, prefetched or scheduled.

    Reserved tasks matter as much as running ones. A worker claims a message
    before it starts executing it, so a sweep that only looked at active()
    saw a freshly claimed task as abandoned and handed out a second copy of
    it -- which is exactly what happened the first time this ran.

    Returns None when nobody answers in time. That is not the same as an
    empty set: "no worker is busy" allows restoring everything, "I could not
    ask" does not.

    The timeout is generous because the broker is a hosted Redis rather than
    one on this machine: a round trip through it measured seven to ten
    seconds, and a short timeout reads as "no workers" when in fact one is
    sitting right there.
    """
    inspector = app.control.inspect(timeout=timeout)

    busy: Set[str] = set()
    answered = False

    for probe in (inspector.active, inspector.reserved, inspector.scheduled):
        try:
            replies = probe()
        except Exception:
            logger.warning("Could not ask the workers what they are holding")
            continue

        if replies is None:
            continue

        answered = True
        for tasks in replies.values():
            for task in tasks or []:
                # scheduled() wraps the message one level deeper than the rest
                request = task.get("request", task)
                if request.get("id"):
                    busy.add(request["id"])

    return busy if answered else None


def _describe(raw: bytes) -> Tuple[Optional[str], str]:
    """Pull (task id, task name) out of a stored unacknowledged message."""
    try:
        message = json.loads(raw)[0]
        headers = message.get("headers") or {}
        return headers.get("id"), headers.get("task") or "unknown"
    except Exception:
        return None, "unparseable"


def restore_orphaned_tasks(app, claimed_before: Optional[float] = None) -> int:
    """
    Put back on the queue the tasks a dead worker never finished.

    With task_acks_late the broker holds a message unacknowledged until the
    task returns, so a worker that is killed mid-job leaves the work in Redis
    instead of losing it. Kombu is supposed to hand those messages back once
    visibility_timeout passes, but it schedules that sweep from the async
    event loop, and Celery refuses to run that loop on Windows:

        # celery/worker/worker.py
        def should_use_eventloop(self):
            return (detect_environment() == 'default' and
                    self._conninfo.transport.implements.asynchronous and
                    not self.app.IS_WINDOWS)

    This worker runs on Windows, so the sweep never ran and nothing came back:
    a download orphaned on September 3rd was still sitting unacknowledged four
    days later, with the video frozen at 5% the whole time.

    Sweeping at worker startup covers the failure that actually happens here,
    which is that the worker dies and someone starts it again. At that instant
    this process holds nothing in flight, so anything still unacknowledged is
    orphaned, apart from whatever another worker is running right now.

    `claimed_before` is the moment this worker came up. A message claimed
    after that cannot be an orphan of a dead worker -- it belongs to this
    process or to a live peer -- so it is left alone no matter what the
    workers report.
    """
    restored = 0
    busy = _busy_task_ids(app)

    try:
        with app.connection_for_read() as connection:
            channel = connection.default_channel
            qos, client = channel.qos, channel.client

            pending = client.hgetall(qos.unacked_key)
            if not pending:
                return 0

            # Without an answer from the workers, fall back to kombu's own
            # rule and only touch messages old enough that no sane task could
            # still be running them.
            cutoff = claimed_before
            if busy is None:
                import time

                aged = time.time() - qos.visibility_timeout
                cutoff = aged if cutoff is None else min(cutoff, aged)
                logger.info(
                    "No worker reported what it is holding; only restoring "
                    "messages idle for more than %ss",
                    qos.visibility_timeout,
                )

            for raw_tag, raw_message in pending.items():
                tag = raw_tag.decode() if isinstance(raw_tag, bytes) else raw_tag
                task_id, task_name = _describe(raw_message)

                if busy is not None and task_id in busy:
                    continue

                if cutoff is not None:
                    claimed = client.zscore(qos.unacked_index_key, tag)
                    if claimed is not None and claimed > cutoff:
                        continue

                qos.restore_by_tag(tag, client)
                restored += 1
                logger.warning("Requeued orphaned task %s [%s]", task_name, task_id)

    except Exception:
        # Recovery is a best effort. A worker that cannot sweep should still
        # start and process new work.
        logger.exception("Could not restore orphaned tasks")

    if restored:
        logger.warning("Requeued %d orphaned task(s) left by a dead worker", restored)

    return restored
