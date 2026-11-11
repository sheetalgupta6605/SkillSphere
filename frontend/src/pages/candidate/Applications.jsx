import { useEffect, useMemo, useRef, useState } from "react";
import { API_URL, api } from "../../lib/api";
import { AtsDecision } from "../../components/AtsDecision";
import { ATS_MINIMUM, latestCurrentAnalysis, meetsAtsMinimum, readApplicationContext } from "../../lib/ats";
import { uploadWithProgress } from "../../lib/upload";

const LABELS = { submitted: "Submitted", applied: "Submitted", under_review: "Under review", shortlisted: "Shortlisted", interview_scheduled: "Interview scheduled", interview: "Interview scheduled", rejected: "Rejected", accepted: "Accepted / offer", selected: "Accepted / offer", withdrawn: "Withdrawn" };
const FILTERS = [["all", "All applications"], ["submitted", "Submitted / pending"], ["under_review", "Under review"], ["shortlisted", "Shortlisted"], ["interview_scheduled", "Interview"], ["accepted", "Accepted / offer"], ["rejected", "Rejected"], ["withdrawn", "Withdrawn"]];
const label = status => LABELS[status] || String(status || "Submitted").replaceAll("_", " ");
const logoSrc = value => value?.startsWith("/") ? `${API_URL}${value}` : value;

export function Applications({ onNavigate }) {
  const [items, setItems] = useState(null); const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [filter, setFilter] = useState("all"); const [query, setQuery] = useState(""); const [busy, setBusy] = useState("");
  useEffect(() => { api("/api/applications/me").then(setItems).catch(err => { setError(err.message); setItems([]); }); }, []);
  const filtered = useMemo(() => (items || []).filter(item => (filter === "all" || (filter === "submitted" ? ["submitted", "applied"].includes(item.status) : filter === "accepted" ? ["accepted", "selected"].includes(item.status) : filter === "interview_scheduled" ? ["interview_scheduled", "interview"].includes(item.status) : item.status === filter)) && `${item.job_title || ""} ${item.company_name || ""}`.toLowerCase().includes(query.toLowerCase())), [items, filter, query]);
  async function withdraw(item) {
    if (!window.confirm("Withdraw this application? This will be saved in your status history.")) return;
    setBusy(item.id); setError("");
    try { const updated = await api(`/api/applications/${item.id}/withdraw`, { method: "POST" }); setItems(current => current.map(value => value.id === item.id ? updated : value)); setNotice("Application withdrawn."); }
    catch (err) { setError(err.message); } finally { setBusy(""); }
  }
  return <section className="dashboard-page candidate-form-page"><span className="eyebrow">Application history</span><h1>Track your <em>momentum.</em></h1><p className="muted page-intro">See where each opportunity stands, from submission through the hiring process.</p>
    {error && <div className="error-box" role="alert">{error}</div>}{notice && <div className="success-box" role="status">{notice}</div>}
    <div className="application-filters"><label>Search jobs or companies<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search applications"/></label><label>Filter status<select value={filter} onChange={event => setFilter(event.target.value)}>{FILTERS.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select></label></div>
    {items === null ? <div className="loading">Loading applications…</div> : filtered.length ? <div className="application-list">{filtered.map(item => <article className="application-tracker-card" key={item.id}>
      <div className="application-tracker-heading">{item.company_logo && <img className="company-detail-logo" src={logoSrc(item.company_logo)} alt={`${item.company_name || "Company"} logo`}/>}<div><span className="eyebrow">{item.company_name || "Company"}</span><h2>{item.job_title || item.job_snapshot?.title || "Job application"}</h2><p className="muted">Applied {item.created_at ? new Date(item.created_at).toLocaleDateString() : "—"} · {item.resume_name || "Resume attached"}</p></div><span className={`status-badge status-${item.status}`}>{label(item.status)}</span></div>
      {item.resume_analysis_id && item.ai_match_score_snapshot != null && <p className="muted">Saved AI match score: <strong>{item.ai_match_score_snapshot}%</strong></p>}
      <div className="row-actions"><button className="secondary-button" onClick={() => onNavigate(`application-${item.id}`)}>View details</button>{!["withdrawn", "rejected", "accepted", "selected"].includes(item.status) && <button className="text-button danger-text" disabled={busy === item.id} onClick={() => withdraw(item)}>{busy === item.id ? "Withdrawing…" : "Withdraw application"}</button>}</div>
    </article>)}</div> : <div className="empty-state compact-empty"><div className="empty-icon">✦</div><h3>{items.length ? "No matching applications" : "No applications yet"}</h3><p>{items.length ? "Try another search or status filter." : "Find a role that fits and your real application history will appear here."}</p>{!items.length && <button className="primary-button" onClick={() => onNavigate("jobs")}>Find jobs →</button>}</div>}
  </section>;
}

