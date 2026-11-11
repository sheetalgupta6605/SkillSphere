import { useEffect, useState } from "react";
import { api } from "../../lib/api";

const emptyProfile = { full_name: "", phone: "", date_of_birth: "", gender: "", location: "", address: "", linkedin: "", github: "", portfolio: "" };

function normalizeUrl(val) {
  if (!val || typeof val !== "string") return null;
  const trimmed = val.trim();
  if (!trimmed) return null;
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

export function PersonalDetails({ user }) {
  const [form, setForm] = useState({ ...emptyProfile, full_name: user?.full_name || "", email: user?.email || "" });
  const [state, setState] = useState({ loading: true, saving: false, error: "", message: "" });
  useEffect(() => {
    api("/api/candidates/profile")
      .then(profile => setForm(current => ({ ...current, ...profile })))
      .catch(error => setState({ loading: false, saving: false, error: error?.message || "Failed to load personal details.", message: "" }))
      .finally(() => setState(current => ({ ...current, loading: false })));
  }, []);
  function update(key, value) { setForm(current => ({ ...current, [key]: value })); }
  async function save(event) {
    event.preventDefault();
    setState({ loading: false, saving: true, error: "", message: "" });
    try {
      await api("/api/candidates/profile", {
        method: "PUT",
        body: JSON.stringify({
          ...form,
          linkedin: normalizeUrl(form.linkedin),
          github: normalizeUrl(form.github),
          portfolio: normalizeUrl(form.portfolio)
        })
      });
      setState({ loading: false, saving: false, error: "", message: "Personal details saved successfully." });
    } catch (error) {
      setState({ loading: false, saving: false, error: error?.message || (typeof error === "string" ? error : "Failed to save details."), message: "" });
    }
  }
  if (state.loading) return <section className="dashboard-page"><div className="loading">Loading your personal details…</div></section>;
  return <section className="dashboard-page candidate-form-page"><span className="eyebrow">Personal details</span><h1>Make your profile <em>personal.</em></h1><p className="muted page-intro">Keep your contact information current so recruiters can reach you with the right opportunity.</p><form className="profile-form detail-form" onSubmit={save}><div className="form-grid"><label>Full name<input required value={form.full_name || ""} onChange={e => update("full_name", e.target.value)}/></label><label>Email address<input value={form.email || user?.email || ""} disabled/></label><label>Phone number<input value={form.phone || ""} onChange={e => update("phone", e.target.value)}/></label><label>Date of birth<input type="date" value={form.date_of_birth || ""} onChange={e => update("date_of_birth", e.target.value)}/></label><label>Gender <small>optional</small><select value={form.gender || ""} onChange={e => update("gender", e.target.value)}><option value="">Prefer not to say</option><option>Female</option><option>Male</option><option>Non-binary</option></select></label><label>Current location<input value={form.location || ""} onChange={e => update("location", e.target.value)}/></label></div><label>Address<textarea rows="3" value={form.address || ""} onChange={e => update("address", e.target.value)}/></label><div className="form-grid"><label>LinkedIn profile<input type="url" placeholder="https://linkedin.com/in/…" value={form.linkedin || ""} onChange={e => update("linkedin", e.target.value)}/></label><label>GitHub profile<input type="url" placeholder="https://github.com/…" value={form.github || ""} onChange={e => update("github", e.target.value)}/></label><label>Portfolio website<input type="url" placeholder="https://…" value={form.portfolio || ""} onChange={e => update("portfolio", e.target.value)}/></label></div>{state.error && <div className="error-box">{state.error}</div>}{state.message && <div className="success-box">{state.message}</div>}<button className="primary-button" disabled={state.saving}>{state.saving ? "Saving…" : "Save personal details →"}</button></form></section>;
}

export default PersonalDetails;
