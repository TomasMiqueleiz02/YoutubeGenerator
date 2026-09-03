import { useEffect, useState } from "react";
import { useStore } from "./store/useStore";
import { apiClient } from "./services/api";
import Login from "./pages/Login";
import Dashboard from "./components/Dashboard";

export default function App() {
  const { user, setUser, token } = useStore();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token) {
      loadUser();
    } else {
      setLoading(false);
    }
  }, [token]);

  const loadUser = async () => {
    try {
      const currentUser = await apiClient.getCurrentUser();
      setUser(currentUser);
    } catch (err) {
      console.error("Failed to load user", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 to-gray-800 flex items-center justify-center text-white">
        <div>Loading...</div>
      </div>
    );
  }

  if (!user) {
    return <Login onLoginSuccess={loadUser} />;
  }

  return <Dashboard />;
}
