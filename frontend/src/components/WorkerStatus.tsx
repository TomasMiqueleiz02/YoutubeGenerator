import { useEffect, useState } from "react";
import { apiClient } from "../services/api";
import { WorkerStatus as Status } from "../types";

/**
 * Shows whether the machine that processes videos is running.
 *
 * Uploads are handled by a worker on a PC at home, not by the server this
 * page came from, because YouTube refuses downloads from datacenters. When
 * that PC is off, an upload queues and nothing happens, with no way to tell
 * that from a slow job. This says which of the two it is.
 */
export default function WorkerStatus() {
  const [status, setStatus] = useState<Status | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const result = await apiClient.getWorkerStatus();
        if (!cancelled) setStatus(result);
      } catch {
        if (!cancelled) setStatus(null);
      }
    };

    check();
    const timer = window.setInterval(check, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  // Nothing known yet, or the API could not reach the queue: saying "offline"
  // here would be a guess, and a wrong one sends people to restart something
  // that is already running.
  if (!status || status.online === null) return null;

  const online = status.online;

  return (
    <div className="relative">
      <button
        onClick={() => setExpanded((open) => !open)}
        className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs transition-colors"
        style={{
          background: online ? "transparent" : "rgba(248,113,113,0.12)",
          color: online ? "var(--text-dim)" : "var(--bad)",
        }}
        title={online ? "El procesador está corriendo" : "El procesador está apagado"}
      >
        <span
          className="h-2 w-2 rounded-full"
          style={{
            background: online ? "var(--good)" : "var(--bad)",
            boxShadow: online ? "0 0 8px var(--good)" : "none",
          }}
        />
        <span className="hidden sm:block">
          {online ? "Procesador activo" : "Procesador apagado"}
        </span>
      </button>

      {expanded && (
        <div
          className="card absolute right-0 top-full z-30 mt-2 w-72 p-4 text-xs leading-relaxed"
          style={{ color: "var(--text-dim)" }}
        >
          {online ? (
            <>
              <p style={{ color: "var(--text)" }} className="mb-1.5 font-medium">
                Todo listo
              </p>
              <p>
                Los videos que subas se descargan y se cortan en{" "}
                <span style={{ color: "var(--text)" }}>
                  {status.hostname || "tu PC"}
                </span>
                .
              </p>
            </>
          ) : (
            <>
              <p style={{ color: "var(--bad)" }} className="mb-1.5 font-medium">
                Tu PC no está procesando
              </p>
              <p className="mb-2">
                Podés subir videos igual: quedan en cola y arrancan solos
                cuando la PC vuelva.
              </p>
              <p>
                Para arrancarlo ahora, abrí{" "}
                <code
                  className="rounded px-1 py-0.5"
                  style={{ background: "var(--bg)", color: "var(--text)" }}
                >
                  start-worker.bat
                </code>
                .
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
