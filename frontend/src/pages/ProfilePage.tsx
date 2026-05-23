import { useState, useEffect, useRef, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import "./ProfilePage.css";

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
      .catch(() => navigate("/login"))
      .finally(() => setLoading(false));
  }, [navigate]);

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
      <div className="profile-page">
        <div className="profile-loading">加载中...</div>
      </div>
    );
  }

  if (!profile) return null;

  const avatarSrc = avatarPreview || profile.profile.avatar;

  return (
    <div className="profile-page">
      <div className="profile-card">
        <div className="profile-header">
          <button className="profile-back-btn" onClick={() => navigate("/")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5" /><path d="m12 19-7-7 7-7" />
            </svg>
            返回
          </button>
          <h2>个人资料</h2>
          {!editing ? (
            <button className="profile-edit-btn" onClick={() => setEditing(true)}>
              编辑
            </button>
          ) : (
            <div className="profile-header-actions">
              <button className="profile-cancel-btn" onClick={handleCancel}>
                取消
              </button>
            </div>
          )}
        </div>

        {success && <div className="profile-success">{success}</div>}
        {error && <div className="profile-error">{error}</div>}

        <form onSubmit={handleProfileSubmit}>
          {/* Avatar */}
          <div className="profile-avatar-section">
            <div
              className={`profile-avatar ${editing ? "editable" : ""}`}
              onClick={editing ? handleAvatarClick : undefined}
            >
              {avatarSrc ? (
                <img src={avatarSrc} alt="头像" />
              ) : (
                <span className="profile-avatar-placeholder">
                  {profile.user.username.charAt(0).toUpperCase()}
                </span>
              )}
              {editing && (
                <div className="profile-avatar-overlay">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
                    <circle cx="12" cy="13" r="4" />
                  </svg>
                </div>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/gif,image/webp"
              onChange={handleAvatarChange}
              style={{ display: "none" }}
            />
          </div>

          {/* Info Fields */}
          <div className="profile-fields">
            <div className="profile-field">
              <label>用户名</label>
              <div className="profile-field-value">{profile.user.username}</div>
            </div>
            <div className="profile-field">
              <label>邮箱</label>
              <div className="profile-field-value">{profile.user.email || "未设置"}</div>
            </div>

            <div className="profile-field">
              <label>昵称</label>
              {editing ? (
                <input
                  type="text"
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  placeholder="设置昵称"
                  maxLength={50}
                />
              ) : (
                <div className="profile-field-value">{profile.profile.nickname || "未设置"}</div>
              )}
            </div>

            <div className="profile-field">
              <label>生日</label>
              {editing ? (
                <input
                  type="date"
                  value={birthday}
                  onChange={(e) => setBirthday(e.target.value)}
                />
              ) : (
                <div className="profile-field-value">{profile.profile.birthday || "未设置"}</div>
              )}
            </div>

            <div className="profile-field">
              <label>性别</label>
              {editing ? (
                <select value={gender} onChange={(e) => setGender(e.target.value)}>
                  {GENDER_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              ) : (
                <div className="profile-field-value">
                  {GENDER_OPTIONS.find((o) => o.value === profile.profile.gender)?.label || "未设置"}
                </div>
              )}
            </div>

            <div className="profile-field">
              <label>个人简介</label>
              {editing ? (
                <textarea
                  value={bio}
                  onChange={(e) => setBio(e.target.value)}
                  placeholder="介绍一下自己吧"
                  maxLength={500}
                  rows={3}
                />
              ) : (
                <div className="profile-field-value">{profile.profile.bio || "未设置"}</div>
              )}
            </div>
          </div>

          {editing && (
            <button className="profile-save-btn" type="submit" disabled={saving}>
              {saving ? "保存中..." : "保存"}
            </button>
          )}
        </form>

        {/* Password Change */}
        <div className="profile-password-section">
          <button
            className="profile-password-toggle"
            onClick={() => setShowPasswordForm(!showPasswordForm)}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            修改密码
            <svg
              className={`profile-chevron ${showPasswordForm ? "open" : ""}`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>

          {showPasswordForm && (
            <form className="profile-password-form" onSubmit={handlePasswordSubmit}>
              {passwordError && <div className="profile-error">{passwordError}</div>}
              <div className="profile-field">
                <label>原密码</label>
                <input
                  type="password"
                  value={oldPassword}
                  onChange={(e) => setOldPassword(e.target.value)}
                  required
                />
              </div>
              <div className="profile-field">
                <label>新密码</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={8}
                />
              </div>
              <div className="profile-field">
                <label>确认新密码</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />
              </div>
              <button className="profile-save-btn" type="submit" disabled={passwordSaving}>
                {passwordSaving ? "修改中..." : "确认修改"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
