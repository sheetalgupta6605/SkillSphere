import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { EmptyState } from "../../components/Layout";

export function RecentlyViewed({ onNavigate }) {
  const [jobs, setJobs] = useState(null); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function load() { setError(""); try { setJobs(await api("/api/jobs/recently-viewed/me")); } catch (err) { setError(err.message); setJobs([]); } }
  useEffect(() => { load(); }, []);
  async function clearHistory() { setBusy(true); setError(""); try { await api("/api/jobs/recently-viewed/me", { method: "DELETE" }); setJobs([]); } catch (err) { setError(err.message); } finally { setBusy(false); } }
  return <section className="dashboard-page"><div className="page-heading"><div><span className="eyebrow">Your browsing</span><h1>Recently viewed jobs</h1><p className="muted">Job views are saved to your account for quick access.</p></div>{jobs?.length > 0 && <button className="secondary-button" onClick={clearHistory} disabled={busy}>{busy ? "Clearing…" : "Clear history"}</button>}</div>{error && <div className="error-box">{error}</div>}{jobs === null ? <p className="loading">Loading recently viewed jobs…</p> : jobs.length ? <div className="data-list">{jobs.map(job => <div className="data-row recent-job-row" key={job.id}><span className="row-avatar">{(job.company_name || "J")[0]}</span><span className="row-main"><strong>{job.title}</strong><small>{job.company_name || "Company"} · {job.location || "Location not specified"} · {job.job_type || "Job"}</small></span><button className="secondary-button" onClick={() => onNavigate(`job-${job.id}`)}>View job →</button></div>)}</div> : <EmptyState title="No jobs viewed yet" text="Open a job listing and it will appear here for quick access." action="Find jobs" onAction={() => onNavigate("jobs")}/>}</section>;
}
