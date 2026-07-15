import { useState, useEffect, useRef, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import AppShell from "../components/AppShell";
import { useLoginModal } from "../components/LoginModalProvider";
import "../styles/form.css";

interface ProfileData {
  user: { id: number; username: string; email: string };
  profile: {
    avatar: string | null;
    nickname: string;
    birthday: string | null;
    gender: string;
    bio: string;
  };
}

const GENDER_OPTIONS = [
  { value: "", label: "未设置" },
  { value: "M", label: "男" },
  { value: "F", label: "女" },
  { value: "O", label: "其他" },
];
const genderLabel = (v: string) => GENDER_OPTIONS.find((o) => o.value === v)?.label || "未设置";

export default function ProfilePage() {
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const navigate = useNavigate();
  const { openLogin } = useLoginModal();

  // Form state
  const [nickname, setNickname] = useState("");
  const [birthday, setBirthday] = useState("");
  const [gender, setGender] = useState("");
  const [bio, setBio] = useState("");

  // Password change state
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);

  useEffect(() => {
    api
      .getProfile()
      .then((data) => {
        setProfile(data);
        setNickname(data.profile.nickname);
        setBirthday(data.profile.birthday || "");
        setGender(data.profile.gender);
        setBio(data.profile.bio);
      })
      .catch(() => openLogin())
      .finally(() => setLoading(false));
  }, [openLogin]);

  const handleAvatarClick = () => fileInputRef.current?.click();

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      setError("头像文件不能超过 2MB");
      return;
    }
    const reader = new FileReader();
    reader.onload = (ev) => setAvatarPreview(ev.target?.result as string);
    reader.readAsDataURL(file);
  };

  const handleProfileSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const formData = new FormData();
      if (avatarPreview) {
        const file = fileInputRef.current?.files?.[0];
        if (file) formData.append("avatar", file);
      }
      formData.append("nickname", nickname);
      formData.append("birthday", birthday);
      formData.append("gender", gender);
      formData.append("bio", bio);

      const data = await api.updateProfile(formData);
      setProfile(data);
      setAvatarPreview(null);
      setEditing(false);
      setSuccess("资料已更新");
      setTimeout(() => setSuccess(""), 3000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handlePasswordSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setPasswordError("");
    if (newPassword !== confirmPassword) {
      setPasswordError("两次输入的密码不一致");
      return;
    }
    if (newPassword.length < 8) {
      setPasswordError("新密码至少 8 个字符");
      return;
    }
    setPasswordSaving(true);
    try {
      await api.changePassword(oldPassword, newPassword);
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setShowPasswordForm(false);
      setSuccess("密码已修改");
      setTimeout(() => setSuccess(""), 3000);
    } catch (err: any) {
      setPasswordError(err.message);
    } finally {
      setPasswordSaving(false);
    }
  };

  const handleCancel = () => {
    if (!profile) return;
    setNickname(profile.profile.nickname);
    setBirthday(profile.profile.birthday || "");
    setGender(profile.profile.gender);
    setBio(profile.profile.bio);
    setAvatarPreview(null);
    setEditing(false);
    setError("");
  };

  if (loading) {
    return (
      <AppShell>
        <div className="container" style={{ paddingTop: "var(--s-12)" }}>
          <p className="muted">加载中…</p>
        </div>
      </AppShell>
    );
  }

  if (!profile) return null;

  const avatarSrc = avatarPreview || profile.profile.avatar;
  const initial = profile.user.username.charAt(0).toUpperCase();

  return (
    <AppShell>
      <div className="page-head">
        <div className="container">
          <nav className="breadcrumb">
            <a href="#" onClick={(e) => { e.preventDefault(); navigate("/"); }}>主页</a>
            <span className="sep">/</span>
            <span>个人中心</span>
          </nav>
          <div className="page-head-row">
            <h1>个人资料</h1>
            {!editing ? (
              <button className="btn btn-primary" onClick={() => setEditing(true)}>编辑</button>
            ) : (
              <button className="btn btn-ghost" onClick={handleCancel}>取消</button>
            )}
          </div>
        </div>
      </div>

      <div className="container" style={{ paddingBottom: "var(--s-16)" }}>
        <div className="form-card">
          <form onSubmit={handleProfileSubmit} className="card card-pad form-stack">
            {success && (
              <div className="alert alert-success">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5" /></svg>
                <span>{success}</span>
              </div>
            )}
            {error && (
              <div className="alert alert-danger">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 8v4M12 16h.01" /></svg>
                <span>{error}</span>
              </div>
            )}

            {/* 头像 */}
            <div className="avatar-upload">
              <div className={"avatar" + (editing ? " editable" : "")} onClick={editing ? handleAvatarClick : undefined} role={editing ? "button" : undefined}>
                {avatarSrc ? <img src={avatarSrc} alt="头像" /> : <span>{initial}</span>}
                {editing && (
                  <span className="cam">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" /><circle cx="12" cy="13" r="4" /></svg>
                  </span>
                )}
              </div>
              <div className="au-meta">
                <span className="au-name">{profile.profile.nickname || profile.user.username}</span>
                {editing ? (
                  <>
                    <span className="au-hint">点击头像更换 · 不超过 2MB</span>
                    <button className="btn btn-ghost btn-sm" type="button" onClick={handleAvatarClick}>更换头像</button>
                  </>
                ) : (
                  <span className="au-hint">头像与个人资料</span>
                )}
              </div>
              <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/gif,image/webp" onChange={handleAvatarChange} style={{ display: "none" }} />
            </div>

            {/* 只读：用户名 / 邮箱 */}
            <div className="form-grid">
              <div className="field">
                <label className="label">用户名</label>
                <div className="field-value">{profile.user.username}</div>
              </div>
              <div className="field">
                <label className="label">邮箱</label>
                <div className={"field-value" + (profile.user.email ? "" : " muted")}>{profile.user.email || "未设置"}</div>
              </div>
            </div>

            {/* 可编辑：昵称 / 生日 */}
            <div className="form-grid">
              <div className="field">
                <label className="label">昵称</label>
                {editing ? (
                  <input className="input" type="text" value={nickname} onChange={(e) => setNickname(e.target.value)} placeholder="设置昵称" maxLength={50} />
                ) : (
                  <div className={"field-value" + (profile.profile.nickname ? "" : " muted")}>{profile.profile.nickname || "未设置"}</div>
                )}
              </div>
              <div className="field">
                <label className="label">生日</label>
                {editing ? (
                  <input className="input" type="date" value={birthday} onChange={(e) => setBirthday(e.target.value)} />
                ) : (
                  <div className={"field-value" + (profile.profile.birthday ? "" : " muted")}>{profile.profile.birthday || "未设置"}</div>
                )}
              </div>
            </div>

            {/* 性别 */}
            <div className="field">
              <label className="label">性别</label>
              {editing ? (
                <select className="select" value={gender} onChange={(e) => setGender(e.target.value)}>
                  {GENDER_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              ) : (
                <div className={"field-value" + (profile.profile.gender ? "" : " muted")}>{genderLabel(profile.profile.gender)}</div>
              )}
            </div>

            {/* 个人简介 */}
            <div className="field">
              <label className="label">个人简介</label>
              {editing ? (
                <textarea className="textarea" value={bio} onChange={(e) => setBio(e.target.value)} placeholder="介绍一下自己吧" maxLength={500} rows={3} />
              ) : (
                <div className={"field-value" + (profile.profile.bio ? "" : " muted")}>{profile.profile.bio || "未设置"}</div>
              )}
            </div>

            {editing && (
              <div className="form-actions">
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? "保存中…" : "保存"}</button>
              </div>
            )}
          </form>

          {/* 修改密码 */}
          <div className={"collapse" + (showPasswordForm ? " is-open" : "")} style={{ marginTop: "var(--s-5)" }}>
            <button type="button" className="collapse-head" onClick={() => setShowPasswordForm((v) => !v)}>
              <svg className="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
              修改密码
              <svg className="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>
            </button>
            {showPasswordForm && (
              <form className="collapse-body" onSubmit={handlePasswordSubmit}>
                {passwordError && (
                  <div className="alert alert-danger">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 8v4M12 16h.01" /></svg>
                    <span>{passwordError}</span>
                  </div>
                )}
                <div className="field">
                  <label className="label">原密码</label>
                  <input className="input" type="password" value={oldPassword} onChange={(e) => setOldPassword(e.target.value)} required />
                </div>
                <div className="form-grid">
                  <div className="field">
                    <label className="label">新密码</label>
                    <input className="input" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={8} />
                  </div>
                  <div className="field">
                    <label className="label">确认新密码</label>
                    <input className="input" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required />
                  </div>
                </div>
                <div className="form-actions">
                  <button className="btn btn-primary" type="submit" disabled={passwordSaving}>{passwordSaving ? "修改中…" : "确认修改"}</button>
                </div>
              </form>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
