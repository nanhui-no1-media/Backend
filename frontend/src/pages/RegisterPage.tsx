import { useState, useEffect, useRef, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import AppShell from "../components/AppShell";
import PasswordInput from "../components/PasswordInput";
import { useLoginModal } from "../components/LoginModalProvider";
import { isTurnstileEnabled, renderTurnstile } from "../turnstile";

/**
 * 注册页（ADR-0006 注册↔验证分离）：只建登录身份（用户名 + 双密码 + Turnstile）。
 * 邮箱 / 真实姓名 / 身份证明都挪到登录后的「账号验证」面板（绑定邮箱 / 提交身份证明）。
 *
 * 后端为权威校验源；前端只做轻量预检（必填、密码一致、长度），其余错误由后端返回展示。
 */
export default function RegisterPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [turnstileToken, setTurnstileToken] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const navigate = useNavigate();
  const { openLogin } = useLoginModal();

  const turnstileRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);

  // 渲染 Turnstile 挂件（仅在配了 sitekey 时；本地留空跳过，后端 DEBUG 下不校验）。
  useEffect(() => {
    if (!isTurnstileEnabled() || !turnstileRef.current) return;
    widgetIdRef.current = renderTurnstile(
      turnstileRef.current,
      (token) => setTurnstileToken(token),
      () => setTurnstileToken("")
    );
    return () => {
      const id = widgetIdRef.current;
      if (id && window.turnstile) window.turnstile.remove(id);
    };
  }, []);

  const resetTurnstile = () => {
    setTurnstileToken("");
    if (widgetIdRef.current && window.turnstile) window.turnstile.reset(widgetIdRef.current);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");

    if (!username.trim()) {
      setError("请填写用户名。");
      return;
    }
    if (password !== password2) {
      setError("两次输入的密码不一致。");
      return;
    }
    if (password.length < 8) {
      setError("密码至少 8 位。");
      return;
    }
    if (isTurnstileEnabled() && !turnstileToken) {
      setError("请先完成人机校验。");
      return;
    }

    setLoading(true);
    const fd = new FormData();
    fd.append("username", username.trim());
    fd.append("password", password);
    fd.append("password2", password2);
    if (turnstileToken) fd.append("turnstile_token", turnstileToken);

    try {
      await api.register(fd);
      setDone(true);
    } catch (err: any) {
      setError(err?.message || "注册失败，请稍后重试。");
      resetTurnstile();
    } finally {
      setLoading(false);
    }
  };

  const goLogin = () => {
    navigate("/");
    openLogin();
  };

  return (
    <AppShell>
      <div className="page">
        <div className="container" style={{ maxWidth: 460 }}>
          <div style={{ paddingTop: "var(--s-16)", paddingBottom: "var(--s-16)" }}>
            <div className="card card-pad">
              {done ? (
                <>
                  <h2 style={{ marginBottom: "var(--s-4)" }}>注册成功</h2>
                  <p className="muted" style={{ marginBottom: "var(--s-5)" }}>
                    你现在可以用<strong>{username}</strong>和密码登录。登录后在个人中心「账号验证」
                    完成验证（绑定邮箱或提交身份证明），即可解锁发帖、发消息、建申报等全部功能。
                  </p>
                  <button className="btn btn-primary btn-block" type="button" onClick={goLogin}>
                    去登录
                  </button>
                </>
              ) : (
                <>
                  <h2 style={{ marginBottom: "var(--s-5)" }}>注册账号</h2>
                  <form
                    onSubmit={handleSubmit}
                    style={{ display: "flex", flexDirection: "column", gap: "var(--s-4)" }}
                  >
                    {error && (
                      <div className="alert alert-danger">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 8v4M12 16h.01" /></svg>
                        <span>{error}</span>
                      </div>
                    )}
                    <div className="field">
                      <label className="label">用户名</label>
                      <input
                        className="input"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        placeholder="登录用用户名"
                        autoComplete="username"
                        required
                      />
                    </div>
                    <div className="field">
                      <label className="label">密码</label>
                      <PasswordInput
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="至少 8 位"
                        autoComplete="new-password"
                      />
                    </div>
                    <div className="field">
                      <label className="label">确认密码</label>
                      <PasswordInput
                        value={password2}
                        onChange={(e) => setPassword2(e.target.value)}
                        placeholder="再输一次"
                        autoComplete="new-password"
                      />
                    </div>
                    <div ref={turnstileRef} />
                    <button className="btn btn-primary btn-block" type="submit" disabled={loading}>
                      {loading ? "提交中…" : "注册"}
                    </button>
                  </form>
                  <div className="hint center" style={{ marginTop: "var(--s-4)" }}>
                    已有账号？{" "}
                    <a href="#" onClick={(e) => { e.preventDefault(); goLogin(); }}>
                      去登录
                    </a>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
