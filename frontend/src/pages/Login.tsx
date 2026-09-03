import { useState } from "react";
import { useStore } from "../store/useStore";
import { apiClient } from "../services/api";

interface Props {
  onLoginSuccess: () => void;
}

export default function Login({ onLoginSuccess }: Props) {
  const { setUser, setToken } = useStore();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === "register") {
        await apiClient.register(email, username, password);
      }
      const response = await apiClient.login(email, password);
      setToken(response.access_token);
      setUser(await apiClient.getCurrentUser());
      onLoginSuccess();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(
        typeof detail === "string"
          ? detail
          : mode === "login"
          ? "Email o contraseña incorrectos"
          : "No se pudo crear la cuenta"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div
            className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl text-2xl"
            style={{ background: "var(--accent-soft)" }}
          >
            ✂️
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Clip Generator</h1>
          <p className="mt-2 text-sm" style={{ color: "var(--text-dim)" }}>
            Convertí videos largos en clips para redes
          </p>
        </div>

        <div className="card p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                className="mb-1.5 block text-xs font-medium"
                style={{ color: "var(--text-dim)" }}
              >
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input"
                placeholder="vos@ejemplo.com"
                autoComplete="email"
                required
              />
            </div>

            {mode === "register" && (
              <div>
                <label
                  className="mb-1.5 block text-xs font-medium"
                  style={{ color: "var(--text-dim)" }}
                >
                  Usuario
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="input"
                  placeholder="tomas"
                  required
                />
              </div>
            )}

            <div>
              <label
                className="mb-1.5 block text-xs font-medium"
                style={{ color: "var(--text-dim)" }}
              >
                Contraseña
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                placeholder="••••••••"
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
                required
              />
            </div>

            {error && (
              <div
                className="rounded-lg px-3 py-2.5 text-xs"
                style={{
                  background: "rgba(248,113,113,0.1)",
                  color: "var(--bad)",
                }}
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary w-full"
            >
              {loading
                ? "Un momento..."
                : mode === "login"
                ? "Entrar"
                : "Crear cuenta"}
            </button>
          </form>
        </div>

        <p className="mt-5 text-center text-sm" style={{ color: "var(--text-dim)" }}>
          {mode === "login" ? "¿No tenés cuenta?" : "¿Ya tenés cuenta?"}{" "}
          <button
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError(null);
            }}
            className="font-semibold"
            style={{ color: "var(--accent)" }}
          >
            {mode === "login" ? "Registrate" : "Entrá"}
          </button>
        </p>
      </div>
    </div>
  );
}
