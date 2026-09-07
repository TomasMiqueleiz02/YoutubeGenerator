"""
Spans of a video worth clipping, marked by hand.

An hour of gaming footage is mostly setup, and a model reading the whole
transcript spends its budget on the boring parts as readily as on the good
ones. Someone who watched the video already knows where the payoff is, and
saying so is both cheaper and more accurate than any amount of prompt work.

Marking a span also cuts the wait: the frame pass is the slowest stage by far
and it only has to decode what was asked for.

Ranges are seconds from the start of the video, stored as [start, end] pairs.
An empty list means the whole video, which is what every video had before
this existed.
"""

from typing import Iterable, List, Optional, Sequence, Tuple

Range = Tuple[float, float]

# Shorter than this there is nothing to find: a clip has a floor of 12
# seconds, and a span needs room around the moment to breathe.
MIN_SPAN_SECONDS = 15.0


def normalize(raw: Optional[Iterable], duration: Optional[float] = None) -> List[Range]:
    """
    Turn whatever arrived into sorted, merged, in-bounds spans.

    Accepts [[start, end], ...] or [{"start": .., "end": ..}, ...], which is
    the difference between what the API receives and what ends up in the
    database column. Anything unusable is dropped rather than raising: a
    malformed range should fall back to analyzing everything, not fail the
    upload.
    """
    if not raw:
        return []

    spans: List[Range] = []
    for item in raw:
        try:
            if isinstance(item, dict):
                start, end = float(item["start"]), float(item["end"])
            else:
                start, end = float(item[0]), float(item[1])
        except (TypeError, ValueError, KeyError, IndexError):
            continue

        if end < start:
            start, end = end, start

        start = max(0.0, start)
        if duration:
            end = min(end, float(duration))
            if start >= duration:
                continue

        if end - start < MIN_SPAN_SECONDS:
            continue

        spans.append((start, end))

    if not spans:
        return []

    # Overlapping spans would make the analyzer decode the same frames twice
    spans.sort()
    merged = [spans[0]]
    for start, end in spans[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    return merged


def total_seconds(ranges: Sequence[Range]) -> float:
    return sum(end - start for start, end in ranges)


def contains(ranges: Sequence[Range], start: float, end: float) -> bool:
    """True when a moment fits inside one span. No ranges means no limits."""
    if not ranges:
        return True
    return any(start >= r_start and end <= r_end for r_start, r_end in ranges)


def covers(ranges: Sequence[Range], moment: float) -> bool:
    """True when a single point in time falls inside a span."""
    if not ranges:
        return True
    return any(start <= moment <= end for start, end in ranges)


def overlaps(ranges: Sequence[Range], start: float, end: float) -> bool:
    """True when a moment touches any span at all."""
    if not ranges:
        return True
    return any(start < r_end and end > r_start for r_start, r_end in ranges)


def mask(scores, ranges: Sequence[Range]):
    """
    Zero out the seconds outside the marked spans.

    The score timelines are indexed by second of the source video, and every
    stage downstream relies on that. Rather than shortening them and having
    to translate indices everywhere, keep them full length and flatten what
    was not asked for, so a fallback that hunts for peaks cannot find one in
    a part of the video nobody wants.
    """
    import numpy as np

    scores = np.asarray(scores, dtype=float)
    if not ranges or scores.size == 0:
        return scores

    keep = np.zeros(scores.shape, dtype=bool)
    for start, end in ranges:
        keep[int(start) : min(int(end) + 1, scores.size)] = True

    return np.where(keep, scores, 0.0)


def as_pairs(ranges: Sequence[Range]) -> List[List[float]]:
    """The shape stored in the database and sent over the API."""
    return [[float(start), float(end)] for start, end in ranges]


def to_clip_timestamps(ranges: Sequence[Range]) -> List[float]:
    """Flat [start, end, start, end, ...], which is what Whisper expects."""
    flat: List[float] = []
    for start, end in ranges:
        flat.extend([float(start), float(end)])
    return flat


def describe(ranges: Sequence[Range]) -> str:
    """Human-readable spans for the log, e.g. '10:30-14:00, 55:00-58:30'."""
    if not ranges:
        return "whole video"

    def clock(value: float) -> str:
        return "%d:%02d" % (int(value // 60), int(value % 60))

    return ", ".join("%s-%s" % (clock(s), clock(e)) for s, e in ranges)