export function ApplyJobPage({ jobId, onNavigate }) {
  const [job, setJob] = useState(null);
  const [resumes, setResumes] = useState(null);
  const [analyses, setAnalyses] = useState([]);
  const [resumeId, setResumeId] = useState("");
  const [coverLetter, setCoverLetter] = useState("");
  const [answers, setAnswers] = useState({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState(false);

  // Resume upload state
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [showUploader, setShowUploader] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    let live = true;
    const context = readApplicationContext(jobId);
    Promise.all([
      api(`/api/jobs/${jobId}`),
      api("/api/resumes"),
      api("/api/resume-analysis/me?limit=100").catch(() => ({ items: [] })),
      api("/api/candidates/me").catch(() => null),
    ])
      .then(([j, r, a, p]) => {
        if (!live) return;
        setJob(j);
        const resumeList = r || [];
        setResumes(resumeList);
        setAnalyses(a.items || []);
        const preferred =
          resumeList.find(item => item.id === context?.resumeId && item.status === "completed") ||
          resumeList.find(item => item.id === p?.resume_id && item.status === "completed") ||
          resumeList.find(item => item.status === "completed");
        if (preferred) setResumeId(preferred.id);
      })
      .catch(err => {
        if (live) setError(err.message);
      })
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [jobId]);

  async function handleInlineUpload(e) {
    if (e) e.preventDefault();
    if (!uploadFile) {
      setError("Please select a PDF resume file to upload.");
      return;
    }
    if (!uploadFile.name.toLowerCase().endsWith(".pdf")) {
      setError("Please select a valid PDF file.");
      return;
    }
    const body = new FormData();
    body.append("file", uploadFile);
    setUploading(true);
    setError("");
    setNotice("Uploading resume…");
    setUploadProgress(0);
    try {
      const uploaded = await uploadWithProgress("/api/resumes/upload", body, setUploadProgress);
      setNotice("Resume uploaded! Extracting text and parsing details…");
      const newResumeId = uploaded.id;
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        try {
          const statusRes = await api(`/api/resumes/${newResumeId}/status`);
          if (statusRes.status === "completed") {
            clearInterval(poll);
            const freshResumes = await api("/api/resumes");
            setResumes(freshResumes);
            setResumeId(newResumeId);
            setUploading(false);
            setUploadFile(null);
            setShowUploader(false);
            if (fileInputRef.current) fileInputRef.current.value = "";
            setNotice("Resume uploaded and processed successfully! Now analyze your resume against this job.");
          } else if (statusRes.status === "failed" || attempts > 20) {
            clearInterval(poll);
            setUploading(false);
            const freshResumes = await api("/api/resumes").catch(() => []);
            setResumes(freshResumes);
            setError(statusRes.error || "Resume processing took too long or failed. Please check the PDF.");
          }
        } catch {
          if (attempts > 20) {
            clearInterval(poll);
            setUploading(false);
          }
        }
      }, 1500);
    } catch (err) {
      setError(err.message || "Failed to upload resume.");
      setUploading(false);
    }
  }

  const questions = job?.screening_questions || job?.application_questions || [];
  const selectedResume = resumes?.find(item => item.id === resumeId);
  const match = latestCurrentAnalysis(analyses, selectedResume, job);
  const applicable = Boolean(match && meetsAtsMinimum(match));

  async function analyze() {
    if (!resumeId) {
      setError("A valid resume is required before analyzing or applying.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api(`/api/resume-analysis/analyze/${jobId}`, {
        method: "POST",
        body: JSON.stringify({ resume_id: resumeId }),
      });
      setAnalyses(current => [result, ...current.filter(item => item.id !== result.id)]);
      setNotice("This comparison was saved to your analysis history.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!resumeId) {
      setError("A valid resume is mandatory to apply for a job. Please select or upload a resume.");
      setReview(false);
      return;
    }
    if (!applicable || !match) {
      setError(`Analyze this resume again. An ATS score of ${ATS_MINIMUM}% or higher is required before you can apply.`);
      setReview(false);
      return;
    }
    if (!window.confirm("Submit this application now? Please confirm your resume, cover letter, and answers are correct.")) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api(`/api/applications/${jobId}/apply`, {
        method: "POST",
        body: JSON.stringify({
          resume_id: resumeId,
          cover_letter: coverLetter,
          screening_answers: answers,
          resume_analysis_id: match.id,
        }),
      });
      setNotice("Application submitted successfully.");
      onNavigate(`application-${result.id}`);
    } catch (err) {
      setError(err.message);
      setReview(false);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <section className="dashboard-page"><p className="loading">Loading application form…</p></section>;
  if (!job) return <section className="dashboard-page"><div className="error-box">{error || "Job is unavailable."}</div><button className="secondary-button" onClick={() => onNavigate("jobs")}>Back to jobs</button></section>;

  const hasResumes = Boolean(resumes && resumes.length);

  return (
    <section className="dashboard-page candidate-form-page">
      <button className="back-link" onClick={() => onNavigate(`job-${jobId}`)}>← Back to job</button>
      <span className="eyebrow">Application form</span>
      <h1>{review ? "Review your " : "Apply to "}<em>{job.title}</em></h1>
      <p className="muted page-intro">{job.company_name || "Company"} · {[job.location, job.job_type].filter(Boolean).join(" · ")}</p>

      {error && <div className="error-box" role="alert">{error}</div>}
      {notice && <div className="success-box" role="status">{notice}</div>}

      {!hasResumes ? (
        <div className="dashboard-panel" style={{ border: "2px dashed var(--accent, #6366f1)", padding: "1.5rem", borderRadius: "12px", marginBottom: "1.5rem" }}>
          <div className="panel-heading">
            <h2>Resume Required</h2>
          </div>
          <p>
            A resume is mandatory to apply for <strong>{job.title}</strong>. Please upload your PDF resume below to proceed.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginTop: "1rem" }}>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              disabled={uploading}
              onChange={e => {
                setUploadFile(e.target.files?.[0] || null);
                setError("");
              }}
            />
            {uploading && (
              <div>
                <p className="muted" style={{ margin: "0.25rem 0" }}>Uploading &amp; extracting: {uploadProgress}%</p>
                <div style={{ background: "var(--border)", borderRadius: "4px", height: "6px", width: "100%", overflow: "hidden" }}>
                  <div style={{ background: "var(--accent, #6366f1)", height: "100%", width: `${uploadProgress}%`, transition: "width 0.3s" }} />
                </div>
              </div>
            )}
            <div className="row-actions">
              <button className="primary-button" type="button" disabled={!uploadFile || uploading} onClick={handleInlineUpload}>
                {uploading ? "Processing resume…" : "Upload PDF Resume"}
              </button>
            </div>
          </div>
        </div>
      ) : !review ? (
        <div className="profile-form application-form">
          <label>
            Resume (Mandatory)
            <select
              required
              value={resumeId}
              onChange={event => {
                setResumeId(event.target.value);
                setReview(false);
                setNotice("");
              }}
            >
              <option value="">Choose your resume</option>
              {resumes.map(item => (
                <option value={item.id} key={item.id}>
                  {item.original_name} · {item.status}
                </option>
              ))}
            </select>
          </label>

          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.5rem" }}>
            <button
              type="button"
              className="text-button"
              style={{ fontSize: "0.9rem", padding: "0.2rem 0" }}
              onClick={() => setShowUploader(v => !v)}
            >
              {showUploader ? "✕ Cancel upload" : "+ Upload a new PDF resume"}
            </button>
          </div>

          {showUploader && (
            <div style={{ padding: "1rem", border: "1px dashed var(--border)", borderRadius: "8px", background: "var(--surface-subtle, rgba(0,0,0,0.02))", marginBottom: "1rem" }}>
              <p style={{ margin: "0 0 0.5rem 0", fontWeight: 500 }}>Upload a new resume PDF</p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                disabled={uploading}
                onChange={e => {
                  setUploadFile(e.target.files?.[0] || null);
                  setError("");
                }}
              />
              {uploading && (
                <div style={{ margin: "0.5rem 0" }}>
                  <p className="muted" style={{ margin: "0.25rem 0" }}>Uploading &amp; processing: {uploadProgress}%</p>
                  <div style={{ background: "var(--border)", borderRadius: "4px", height: "6px", width: "100%", overflow: "hidden" }}>
                    <div style={{ background: "var(--accent, #6366f1)", height: "100%", width: `${uploadProgress}%`, transition: "width 0.3s" }} />
                  </div>
                </div>
              )}
              <div className="row-actions" style={{ marginTop: "0.75rem" }}>
                <button className="secondary-button" type="button" disabled={!uploadFile || uploading} onClick={handleInlineUpload}>
                  {uploading ? "Processing…" : "Upload and Attach"}
                </button>
              </div>
            </div>
          )}

          {resumes.some(item => item.status === "uploaded" || item.status === "processing") && (
            <p className="muted">Resume processing is in progress. Analyze it after processing completes.</p>
          )}

          <div className="row-actions">
            <button
              className="secondary-button"
              type="button"
              disabled={busy || !resumeId || selectedResume?.status !== "completed"}
              onClick={analyze}
            >
              {busy ? "Analyzing…" : match ? "Analyze Resume again" : "Analyze Resume"}
            </button>
          </div>

          {!match && (
            <p className="muted">
              Analyze the selected resume against this job before applying. An ATS score of {ATS_MINIMUM}% or higher is required. Changing your resume or the job requirements requires a new analysis.
            </p>
          )}

          {match && <AtsDecision analysis={match} onViewResult={() => onNavigate(`analysis-result-${match.id}`)} />}

          {applicable && (
            <>
              <label>
                Cover letter
                <textarea
                  rows="7"
                  maxLength={10000}
                  value={coverLetter}
                  onChange={event => setCoverLetter(event.target.value)}
                  placeholder="Introduce yourself and explain your interest in this role."
                />
              </label>

              {questions.map((question, index) => {
                const key = String(question.id || question._id || question.question);
                return (
                  <label key={key}>
                    {question.question || `Question ${index + 1}`}
                    {question.required || question.is_required ? " *" : ""}
                    <textarea
                      required={Boolean(question.required || question.is_required)}
                      maxLength={2000}
                      rows="3"
                      value={answers[key] || ""}
                      onChange={event => setAnswers(current => ({ ...current, [key]: event.target.value }))}
                    />
                  </label>
                );
              })}

              <div className="row-actions">
                <button
                  className="primary-button"
                  disabled={!resumeId || busy || !applicable}
                  onClick={() => {
                    setError("");
                    setReview(true);
                  }}
                >
                  Review application →
                </button>
                <button className="text-button" onClick={() => onNavigate("resume")}>
                  Manage resumes
                </button>
              </div>
            </>
          )}
        </div>
      ) : applicable ? (
        <div className="dashboard-card application-review">
          <h2>Review before submitting</h2>
          <p><strong>Job:</strong> {job.title} · {job.company_name}</p>
          <p><strong>Resume:</strong> {selectedResume?.original_name}</p>
          <p><strong>Cover letter:</strong></p>
          <p className="review-text">{coverLetter || "No cover letter added."}</p>
          <p><strong>ATS score:</strong> {match.percentage}% (required {match.ats_minimum ?? ATS_MINIMUM}%)</p>
          {questions.map(question => {
            const key = String(question.id || question._id || question.question);
            return (
              <p key={key}>
                <strong>{question.question}</strong>
                <br />
                {answers[key] || "No answer"}
              </p>
            );
          })}
          <div className="row-actions">
            <button className="primary-button" disabled={busy || !applicable || !resumeId} onClick={submit}>
              {busy ? "Submitting…" : "Confirm and submit application"}
            </button>
            <button className="secondary-button" onClick={() => setReview(false)}>
              Edit application
            </button>
          </div>
        </div>
      ) : (
        <AtsDecision analysis={match} onViewResult={match ? () => onNavigate(`analysis-result-${match.id}`) : undefined} />
      )}
    </section>
  );
}


