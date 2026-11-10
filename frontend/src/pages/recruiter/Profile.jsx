import { useEffect, useState } from "react";
import { api } from "../../lib/api";

export function RecruiterProfile() {
  const [form, setForm] = useState({ full_name: "", email: "", phone: "", designation: "", company_name: "" });
  const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(false); const [error, setError] = useState(""); const [message, setMessage] = useState("");
  useEffect(() => { api("/api/recruiter/profile").then(setForm).catch(err => setError(err.message)).finally(() => setLoading(false)); }, []);
  function update(key, value) { setForm(current => ({ ...current, [key]: value })); }
  async function save(event) { event.preventDefault(); setSaving(true); setError(""); setMessage(""); try { const profile = await api("/api/recruiter/profile", { method: "PUT", body: JSON.stringify({ full_name: form.full_name, phone: form.phone, designation: form.designation }) }); setForm(current => ({ ...current, ...profile })); setMessage("Recruiter profile updated."); } catch (err) { setError(err.message); } finally { setSaving(false); } }
  if (loading) return <section className="dashboard-page"><p className="loading">Loading recruiter profile…</p></section>;
  return <section className="dashboard-page recruiter-form-page"><span className="eyebrow">Recruiter workspace</span><h1>Your recruiter <em>profile.</em></h1><p className="muted page-intro">Update your contact details. Your role and linked company are managed by SkillSphere.</p>{error && <div className="error-box" role="alert">{error}</div>}{message && <div className="success-box" role="status">{message}</div>}<form className="profile-form" onSubmit={save}><div className="form-grid"><label>Recruiter name<input required minLength="2" maxLength="120" value={form.full_name || ""} onChange={e => update("full_name", e.target.value)}/></label><label>Email address<input disabled value={form.email || ""}/></label><label>Phone number<input type="tel" maxLength="40" value={form.phone || ""} onChange={e => update("phone", e.target.value)}/></label><label>Designation<input maxLength="120" placeholder="e.g. Talent Acquisition Lead" value={form.designation || ""} onChange={e => update("designation", e.target.value)}/></label><label>Linked company<input disabled value={form.company_name || "No company profile yet"}/></label></div><button className="primary-button" disabled={saving}>{saving ? "Saving…" : "Save recruiter profile →"}</button></form></section>;
}

export default RecruiterProfile;
