import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { EmptyState } from "../../components/Layout";

export function JobMatcher({ onNavigate }) {
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState("");
  const [hasResume, setHasResume] = useState(false);
  useEffect(() => {
    let active = true;
    Promise.all([api("/api/jobs?limit=30&sort=newest"), api("/api/resumes")]).then(([result, resumes]) => { if (active) { setJobs(result.items || []); setHasResume(resumes.some(item => item.status === "completed")); } }).catch(err => { if (active) { setError(err.message); setJobs([]); } });
    return () => { active = false; };
  }, []);
  return <section className="dashboard-page candidate-form-page">
    <span className="eyebrow">Job matching</span><h1>AI Job <em>Matcher.</em></h1>
    <div className="notice-box" role="status"><strong>AI matching is not configured.</strong><p>No model/API provider is configured in this project, so this page will not invent AI match scores. The existing resume analyzer provides transparent requirement comparisons and saved results.</p>{hasResume ? <button className="secondary-button" onClick={() => onNavigate("analysis")}>Open resume analysis history</button> : <button className="primary-button" onClick={() => onNavigate("resume")}>Upload a resume</button>}</div>
    <div className="page-heading"><div><h2>Published opportunities</h2><p className="muted">These are real active jobs from the job listings API.</p></div><button className="text-button" onClick={() => onNavigate("jobs")}>Search all jobs →</button></div>
    {error && <div className="error-box" role="alert">{error}</div>}{jobs === null ? <p className="loading">Loading published jobs…</p> : jobs.length ? <div className="job-grid">{jobs.map(job => <article className="job-card" key={job.id}><span className="eyebrow">{job.company_name || "Company"}</span><h3>{job.title}</h3><p className="muted">{[job.location, job.work_mode, job.job_type, job.experience_range].filter(Boolean).join(" · ")}</p><div className="job-card-bottom"><button className="secondary-button" onClick={() => onNavigate(`job-${job.id}`)}>View details & analysis</button></div></article>)}</div> : <EmptyState title="No published jobs yet" text="New opportunities will appear here after recruiters publish them." action="Refresh jobs" onAction={() => { setJobs(null); api("/api/jobs?limit=30&sort=newest").then(result => setJobs(result.items || [])).catch(err => { setError(err.message); setJobs([]); }); }}/>}</section>;
}
