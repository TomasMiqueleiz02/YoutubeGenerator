import { parseRanges, formatTimecode } from "../lib/timeRanges";

interface Props {
  value: string;
  onChange: (value: string) => void;
  /** Length of the video, when known, to catch spans past the end */
  duration?: number | null;
  disabled?: boolean;
}

/**
 * Where someone types the parts of a video worth clipping.
 *
 * Marking spans is the difference between a model reading an hour of footage
 * and reading the five minutes that actually had something in them, so the
 * field shows what it understood as you type: getting "10:30-14:00" silently
 * misread would waste a whole run.
 */
export default function RangeField({ value, onChange, duration, disabled }: Props) {
  const parsed = parseRanges(value, duration);

  return (
    <div>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="10:30-14:00, 55:00-58:30"
        className="input w-full"
        disabled={disabled}
        spellCheck={false}
      />

      <p className="mt-1.5 text-xs" style={{ color: "var(--text-faint)" }}>
        {parsed.error ? (
          <span style={{ color: "var(--bad)" }}>{parsed.error}</span>
        ) : parsed.ranges.length > 0 ? (
          <span style={{ color: "var(--good)" }}>
            {parsed.ranges.length === 1
              ? "1 tramo"
              : `${parsed.ranges.length} tramos`}{" "}
            · {formatTimecode(parsed.totalSeconds)} de video a analizar
          </span>
        ) : (
          "Minutos y segundos, separados por coma. Un número solo son minutos."
        )}
      </p>
    </div>
  );
}
