import { useEffect, useState } from "react";
import { useStore } from "./store/useStore";
import { apiClient } from "./services/api";
import Login from "./pages/Login";
import Dashboard from "./components/Dashboard";

export default function App() {
  const { user, setUser, token } = useStore();
  const [checking, setChecking] = useState(true);

  const loadUser = async () => {
    try {
      setUser(await apiClient.getCurrentUser());
    } catch {
      setUser(null);
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    if (token) {
      loadUser();
    } else {
      setChecking(false);
    }
  }, [token]);

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-sm" style={{ color: "var(--text-dim)" }}>
          Cargando...
        </div>
      </div>
    );
  }

  return user ? <Dashboard /> : <Login onLoginSuccess={loadUser} />;
}
