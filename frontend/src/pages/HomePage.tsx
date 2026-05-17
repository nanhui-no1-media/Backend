import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import "./HomePage.css";

interface User {
  id: number;
  username: string;
  email: string;
}

export default function HomePage() {
  const [user, setUser] = useState<User | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.me().then((data) => setUser(data.user)).catch(() => navigate("/login"));
  }, [navigate]);

  const handleLogout = async () => {
    try {
      await api.logout();
    } finally {
      navigate("/login");
    }
  };

  return (
    <div className="home-container">
      <div className="home-header">
        <h1>Dashboard</h1>
        <button className="logout-btn" onClick={handleLogout}>Logout</button>
      </div>
      <div className="home-content">
        <p>Welcome, {user?.username}!</p>
        <p>Email: {user?.email}</p>
      </div>
    </div>
  );
}
