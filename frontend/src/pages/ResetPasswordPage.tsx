import { useState, FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import "./ResetPasswordPage.css";

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const uid = searchParams.get("uid") || "";
  const token = searchParams.get("token") || "";
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  if (!uid || !token) {
    return (
      <div className="reset-container">
        <div className="reset-card">
          <h2>链接无效</h2>
          <p style={{ textAlign: "center" }}>该密码重置链接无效。</p>
          <div className="links">
            <Link to="/login">返回登录</Link>
          </div>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.passwordResetConfirm(uid, token, newPassword);
      navigate("/login");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="reset-container">
      <div className="reset-card">
        <h2>重置密码</h2>
        <form onSubmit={handleSubmit}>
          {error && <div className="error-msg">{error}</div>}
          <div className="form-group">
            <label>新密码</label>
            <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required />
          </div>
          <button className="submit-btn" type="submit" disabled={loading}>
            {loading ? "重置中..." : "重置密码"}
          </button>
        </form>
      </div>
    </div>
  );
}