export function ApplicationDetailPage({ applicationId, onNavigate }) {
  const [item, setItem] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;

    api(`/api/applications/${applicationId}`)
      .then(data => {
        if (live) setItem(data);
      })
      .catch(err => {
        if (live) setError(err.message);
      });

    return () => {
      live = false;
    };
  }, [applicationId]);

  if (error) {
    return (
      <section className="dashboard-page">
        <div className="error-box">{error}</div>
        <button className="secondary-button" onClick={() => onNavigate("applications")}>
          Back to My Applications
        </button>
      </section>
    );
  }

  if (!item) {
    return (
      <section className="dashboard-page">
        <p className="loading">Loading application details…</p>
      </section>
    );
  }

  const history = [...(item.status_history || [])].sort(
    (a, b) =>
      new Date(a.at || a.created_at || 0) -
      new Date(b.at || b.created_at || 0)
  );

  const interview = item.interview;

  const screeningEntries = Object.entries(item.screening_answers || {});

  return (
    <section className="dashboard-page candidate-form-page">
      <button className="back-link" onClick={() => onNavigate("applications")}>
        ← Back to My Applications
      </button>

      {/* Header Overview Card */}
      <div className="app-detail-hero-card">
        <div className="app-detail-hero-info">
          <span className="eyebrow">Application Details</span>
          <h1>{item.job_title || item.job_snapshot?.title || "Application"}</h1>
          <div className="app-detail-hero-meta">
            <span><strong>{item.company_name || item.job_snapshot?.company_name || "Company"}</strong></span>
            <span>•</span>
            <span>Applied on {item.created_at ? new Date(item.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "—"}</span>
            {item.resume_name && (
              <>
                <span>•</span>
                <span>Resume: {item.resume_name}</span>
              </>
            )}
          </div>
        </div>
        <span className={`status-badge status-${item.status}`}>
          {label(item.status)}
        </span>
      </div>

      <div className="app-detail-layout">
        {/* 1. Job Information Card */}
        <section className="app-detail-card" aria-label="Job information">
          <div className="app-detail-card-header">
            <div>
              <span className="eyebrow">Position Overview</span>
              <h2>Job information</h2>
            </div>
            {item.job?.website && (
              <a
                href={item.job.website}
                target="_blank"
                rel="noreferrer"
                className="secondary-button small"
              >
                Company website ↗
              </a>
            )}
          </div>

          <div className="app-info-grid">
            <div className="app-info-item">
              <span className="app-info-label">Role Title</span>
              <span className="app-info-value">{item.job?.title || item.job_title || "Not specified"}</span>
            </div>
            <div className="app-info-item">
              <span className="app-info-label">Company</span>
              <span className="app-info-value">{item.company_name || item.job?.company_name || "Not specified"}</span>
            </div>
            <div className="app-info-item">
              <span className="app-info-label">Location</span>
              <span className="app-info-value">{item.job?.location || "Not specified"}</span>
            </div>
            <div className="app-info-item">
              <span className="app-info-label">Employment Type</span>
              <span className="app-info-value">{item.job?.job_type || "Not specified"}</span>
            </div>
            {item.job?.work_mode && (
              <div className="app-info-item">
                <span className="app-info-label">Work Mode</span>
                <span className="app-info-value">{item.job.work_mode}</span>
              </div>
            )}
            {item.job?.salary_range && (
              <div className="app-info-item">
                <span className="app-info-label">Salary Range</span>
                <span className="app-info-value">{item.job.salary_range}</span>
              </div>
            )}
          </div>

          {item.job?.description && (
            <div className="app-description-block">
              <span className="app-info-label">Job Description</span>
              <p className="app-description-content">{item.job.description}</p>
            </div>
          )}

          {item.job?.company_description && (
            <div className="app-description-block">
              <span className="app-info-label">About the Company</span>
              <p className="app-description-content">{item.job.company_description}</p>
            </div>
          )}
        </section>

        {/* 2. Submitted Materials Card */}
        <section className="app-detail-card" aria-label="Submitted materials">
          <div className="app-detail-card-header">
            <div>
              <span className="eyebrow">Application Attachments</span>
              <h2>Submitted materials</h2>
            </div>
          </div>

          <div className="app-material-row">
            <div className="resume-icon">PDF</div>
            <div className="app-material-meta">
              <strong>{item.resume_name || "Resume document"}</strong>
              <small className="muted">Attached to this application</small>
            </div>
            <span className="status-badge status-published">Verified PDF</span>
          </div>

          {screeningEntries.length > 0 && (
            <div className="app-description-block">
              <span className="app-info-label">Screening Questions & Answers</span>
              {screeningEntries.map(([question, answer]) => (
                <div className="app-screening-item" key={question}>
                  <strong>{question}</strong>
                  <p>{answer || "No response provided."}</p>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* 3. Cover Letter Card */}
        <section className="app-detail-card" aria-label="Cover letter">
          <div className="app-detail-card-header">
            <div>
              <span className="eyebrow">Candidate Statement</span>
              <h2>Cover letter</h2>
            </div>
          </div>

          <div className="app-cover-letter-box">
            <p className="review-text">
              {item.cover_letter || "No cover letter was submitted with this application."}
            </p>
          </div>
        </section>

        {/* 4. Interview Details Card (if scheduled) */}
        {interview && (
          <section
            className={`app-detail-card app-interview-card ${interview.status === "cancelled" || item.status === "rejected" ? "cancelled" : "active"}`}
            aria-label="Interview details"
          >
            <div className="app-detail-card-header">
              <div>
                <span
                  className="eyebrow"
                  style={interview.status === "cancelled" || item.status === "rejected" ? { color: "var(--error, #dc2626)" } : undefined}
                >
                  {interview.status === "cancelled" || item.status === "rejected"
                    ? "Interview Cancelled"
                    : "Recruiter Scheduled Interview"}
                </span>
                <h2>Interview details</h2>
              </div>
              <span
                className={`status-badge ${interview.status === "cancelled" || item.status === "rejected" ? "status-rejected" : "status-interview"}`}
              >
                {interview.status === "cancelled" || item.status === "rejected" ? "Cancelled" : "Scheduled"}
              </span>
            </div>

            {(interview.status === "cancelled" || item.status === "rejected") && (
              <div className="error-box">
                <strong>This interview has been cancelled</strong>
                <p style={{ margin: "0.25rem 0 0" }}>
                  {interview.cancellation_reason || "The scheduled interview was cancelled because the application status is Rejected."}
                  {interview.cancelled_at && ` (Cancelled on ${new Date(interview.cancelled_at).toLocaleDateString()})`}
                </p>
              </div>
            )}

            <div className="app-info-grid">
              <div className="app-info-item">
                <span className="app-info-label">Date</span>
                <span className="app-info-value">
                  {interview.scheduled_at
                    ? new Date(interview.scheduled_at).toLocaleDateString(undefined, {
                        weekday: "short",
                        day: "numeric",
                        month: "long",
                        year: "numeric",
                      })
                    : "Not provided"}
                </span>
              </div>
              <div className="app-info-item">
                <span className="app-info-label">Time</span>
                <span className="app-info-value">
                  {interview.scheduled_at
                    ? new Date(interview.scheduled_at).toLocaleTimeString(undefined, {
                        hour: "2-digit",
                        minute: "2-digit",
                        hour12: true,
                      })
                    : "Not provided"}
                </span>
              </div>
              <div className="app-info-item">
                <span className="app-info-label">Interview Type</span>
                <span className="app-info-value">
                  {interview.interview_type === "online"
                    ? "Online video call"
                    : interview.interview_type === "in_person"
                    ? "In person"
                    : "Not specified"}
                </span>
              </div>
              {interview.interview_type === "online" && interview.meeting_link && (
                <div className="app-info-item">
                  <span className="app-info-label">Meeting Link</span>
                  <a href={interview.meeting_link} target="_blank" rel="noreferrer" className="app-info-value">
                    Join online interview ↗
                  </a>
                </div>
              )}
              {interview.interview_type === "in_person" && interview.location && (
                <div className="app-info-item">
                  <span className="app-info-label">Meeting Location</span>
                  <span className="app-info-value">{interview.location}</span>
                </div>
              )}
            </div>

            {interview.instructions && (
              <div className="app-description-block">
                <span className="app-info-label">Special Instructions</span>
                <p className="app-description-content">{interview.instructions}</p>
              </div>
            )}
          </section>
        )}

        {/* 5. Status Card */}
        <section className="app-detail-card" aria-label="Application status">
          <div className="app-detail-card-header">
            <div>
              <span className="eyebrow">Hiring Progress</span>
              <h2>Current status</h2>
            </div>
            <span className={`status-badge status-${item.status}`}>
              {label(item.status)}
            </span>
          </div>

          <div className="app-status-overview">
            <div className="app-status-overview-info">
              <strong>Application Status: {label(item.status)}</strong>
              <small className="muted">
                {item.status === "submitted" || item.status === "applied"
                  ? "Your application has been received and is awaiting recruiter review."
                  : item.status === "under_review"
                  ? "A recruiter is currently reviewing your profile and submitted materials."
                  : item.status === "shortlisted"
                  ? "Congratulations! Your profile has been shortlisted for this role."
                  : item.status === "interview_scheduled" || item.status === "interview"
                  ? "An interview has been scheduled with the hiring team."
                  : item.status === "selected" || item.status === "accepted"
                  ? "Congratulations! You have received an offer / selection for this role."
                  : item.status === "rejected"
                  ? "Thank you for your interest. The hiring team has decided to proceed with other candidates."
                  : "Status updated."}
              </small>
            </div>
          </div>

          {item.resume_analysis_id && item.ai_match_score_snapshot != null && (
            <div className="app-match-score-card">
              <div className="app-match-score-badge">
                <span>ATS Resume Match Score:</span>
                <strong>{item.ai_match_score_snapshot}%</strong>
              </div>
              <button
                className="secondary-button small"
                type="button"
                onClick={() => onNavigate(`analysis-result-${item.resume_analysis_id}`)}
              >
                View full analysis report →
              </button>
            </div>
          )}
        </section>

        {/* 6. Status History Card */}
        <section className="app-detail-card" aria-label="Status history">
          <div className="app-detail-card-header">
            <div>
              <span className="eyebrow">Audit Timeline</span>
              <h2>Status history</h2>
            </div>
            <small className="muted">{history.length} update{history.length === 1 ? "" : "s"}</small>
          </div>

          {history.length > 0 ? (
            <ol className="application-status-history">
              {history.map((entry, index) => (
                <li key={`${entry.at || index}-${index}`}>
                  <span className="timeline-dot" />
                  <div>
                    <strong>{label(entry.new_status || entry.status)}</strong>
                    <p>
                      {entry.at || entry.created_at
                        ? new Date(entry.at || entry.created_at).toLocaleString(undefined, {
                            dateStyle: "medium",
                            timeStyle: "short",
                          })
                        : "Date unavailable"}
                      {entry.actor_role ? ` · Updated by ${entry.actor_role}` : ""}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted" style={{ margin: 0 }}>
              No status updates recorded yet.
            </p>
          )}
        </section>
      </div>
    </section>
  );
}
