import { useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { api } from "../api/client";

export default function HomePage() {
  const [user, setUser] = useState<any>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.me()
      .then((data) => setUser(data))
      .catch(() => navigate("/login"));
  }, [navigate]);

  const handleLogout = async () => {
    try {
      await api.logout();
    } finally {
      navigate("/login");
    }
  };

  return (
    <div style={{ padding: 32, fontFamily: "sans-serif", maxWidth: 600, margin: "0 auto" }}>
      <h1>Home</h1>
      {user && <p>Welcome, {user.username || user.email || "user"}!</p>}
      <button
        onClick={handleLogout}
        style={{
          padding: "8px 16px",
          background: "#d32f2f",
          color: "white",
          border: "none",
          borderRadius: 4,
          cursor: "pointer",
        }}
      >
        Logout
      </button>
    </div>
  );
}
