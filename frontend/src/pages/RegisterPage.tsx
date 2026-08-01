import { useState, useEffect, useRef, type FormEvent, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import AppShell from "../components/AppShell";
import PasswordInput from "../components/PasswordInput";
import { useLoginModal } from "../components/LoginModalProvider";
import { isTurnstileEnabled, renderTurnstile } from "../turnstile";

const IDENTITY_OPTIONS = [
  { value: "", label: "请选择身份" },
  { value: "student", label: "在校生" },
  { value: "external", label: "外校生" },
  { value: "graduate", label: "毕业生" },
];

const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 5 * 1024 * 1024;

/**
 * 自助注册页（#28）。访客填用户名 / 真实姓名 / 身份 / 邮箱 / 密码 + 上传学生证照片，
 * 过 Turnstile（配了 sitekey 才渲染）后提交。成功即建号（未验证），跳「验证邮件已发送」态。
 *
 * 后端为权威校验源；前端只做轻量预检（必填、密码一致、文件数/大小），其余错误由后端返回展示。
 */
export default function RegisterPage() {
  const [username, setUsername] = useState("");
  const [realName, setRealName] = useState("");
  const [identity, setIdentity] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [files, setFiles] = useState<File[]>([]);
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

  const onFilesChange = (e: ChangeEvent<HTMLInputElement>) => {
    setError("");
    const picked = Array.from(e.target.files ?? []);
    // 前端预检：类型 / 大小（后端仍会复校）
    const badType = picked.find((f) => !ALLOWED_TYPES.includes(f.type));
    if (badType) {
      setError(`「${badType.name}」格式不支持（仅 JPG / PNG / WebP）`);
      return;
    }
    const oversize = picked.find((f) => f.size > MAX_BYTES);
    if (oversize) {
      setError(`「${oversize.name}」超过 5MB 上限`);
      return;
    }
    if (picked.length > 3) {
      setError("身份证明最多 3 张");
      return;
    }
    setFiles(picked);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");

    if (!username.trim() || !realName.trim() || !email.trim()) {
      setError("请填写用户名、真实姓名、邮箱。");
      return;
    }
    if (!identity) {
      setError("请选择身份。");
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
    if (files.length < 1) {
      setError("请至少上传 1 张身份证明照片。");
      return;
    }
    if (isTurnstileEnabled() && !turnstileToken) {
      setError("请先完成人机校验。");
      return;
    }

    setLoading(true);
    const fd = new FormData();
    fd.append("username", username.trim());
    fd.append("real_name", realName.trim());
    fd.append("identity", identity);
    fd.append("email", email.trim());
    fd.append("password", password);
    fd.append("password2", password2);
    if (turnstileToken) fd.append("turnstile_token", turnstileToken);
    files.forEach((f) => fd.append("proof_files", f));

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

  const goHome = () => {
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
                  <h2 style={{ marginBottom: "var(--s-4)" }}>验证邮件已发送</h2>
                  <p className="muted" style={{ marginBottom: "var(--s-5)" }}>
                    我们向 <strong>{email}</strong> 发了一封验证邮件，点击邮件里的链接完成邮箱验证后即可首次登录。
                    没收到？检查垃圾邮件箱，或稍后用登录页的「重发验证邮件」补发。
                  </p>
                  <button className="btn btn-primary btn-block" type="button" onClick={goHome}>
                    返回登录
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
                      <label className="label">真实姓名（不公开）</label>
                      <input
                        className="input"
                        value={realName}
                        onChange={(e) => setRealName(e.target.value)}
                        placeholder="用于身份核验，仅本人与审核员可见"
                        required
                      />
                    </div>
                    <div className="field">
                      <label className="label">身份</label>
                      <select
                        className="input"
                        value={identity}
                        onChange={(e) => setIdentity(e.target.value)}
                        required
                      >
                        {IDENTITY_OPTIONS.map((o) => (
                          <option key={o.value} value={o.value} disabled={o.value === ""}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="field">
                      <label className="label">邮箱</label>
                      <input
                        className="input"
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="用于验证与找回密码"
                        autoComplete="email"
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
                    <div className="field">
                      <label className="label">学生证照片（1~3 张，JPG/PNG/WebP，单张 ≤5MB）</label>
                      <input
                        className="input"
                        type="file"
                        accept={ALLOWED_TYPES.join(",")}
                        multiple
                        onChange={onFilesChange}
                      />
                      {files.length > 0 && (
                        <div className="hint">
                          已选 {files.length} 张：{files.map((f) => f.name).join("、")}
                        </div>
                      )}
                    </div>
                    <div ref={turnstileRef} />
                    <button className="btn btn-primary btn-block" type="submit" disabled={loading}>
                      {loading ? "提交中…" : "注册"}
                    </button>
                  </form>
                  <div className="hint center" style={{ marginTop: "var(--s-4)" }}>
                    已有账号？{" "}
                    <a href="#" onClick={(e) => { e.preventDefault(); goHome(); }}>
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
