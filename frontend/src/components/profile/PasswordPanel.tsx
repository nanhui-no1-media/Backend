import { useState, type FormEvent } from "react";
import { api } from "../../api/client";
import "../../styles/form.css";

export default function PasswordPanel() {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (newPassword !== confirm) { setError("两次输入的密码不一致"); return; }
    if (newPassword.length < 8) { setError("新密码至少 8 个字符"); return; }
    setSaving(true);
    try {
      await api.changePassword(oldPassword, newPassword);
      setOldPassword(""); setNewPassword(""); setConfirm("");
      setSuccess("密码已修改");
      setTimeout(() => setSuccess(""), 3000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="card card-pad form-stack" onSubmit={submit}>
      {success && <div className="alert alert-success"><span>{success}</span></div>}
      {error && <div className="alert alert-danger"><span>{error}</span></div>}
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
          <input className="input" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
        </div>
      </div>
      <div className="form-actions">
        <button className="btn btn-primary" type="submit" disabled={saving}>{saving ? "修改中…" : "确认修改"}</button>
      </div>
    </form>
  );
}
