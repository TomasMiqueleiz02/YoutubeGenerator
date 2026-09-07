import json
import logging
import socket
import threading
import time

logger = logging.getLogger(__name__)

# Where the worker leaves its sign of life, and how the API finds it.
HEARTBEAT_KEY = "worker:heartbeat"

# Beat often, expire slowly: a beat that has to cross a hosted Redis can be
# late without the worker being gone, and a page that flickers "offline"
# every time the network hiccups teaches people to ignore it.
BEAT_SECONDS = 15
BEAT_TTL = 60


def _client(app):
    import redis

    return redis.from_url(app.conf.broker_url)


def start_heartbeat(app) -> None:
    """
    Announce, every few seconds, that this machine is running the worker.

    The web app runs on Railway and the worker runs on a PC at home, so the
    page has no way of knowing whether anything is there to pick up a video.
    Without this it accepts an upload, shows "pending", and waits forever
    with no hint that the reason is a closed window. A key in Redis with an
    expiry is enough: present means alive, missing means nobody is home.
    """

    def beat():
        client = None
        while True:
            try:
                if client is None:
                    client = _client(app)
                client.setex(
                    HEARTBEAT_KEY,
                    BEAT_TTL,
                    json.dumps({"hostname": socket.gethostname(), "at": time.time()}),
                )
            except Exception:
                # A dropped connection is not worth a stack trace every 15
                # seconds. Throw the client away and rebuild it next beat.
                logger.debug("Heartbeat failed", exc_info=True)
                client = None
            time.sleep(BEAT_SECONDS)

    threading.Thread(target=beat, name="worker-heartbeat", daemon=True).start()


def clear_heartbeat(app) -> None:
    """Drop the key on a clean shutdown so the page updates immediately."""
    try:
        _client(app).delete(HEARTBEAT_KEY)
    except Exception:
        logger.debug("Could not clear heartbeat", exc_info=True)
