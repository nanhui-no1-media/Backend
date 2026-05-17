import { useState, FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import "./LoginPage.css";

type Tab = "username" | "email" | "phone";

export default function LoginPage() {
  const [tab, setTab] = useState<Tab>("username");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (tab === "username") {
        await api.login(username, password);
      } else {
        await api.loginWithEmail(email, password);
      }
      navigate("/");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <h2>Login</h2>
        <div className="tabs">
          <button className={tab === "username" ? "active" : ""} onClick={() => setTab("username")}>
            Username
          </button>
          <button className={tab === "email" ? "active" : ""} onClick={() => setTab("email")}>
            Email
          </button>
          <button disabled title="Coming soon">Phone</button>
        </div>

        {tab === "phone" ? (
          <div className="coming-soon">Phone login coming soon</div>
        ) : (
          <form onSubmit={handleSubmit}>
            {error && <div className="error-msg">{error}</div>}
            {tab === "username" && (
              <div className="form-group">
                <label>Username</label>
                <input value={username} onChange={(e) => setUsername(e.target.value)} required />
              </div>
            )}
            {tab === "email" && (
              <div className="form-group">
                <label>Email</label>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
              </div>
            )}
            <div className="form-group">
              <label>Password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <button className="submit-btn" type="submit" disabled={loading}>
              {loading ? "Logging in..." : "Login"}
            </button>
          </form>
        )}

        <div className="links">
          <Link to="/forgot-password">Forgot password?</Link>
          <span style={{ margin: "0 8px" }}>|</span>
          <Link to="/register">Register</Link>
        </div>
      </div>
    </div>
  );
}
