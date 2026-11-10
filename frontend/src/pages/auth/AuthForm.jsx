import { useState } from "react";
import { useAuth } from "../../context/AuthContext";

export function AuthForm({ mode, onSuccess, onNavigate }) {
  const { login, register } = useAuth();
  const [form, setForm] = useState({
    full_name: "", email: "", password: "", confirm_password: "", role: "candidate",
    contact_number: "", company_name: "", company_website: "", company_location: "",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [remember, setRemember] = useState(false);
  const [forgot, setForgot] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "register") {
        await register(form);
        onNavigate("login");
        return;
      }
      const signedInUser = await login({ email: form.email, password: form.password }, remember);
      onSuccess(signedInUser);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const registeringRecruiter = mode === "register" && form.role === "recruiter";
  return <section className="auth-page"><div className="auth-panel">
    <span className="eyebrow">{mode === "login" ? "Welcome back" : "Create your SkillSphere account"}</span>
    <h1>{mode === "login" ? "Good to see you." : registeringRecruiter ? "Recruiter registration" : "Candidate registration"}</h1>
    <p className="muted">{mode === "login" ? "Sign in to continue your career journey." : "Your account will be ready after you sign in."}</p>
    <form onSubmit={submit}>
      {mode === "register" && <>
        <label>Account type<select value={form.role} onChange={(event) => update("role", event.target.value)}><option value="candidate">Candidate / job seeker</option><option value="recruiter">Recruiter</option></select></label>
        <label>Full name<input required minLength="2" maxLength="120" autoComplete="name" value={form.full_name} onChange={(event) => update("full_name", event.target.value)} /></label>
      </>}
      <label>Email address<input required type="email" autoComplete="email" value={form.email} onChange={(event) => update("email", event.target.value)} /></label>
      {mode === "register" && <label>Contact number (optional)<input type="tel" maxLength="40" autoComplete="tel" value={form.contact_number} onChange={(event) => update("contact_number", event.target.value)} /></label>}
      {registeringRecruiter && <>
        <label>Company name<input required minLength="2" maxLength="160" autoComplete="organization" value={form.company_name} onChange={(event) => update("company_name", event.target.value)} /></label>
        <label>Company website (optional)<input type="url" value={form.company_website} onChange={(event) => update("company_website", event.target.value)} placeholder="https://example.com" /></label>
        <label>Company location<input required minLength="2" maxLength="160" value={form.company_location} onChange={(event) => update("company_location", event.target.value)} /></label>
      </>}
      <label>Password<div className="password-field"><input required minLength="8" maxLength="72" pattern="(?=.*[A-Za-z])(?=.*[0-9]).{8,}" title="Use at least 8 characters, including a letter and a number." autoComplete={mode === "login" ? "current-password" : "new-password"} type={showPassword ? "text" : "password"} value={form.password} onChange={(event) => update("password", event.target.value)} placeholder="At least 8 characters and a number" /><button type="button" className="password-toggle" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? "Hide" : "Show"}</button></div></label>
      {mode === "register" && <label>Confirm password<div className="password-field"><input required minLength="8" maxLength="72" autoComplete="new-password" type={showConfirm ? "text" : "password"} value={form.confirm_password} onChange={(event) => update("confirm_password", event.target.value)} /><button type="button" className="password-toggle" onClick={() => setShowConfirm(!showConfirm)} aria-label={showConfirm ? "Hide confirmation" : "Show confirmation"}>{showConfirm ? "Hide" : "Show"}</button></div></label>}
      {mode === "login" && <div className="auth-options"><label className="checkbox-label"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} /> Remember me on this device</label><button type="button" className="text-button" onClick={() => setForgot(!forgot)}>Forgot password?</button></div>}
      {forgot && <div className="notice-box" role="status">Password reset email delivery is not configured. Ask an administrator to configure email before requesting a reset.</div>}
      {error && <div className="error-box" role="alert">{error}</div>}
      <button className="primary-button full" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in →" : "Create account →"}</button>
      {mode === "login" && <small className="muted">Remember me stores the access token in this browser’s local storage. Leave it unchecked to keep it only for this tab session.</small>}
    </form>
    <p className="auth-switch">{mode === "login" ? "New to SkillSphere?" : "Already have an account?"} <button type="button" onClick={() => onNavigate(mode === "login" ? "register" : "login")}>{mode === "login" ? "Create account" : "Sign in"}</button></p>
  </div></section>;
}
