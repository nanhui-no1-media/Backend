import { useState, FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import "./ForgotPasswordPage.css";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);
    try {
      await api.passwordReset(email);
      setSuccess("如果该邮箱已注册，重置链接已发送，请查看控制台输出。");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="forgot-container">
      <div className="forgot-card">
        <h2>忘记密码</h2>
        <form onSubmit={handleSubmit}>
          {error && <div className="error-msg">{error}</div>}
          {success && <div className="success-msg">{success}</div>}
          <div className="form-group">
            <label>邮箱</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <button className="submit-btn" type="submit" disabled={loading}>
            {loading ? "发送中..." : "发送重置链接"}
          </button>
        </form>
        <div className="links">
          <Link to="/login">返回登录</Link>
        </div>
      </div>
    </div>
  );
}
