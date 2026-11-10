import { useEffect, useState } from "react";
import { API_URL, api } from "../../lib/api";

const blank = { company_name: "", website: "", industry: "", company_size: "", location: "", description: "", founded_year: "", company_email: "", contact_number: "", social_links: { linkedin: "", facebook: "", instagram: "", x: "" }, logo_url: "" };
const imageUrl = path => path?.startsWith("/") ? `${API_URL}${path}` : path;

export function Company() {
  const [form, setForm] = useState(blank); const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(false); const [file, setFile] = useState(null); const [preview, setPreview] = useState(""); const [error, setError] = useState(""); const [message, setMessage] = useState("");
  useEffect(() => { api("/api/companies/me").then(data => { if (data) setForm(current => ({ ...current, ...data, founded_year: data.founded_year || "", social_links: { ...blank.social_links, ...(data.social_links || {}) } })); }).catch(err => setError(err.message)).finally(() => setLoading(false)); }, []);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  function update(key, value) { setForm(current => ({ ...current, [key]: value })); }
  function chooseLogo(event) {
    const selected = event.target.files?.[0]; setError(""); setMessage("");
    if (!selected) return;
    if (!/^image\/(png|jpeg|webp)$/.test(selected.type) || selected.size > 2 * 1024 * 1024) { setFile(null); setPreview(""); event.target.value = ""; setError("Choose a PNG, JPEG, or WebP image up to 2 MB."); return; }
    if (preview) URL.revokeObjectURL(preview);
    setFile(selected); setPreview(URL.createObjectURL(selected));
  }
  async function save(event) {
    event.preventDefault(); setSaving(true); setError(""); setMessage("");
    try {
      let logoUrl = form.logo_url;
      if (file) { const data = new FormData(); data.append("file", file); const uploaded = await api("/api/companies/logo", { method: "POST", body: data }); logoUrl = uploaded.logo_url; }
      const payload = { ...form, logo_url: undefined, founded_year: form.founded_year ? Number(form.founded_year) : null, social_links: Object.fromEntries(Object.entries(form.social_links).filter(([, value]) => value.trim())) };
      const saved = await api("/api/companies/me", { method: "PUT", body: JSON.stringify(payload) });
      setForm(current => ({ ...current, ...saved, logo_url: logoUrl, founded_year: saved.founded_year || "", social_links: { ...blank.social_links, ...(saved.social_links || {}) } }));
      setFile(null); setPreview(""); setMessage("Company profile saved successfully.");
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }
  if (loading) return <section className="dashboard-page"><p className="loading">Loading company profile…</p></section>;
  return <section className="dashboard-page recruiter-form-page"><span className="eyebrow">Recruiter workspace</span><h1>Company <em>profile.</em></h1><p className="muted page-intro">This profile belongs to your recruiter account and appears on your job listings.</p>{error && <div className="error-box" role="alert">{error}</div>}{message && <div className="success-box" role="status">{message}</div>}
    <form className="profile-form company-profile-form" onSubmit={save}>
      <section className="company-logo-editor"><div className="company-logo-preview">{preview || form.logo_url ? <img src={preview || imageUrl(form.logo_url)} alt="Company logo preview"/> : <span>{form.company_name?.[0] || "＋"}</span>}</div><div><strong>Company logo</strong><p className="muted">PNG, JPEG, or WebP · maximum 2 MB. Preview before saving.</p><label className="secondary-button logo-file-label">Choose logo<input type="file" accept="image/png,image/jpeg,image/webp" onChange={chooseLogo}/></label></div></section>
      <div className="form-grid"><label>Company name<input required maxLength="160" value={form.company_name || ""} onChange={e => update("company_name", e.target.value)}/></label><label>Website<input type="url" maxLength="300" placeholder="https://company.com" value={form.website || ""} onChange={e => update("website", e.target.value)}/></label><label>Industry<input maxLength="120" value={form.industry || ""} onChange={e => update("industry", e.target.value)}/></label><label>Company size<select value={form.company_size || ""} onChange={e => update("company_size", e.target.value)}><option value="">Select company size</option><option>1–10 employees</option><option>11–50 employees</option><option>51–200 employees</option><option>201–500 employees</option><option>501–1,000 employees</option><option>1,001+ employees</option></select></label><label>Company location<input maxLength="160" value={form.location || ""} onChange={e => update("location", e.target.value)}/></label><label>Founded year<input type="number" min="1800" max={new Date().getFullYear()} value={form.founded_year || ""} onChange={e => update("founded_year", e.target.value)}/></label><label>Company email<input type="email" maxLength="254" value={form.company_email || ""} onChange={e => update("company_email", e.target.value)}/></label><label>Contact number<input type="tel" maxLength="40" value={form.contact_number || ""} onChange={e => update("contact_number", e.target.value)}/></label></div>
      <label>Company description<textarea rows="6" maxLength="5000" value={form.description || ""} onChange={e => update("description", e.target.value)}/></label>
      <h2>Social links</h2><div className="form-grid">{["linkedin", "facebook", "instagram", "x"].map(key => <label key={key}>{key === "x" ? "X / Twitter" : key[0].toUpperCase() + key.slice(1)}<input type="url" placeholder="https://" value={form.social_links?.[key] || ""} onChange={e => setForm(current => ({ ...current, social_links: { ...current.social_links, [key]: e.target.value } }))}/></label>)}</div>
      <button className="primary-button" disabled={saving}>{saving ? "Saving company profile…" : "Save company profile →"}</button>
    </form>
  </section>;
}

export default Company;
