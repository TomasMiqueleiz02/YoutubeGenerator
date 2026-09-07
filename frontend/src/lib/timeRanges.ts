/**
 * Parsing for the spans of a video someone marks as worth clipping.
 *
 * People write time the way they read it off a player — "10:30-14:00" — so
 * that is what the field accepts. A bare number means minutes, because the
 * whole point of the field is picking out minutes of a long video.
 */

export interface ParsedRanges {
  ranges: number[][];
  totalSeconds: number;
  error: string | null;
}

/** Seconds from "1:02:30", "10:30" or "10" (minutes). */
function parseTimecode(raw: string): number | null {
  const text = raw.trim();
  if (!text) return null;

  const parts = text.split(":");
  if (parts.some((p) => !/^\d+$/.test(p.trim()))) return null;

  const numbers = parts.map((p) => parseInt(p, 10));

  if (numbers.length === 1) return numbers[0] * 60; // bare number: minutes
  if (numbers.length === 2) return numbers[0] * 60 + numbers[1];
  if (numbers.length === 3) return numbers[0] * 3600 + numbers[1] * 60 + numbers[2];
  return null;
}

export function formatTimecode(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
  return `${h > 0 ? `${h}:` : ""}${mm}:${String(s).padStart(2, "0")}`;
}

/** Shortest span the backend will accept; anything less is dropped there. */
export const MIN_SPAN_SECONDS = 15;

export function parseRanges(text: string, duration?: number | null): ParsedRanges {
  const empty: ParsedRanges = { ranges: [], totalSeconds: 0, error: null };
  if (!text.trim()) return empty;

  const ranges: number[][] = [];

  for (const chunk of text.split(/[,\n]/)) {
    const piece = chunk.trim();
    if (!piece) continue;

    const halves = piece.split(/\s*[-–]\s*/);
    if (halves.length !== 2) {
      return { ...empty, error: `"${piece}" no es un tramo. Se escribe 10:30-14:00.` };
    }

    const start = parseTimecode(halves[0]);
    const end = parseTimecode(halves[1]);

    if (start === null || end === null) {
      return { ...empty, error: `No entiendo los tiempos de "${piece}".` };
    }
    if (end <= start) {
      return { ...empty, error: `En "${piece}" el final va antes que el inicio.` };
    }
    if (end - start < MIN_SPAN_SECONDS) {
      return {
        ...empty,
        error: `"${piece}" dura menos de ${MIN_SPAN_SECONDS} segundos.`,
      };
    }
    if (duration && start >= duration) {
      return {
        ...empty,
        error: `"${piece}" arranca después de que el video termina (${formatTimecode(
          duration
        )}).`,
      };
    }

    ranges.push([start, duration ? Math.min(end, duration) : end]);
  }

  ranges.sort((a, b) => a[0] - b[0]);

  // Merged the same way the backend does, so the summary shown here matches
  // the amount of video that actually gets analyzed.
  const merged: number[][] = [];
  for (const [start, end] of ranges) {
    const last = merged[merged.length - 1];
    if (last && start <= last[1]) {
      last[1] = Math.max(last[1], end);
    } else {
      merged.push([start, end]);
    }
  }

  return {
    ranges: merged,
    totalSeconds: merged.reduce((sum, [start, end]) => sum + (end - start), 0),
    error: null,
  };
}

export function formatRanges(ranges?: number[][] | null): string {
  if (!ranges || ranges.length === 0) return "";
  return ranges
    .map(([start, end]) => `${formatTimecode(start)}-${formatTimecode(end)}`)
    .join(", ");
}
