import { useEffect, useRef, useState } from "react";
import { API_URL, api, formatApiError } from "../../lib/api";
import { uploadWithProgress } from "../../lib/upload";
import { ConfirmDialog } from "../../components/ui";

const MAX_FILE_SIZE = 5 * 1024 * 1024;

async function downloadFile(path, filename) {
  const token = localStorage.getItem("skillsphere_token") || sessionStorage.getItem("skillsphere_token");
  const response = await fetch(`${API_URL}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(formatApiError(body)); }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function getPdfUrl(path) {
  const token = localStorage.getItem("skillsphere_token") || sessionStorage.getItem("skillsphere_token");
  const response = await fetch(`${API_URL}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(formatApiError(body)); }
  return URL.createObjectURL(await response.blob());
}

function fileStatusLabel(status) {
  return ({ uploaded: "Uploaded", processing: "Processing", completed: "Completed", failed: "Failed" })[status] || "Uploaded";
}

export function Resume() {
  const [resumes, setResumes] = useState(null);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [replaceTarget, setReplaceTarget] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [preview, setPreview] = useState(null);
  const [textPreview, setTextPreview] = useState(null);
  const inputRef = useRef(null);

  async function load() {
    try { setResumes(await api("/api/resumes")); setError(""); }
    catch (err) { setError(err.message); setResumes(null); }
  }

  useEffect(() => { load(); }, []);
  useEffect(() => () => { if (preview?.url) URL.revokeObjectURL(preview.url); }, [preview]);
  useEffect(() => {
    if (!resumes?.some(resume => ["uploaded", "processing"].includes(resume.status))) return undefined;
    const timer = window.setInterval(async () => {
      const processing = resumes.filter(resume => ["uploaded", "processing"].includes(resume.status));
      const updates = await Promise.all(processing.map(resume => api(`/api/resumes/${resume.id}/status`).catch(() => null)));
      setResumes(current => current?.map(resume => {
        const updated = updates.find(value => value?.id === resume.id);
        return updated ? { ...resume, ...updated } : resume;
      }));
    }, 2200);
    return () => window.clearInterval(timer);
  }, [resumes]);

  function choose(selected) {
    setMessage("");
    setError("");
    if (!selected) return;
    if (!/\.pdf$/i.test(selected.name)) {
      setFile(null);
      setError("Choose a PDF resume.");
      return;
    }
    if (selected.size > MAX_FILE_SIZE) {
      setFile(null);
      setError("Resume must be 5 MB or smaller.");
      return;
    }
    const allowedMime = ["application/pdf", "application/octet-stream", ""];
    if (!allowedMime.includes(selected.type)) {
      setFile(null);
      setError("Choose a PDF file.");
      return;
    }
    setFile(selected);
    setProgress(0);
  }

  async function upload(event) {
    event.preventDefault();
    if (!file) { setError("Choose a resume file first."); return; }
    if (replaceTarget) return;
    await performUpload();
  }

  async function performUpload() {
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    setBusy(true);
    setProgress(0);
    setError("");
    setMessage("Uploading resume…");
    try {
      const endpoint = replaceTarget ? `/api/resumes/${replaceTarget.id}/replace` : "/api/resumes/upload";
      const result = await uploadWithProgress(endpoint, body, setProgress);
      setProgress(100);
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      await load();
      setMessage(`${replaceTarget ? "Resume replaced" : "Upload complete"}.`);
      setReplaceTarget(null);
    } catch (err) { setError(err.message); setMessage(""); }
    finally { setBusy(false); }
  }

  async function remove() {
    const id = deleteTarget?.id;
    if (!id) return;
    try {
      await api(`/api/resumes/${id}`, { method: "DELETE" });
      setResumes(items => items.filter(item => item.id !== id));
      setMessage("Resume deleted.");
      setError("");
    } catch (err) { setError(err.message); }
    finally { setDeleteTarget(null); }
  }

  async function openPreview(resume) {
    try { const url = await getPdfUrl(`/api/resumes/${resume.id}/preview`); setPreview({ url, name: resume.original_name }); setError(""); }
    catch (err) { setError(err.message); }
  }

  async function showText(resume) {
    try { const data = await api(`/api/resumes/${resume.id}/text`); setTextPreview({ id: resume.id, text: data.text, status: data.status, error: data.error }); }
    catch (err) { setError(err.message); }
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files?.[0]);
  }

  return <section className="dashboard-page candidate-form-page">
    <span className="eyebrow">My resume</span><h1>Keep your story <em>ready.</em></h1>
    <p className="muted page-intro">Upload a PDF to securely store, preview, download, and extract text from your resume.</p>
    <form className={`upload-card resume-uploader ${dragging ? "is-dragging" : ""}`} onSubmit={upload} onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={handleDrop}>
      <div className="upload-icon">↥</div><h2>Drop a PDF here</h2><p className="muted">PDF only · maximum 5 MB · up to 20 pages</p>
      <input ref={inputRef} type="file" accept=".pdf,application/pdf" onChange={event => choose(event.target.files?.[0])}/>
      {replaceTarget && <button type="button" className="text-button" onClick={() => { setReplaceTarget(null); setFile(null); }}>Cancel replacement</button>}
      {file && <div className="selected-file"><strong>{file.name}</strong><span>{(file.size / 1024 / 1024).toFixed(2)} MB</span></div>}
      {busy && <div className="upload-progress" role="status" aria-live="polite"><div className="upload-progress-label"><span>Uploading securely</span><strong>{progress}%</strong></div><div className="upload-progress-track"><span style={{ width: `${progress}%` }}/></div></div>}
      <button className="primary-button" disabled={busy || !file}>{busy ? "Uploading…" : replaceTarget ? `Replace ${replaceTarget.original_name} →` : "Upload resume →"}</button>
    </form>
    {error && <div className="error-box" role="alert">{error}</div>}{message && <div className="success-box" role="status">{message}</div>}
    <section className="resume-list"><div className="section-heading"><div><span className="eyebrow">Your files</span><h2>Resume history</h2></div><span className="muted">{resumes?.length || 0} saved</span></div>
      {resumes === null ? error ? <div className="error-box">Couldn’t load resumes: {error}</div> : <div className="loading">Loading resumes…</div> : resumes.length ? resumes.map(resume => <article className="resume-row resume-history-card" key={resume.id}>
        <div className="resume-icon">{resume.content_type === "application/pdf" ? "PDF" : "FILE"}</div>
        <div className="row-main"><strong>{resume.original_name}</strong><small>Uploaded {new Date(resume.upload_date || resume.created_at).toLocaleDateString()} · {(resume.size / 1024 / 1024).toFixed(2)} MB</small>{resume.error && <small className="resume-error">{resume.error}</small>}</div>
        <span className={`status-badge status-${resume.status}`}>{fileStatusLabel(resume.status)}</span>
        <div className="row-actions"><button className="text-button" onClick={() => openPreview(resume)}>Preview</button><button className="text-button" onClick={() => downloadFile(`/api/resumes/${resume.id}/download`, resume.original_name).catch(err => setError(err.message))}>Download</button><button className="text-button" onClick={() => { setReplaceTarget(resume); setFile(null); inputRef.current?.click(); }}>Replace</button><button className="text-button" onClick={() => showText(resume)} disabled={resume.status !== "completed"}>Extracted text</button><button className="text-button danger-text" onClick={() => setDeleteTarget(resume)}>Delete</button></div>
        {resume.error && <small className="resume-error">{resume.error}</small>}{textPreview?.id === resume.id && <div className="extracted-text"><strong>Extracted text</strong>{textPreview.text ? <pre>{textPreview.text}</pre> : <p className="muted">No text was extracted.</p>}<button type="button" className="text-button" onClick={() => setTextPreview(null)}>Close text</button></div>}
      </article>) : <div className="empty-state compact-empty"><div className="empty-icon">✦</div><h3>No resumes yet</h3><p>Upload a PDF to extract and review your resume text.</p></div>}
    </section>
    {preview && <section className="resume-preview-panel"><div className="section-heading"><div><span className="eyebrow">Resume preview</span><h2>{preview.name}</h2></div><button className="text-button" onClick={() => setPreview(null)}>Close preview</button></div><iframe title={`Preview of ${preview.name}`} src={preview.url} className="resume-preview-frame"/></section>}
    <ConfirmDialog open={Boolean(deleteTarget)} title="Delete this resume?" message="The PDF and its extracted text will be permanently removed." confirmLabel="Delete resume" onCancel={() => setDeleteTarget(null)} onConfirm={remove}/>
    <ConfirmDialog open={Boolean(replaceTarget && file)} title="Replace this resume?" message={`“${replaceTarget?.original_name}” will be replaced by “${file?.name}”.`} confirmLabel="Replace resume" onCancel={() => setReplaceTarget(null)} onConfirm={performUpload} busy={busy}/>
  </section>;
}

export default Resume;
