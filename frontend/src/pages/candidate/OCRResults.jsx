import { useEffect, useState } from "react";
import { api, API_URL } from "../../lib/api";

const fields = [
  ["name", "Full name", "text"], ["email", "Email address", "email"], ["phone", "Phone number", "tel"],
];

function toForm(data = {}) {
  return {
    name: data.name || "",
    email: data.email || "",
    phone: data.phone || "",
    education: Array.isArray(data.education) ? data.education.join("\n") : data.education || "",
    experience: Array.isArray(data.experience) ? data.experience.join("\n") : data.experience || "",
    skills: Array.isArray(data.skills) ? data.skills.join(", ") : data.skills || "",
    pages: data.pages || [],
    raw_text: data.raw_text || "",
  };
}

function toPayload(form) {
  return {
    name: form.name.trim() || null,
    email: form.email.trim() || null,
    phone: form.phone.trim() || null,
    education: form.education.split("\n").map(value => value.trim()).filter(Boolean),
    experience: form.experience.split("\n").map(value => value.trim()).filter(Boolean),
    skills: form.skills.split(",").map(value => value.trim()).filter(Boolean),
    pages: form.pages,
    raw_text: form.raw_text,
  };
}

export function OCRResults() {
  const [resumes, setResumes] = useState([]);
  const [resumeId, setResumeId] = useState("");
  const [result, setResult] = useState(null);
  const [form, setForm] = useState(toForm());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    api("/api/resumes").then(items => {
      setResumes(items);
      if (items.length) setResumeId(items[0].id);
    }).catch(err => setError(err.message));
  }, []);

  useEffect(() => {
    if (!resumeId) return;
    api(`/api/resumes/${resumeId}/status`).then(response => {
      setResult(response);
      setForm(toForm(response.extracted_data));
    }).catch(err => setError(err.message));
  }, [resumeId]);

  useEffect(() => {
    if (result?.status !== "processing" || !resumeId) return undefined;
    const timer = window.setInterval(() => {
      api(`/api/resumes/${resumeId}/status`).then(response => {
        setResult(response);
        if (response.status !== "processing") setForm(toForm(response.extracted_data));
      }).catch(err => setError(err.message));
    }, 2200);
    return () => window.clearInterval(timer);
  }, [resumeId, result?.status]);

  async function refresh() {
    if (!resumeId) return;
    const response = await api(`/api/resumes/${resumeId}/status`);
    setResult(response);
    setForm(toForm(response.extracted_data));
    setResumes(current => current.map(resume => resume.id === resumeId ? { ...resume, status: response.status } : resume));
  }

  async function process() {
    if (!resumeId) { setError("Upload or select a resume first."); return; }
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await api("/api/resume/ocr", { method: "POST", body: JSON.stringify({ resume_id: resumeId }) });
      setResult(response);
      setForm(toForm(response.extracted_data));
      if (response.status === "completed") setMessage("Scan complete. Review and correct the fields below.");
      else if (response.status === "failed") setError(response.error || "Resume processing failed.");
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function saveProfile() {
    if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) { setError("Enter a valid email address or leave it blank."); return; }
    if (form.phone && !/^[+\d][\d ()-]{6,24}$/.test(form.phone)) { setError("Enter a valid phone number or leave it blank."); return; }
    setBusy(true); setError(""); setMessage("");
    const payload = toPayload(form);
    try {
      await api(`/api/resumes/${resumeId}/ocr`, { method: "PUT", body: JSON.stringify(payload) });
      await api(`/api/resumes/${resumeId}/profile-data`, { method: "PUT", body: JSON.stringify(payload) });
      setMessage("Corrected resume details saved to your profile.");
      await refresh();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  function update(field, value) { setForm(current => ({ ...current, [field]: value })); }
  function downloadPages() {
    if (!form.raw_text) return;
    const blob = new Blob([form.raw_text], { type: "text/plain;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob); link.download = `resume-${resumeId}-extracted.txt`; link.click();
    window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }

  const extracted = result?.status === "completed";
  return <section className="dashboard-page candidate-form-page ocr-page">
    <span className="eyebrow">Resume scan</span><h1>Review what we <em>found.</em></h1>
    <p className="muted page-intro">Scanned details stay editable. Any information that could not be read is left blank for you to fill in.</p>
    <div className="snap-toolbar"><label className="ocr-resume-select">Resume<select value={resumeId} onChange={event => { setResumeId(event.target.value); setMessage(""); setError(""); }}><option value="">Choose a resume</option>{resumes.map(resume => <option key={resume.id} value={resume.id}>{resume.original_name} · {resume.status}</option>)}</select></label><button className="primary-button" onClick={process} disabled={busy || !resumeId}>{busy ? "Processing…" : "Process resume →"}</button>{resumeId && <button className="secondary-button" onClick={() => refresh().catch(err => setError(err.message))}>Refresh status</button>}</div>
    {error && <div className="error-box" role="alert">{error}</div>}{message && <div className="success-box" role="status">{message}</div>}
    {result && <section className="ocr-editor">
      <div className="ocr-result-heading"><div><span className="eyebrow">Resume {resumeId.slice(-8)}</span><h2>Extracted details</h2></div><span className={`status-badge status-${result.status}`}>{result.status}</span></div>
      {result.status === "processing" && <div className="skeleton-line" aria-label="Processing resume"/>}
      {result.status === "failed" && <div className="error-box">{result.error || "The scan could not be completed. Check that Tesseract OCR is installed, then try again."}</div>}
      {extracted && <>
        <div className="ocr-form-card"><div className="ocr-fields-grid">{fields.map(([key, label, type]) => <label key={key} className={!form[key] ? "missing-field" : ""}>{label}{!form[key] && <small>Not found — enter it if you wish</small>}<input type={type} value={form[key]} placeholder="Not found" onChange={event => update(key, event.target.value)}/></label>)}</div>
          <label className={!form.education ? "missing-field" : ""}>Education <small>One item per line · blank means not found</small><textarea rows="4" value={form.education} placeholder="Not found" onChange={event => update("education", event.target.value)}/></label>
          <label className={!form.experience ? "missing-field" : ""}>Work experience <small>One item per line · blank means not found</small><textarea rows="5" value={form.experience} placeholder="Not found" onChange={event => update("experience", event.target.value)}/></label>
          <label className={!form.skills ? "missing-field" : ""}>Skills <small>Comma separated · blank means not found</small><input value={form.skills} placeholder="Not found" onChange={event => update("skills", event.target.value)}/></label>
          <div className="detail-actions"><button className="primary-button" onClick={saveProfile} disabled={busy}>{busy ? "Saving…" : "Correct and save to profile →"}</button><button className="secondary-button" onClick={downloadPages}>Download extracted text</button></div>
        </div>
        {!!form.pages.length && <details className="ocr-pages"><summary>Page-wise extracted text ({form.pages.length} pages)</summary>{form.pages.map(page => <article key={page.page_number}><h3>Page {page.page_number}</h3><pre>{page.text || "Not found"}</pre></article>)}</details>}
      </>}
    </section>}
  </section>;
}

export default OCRResults;
