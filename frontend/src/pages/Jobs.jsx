import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigationType, useSearchParams } from "react-router-dom";
import { API_URL, api } from "../lib/api";
import { ATS_MINIMUM, analysisIsCurrent, latestCurrentAnalysis, meetsAtsMinimum, rememberApplicationContext } from "../lib/ats";
import { AtsDecision } from "../components/AtsDecision";
import { EmptyState } from "../components/Layout";
import { LoadingIndicator, Pagination, SearchInput, StatusMessage } from "../components/ui";

const LOCATION_OPTIONS = ["Remote", "New Delhi", "Mumbai", "Bengaluru", "Hyderabad", "Pune", "Chennai", "Kolkata", "Gurugram", "Noida"];
const SKILL_OPTIONS = ["Python", "JavaScript", "React", "Node.js", "FastAPI", "Java", "SQL", "MongoDB", "Figma", "Product Design"];
const FILTER_KEY = "skillsphere_job_filters";
const LAST_SEARCH_KEY = "skillsphere_last_job_search_url";
const DEFAULT_FILTERS = { keyword: "", location: "", company: "", jobType: "", workMode: "", experience: "", skills: "", salaryMin: "", postedDays: "", sort: "newest" };
const FILTER_PARAMS = { keyword: "keyword", location: "location", company: "company", jobType: "job_type", workMode: "work_mode", experience: "experience", skills: "skills", salaryMin: "salary_min", postedDays: "posted_days", sort: "sort" };

function readFilters() {
  try { return { ...DEFAULT_FILTERS, ...JSON.parse(sessionStorage.getItem(FILTER_KEY) || "{}") }; }
  catch { return DEFAULT_FILTERS; }
}
function filtersFromUrl(params, fallback = DEFAULT_FILTERS) {
  return Object.fromEntries(Object.entries(FILTER_PARAMS).map(([key, param]) => [key, params.get(param) ?? fallback[key]]));
}
function dateLabel(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}
function workModeLabel(job) {
  return job.work_mode || (["remote", "hybrid", "on-site", "onsite"].includes(String(job.job_type || "").toLowerCase()) ? job.job_type : "");
}
function jobLogo(job, className = "company-dot") {
  const logo = job.company_logo || job.logo_url;
  const src = logo?.startsWith("/") ? `${API_URL}${logo}` : logo;
  return src ? <img className={`${className} company-logo`} src={src} alt={`${job.company_name || "Company"} logo`} onError={event => { event.currentTarget.style.display = "none"; }}/> : <span className={className}>{job.company_name?.trim()?.[0] || ""}</span>;
}

export function Jobs({ user, onNavigate }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigationType = useNavigationType();
  const firstLocation = useRef(true);
  const pushPage = useRef(false);
  const [result, setResult] = useState({ items: [], pages: 0, page: 1, total: 0 });
  const [filters, setFilters] = useState(() => {
    const current = new URLSearchParams(window.location.search);
    const previous = new URLSearchParams(sessionStorage.getItem(LAST_SEARCH_KEY) || "");
    return filtersFromUrl(current.size ? current : previous, readFilters());
  });
  const [page, setPage] = useState(() => Math.max(1, Number(searchParams.get("page") || new URLSearchParams(sessionStorage.getItem(LAST_SEARCH_KEY) || "").get("page")) || 1));
  const [loading, setLoading] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [savedIds, setSavedIds] = useState(() => new Set());

  useEffect(() => { sessionStorage.setItem(FILTER_KEY, JSON.stringify(filters)); }, [filters]);
  useEffect(() => {
    if (user?.role === "candidate") api("/api/jobs/saved/me").then(items => setSavedIds(new Set(items.filter(item => item.is_available !== false).map(item => item.id)))).catch(() => {});
    else setSavedIds(new Set());
  }, [user]);

  async function load(pageNumber = 1, replaceHistory = true) {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(pageNumber), limit: "12", sort: filters.sort });
      for (const [key, param] of Object.entries(FILTER_PARAMS)) if (filters[key]) params.set(param, filters[key]);
      setSearchParams(params, { replace: replaceHistory });
      const response = await api(`/api/jobs?${params}`);
      setResult(response); setPage(response.page); setError("");
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }
  useEffect(() => {
    const timer = window.setTimeout(() => { const replaceHistory = !pushPage.current; pushPage.current = false; load(page, replaceHistory); }, 280);
    return () => window.clearTimeout(timer);
  }, [filters, page]);
  useEffect(() => {
    if (firstLocation.current) { firstLocation.current = false; return; }
    if (navigationType !== "POP") return;
    const params = new URLSearchParams(location.search);
    setFilters(filtersFromUrl(params)); setPage(Math.max(1, Number(params.get("page")) || 1));
  }, [location.key, navigationType]);

  function update(key, value) { setFilters(current => ({ ...current, [key]: value })); setPage(1); }
  function clearFilters() { setFilters(DEFAULT_FILTERS); setPage(1); }
  async function toggleSave(jobId) {
    if (!user) return onNavigate("login");
    if (user.role !== "candidate") { setError("Only candidates can save jobs."); return; }
    const isSaved = savedIds.has(jobId);
    try {
      await api(`/api/jobs/${jobId}/save`, { method: isSaved ? "DELETE" : "POST" });
      setSavedIds(current => { const next = new Set(current); isSaved ? next.delete(jobId) : next.add(jobId); return next; });
      setNotice(isSaved ? "Job removed from Saved Jobs." : "Job saved to your list."); setError("");
    } catch (err) { setError(err.message); setNotice(""); }
  }
  function openJob(jobId) {
    sessionStorage.setItem(LAST_SEARCH_KEY, window.location.search);
    onNavigate(`job-${jobId}`);
  }

  return <section className="jobs-page">
    <div className="page-heading"><div><span className="eyebrow">Explore opportunities</span><h1>{user?.role === "candidate" ? "Find Your Next Opportunity" : <>Find work that <em>fits.</em></>}</h1><p className="muted">{user?.role === "candidate" ? "Explore opportunities that match your skills, interests and career goals." : loading ? "Searching live jobs…" : `${result.total} matching ${result.total === 1 ? "opportunity" : "opportunities"}`}</p>{user?.role === "candidate" && <p className="muted">{loading ? "Loading published jobs…" : `${result.total} ${result.total === 1 ? "job" : "jobs"} available`}</p>}</div><SearchInput value={filters.keyword} onChange={value => update("keyword", value)} label="Search jobs, skills, or companies" placeholder="Title, skills, company, keywords"/></div>
    <button type="button" className="secondary-button filter-drawer-toggle" aria-expanded={filtersOpen} onClick={() => setFiltersOpen(open => !open)}>{filtersOpen ? "Hide filters" : "Filters"}</button>
    <div className={`filters ${filtersOpen ? "filters-open" : ""}`} aria-label="Job filters">
      <label className="filter-field"><span>Location</span><input list="location-options" placeholder="Choose or type a location" value={filters.location} onChange={event => update("location", event.target.value)}/><datalist id="location-options">{LOCATION_OPTIONS.map(option => <option value={option} key={option}/>)}</datalist></label>
      <label className="filter-field"><span>Company</span><input value={filters.company} onChange={event => update("company", event.target.value)} placeholder="Company name"/></label>
      <label className="filter-field"><span>Employment type</span><select value={filters.jobType} onChange={event => update("jobType", event.target.value)}><option value="">All types</option><option value="full-time">Full time</option><option value="part-time">Part time</option><option value="internship">Internship</option><option value="contract">Contract</option></select></label>
      <label className="filter-field"><span>Work mode</span><select value={filters.workMode} onChange={event => update("workMode", event.target.value)}><option value="">Any work mode</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="on-site">On-site</option></select></label>
      <label className="filter-field"><span>Experience</span><input placeholder="e.g. 2 years" value={filters.experience} onChange={event => update("experience", event.target.value)}/></label>
      <label className="filter-field"><span>Skills (comma separated)</span><input list="skill-options" placeholder="React, Python" value={filters.skills} onChange={event => update("skills", event.target.value)}/><datalist id="skill-options">{SKILL_OPTIONS.map(option => <option value={option} key={option}/>)}</datalist></label>
      <label className="filter-field"><span>Minimum salary</span><input type="number" min="0" step="1000" placeholder="Annual amount" value={filters.salaryMin} onChange={event => update("salaryMin", event.target.value)}/></label>
      <label className="filter-field"><span>Date posted</span><select value={filters.postedDays} onChange={event => update("postedDays", event.target.value)}><option value="">Any time</option><option value="1">Past 24 hours</option><option value="7">Past week</option><option value="30">Past month</option><option value="90">Past 3 months</option></select></label>
      <label className="filter-field"><span>Sort by</span><select value={filters.sort} onChange={event => update("sort", event.target.value)}><option value="newest">Newest</option><option value="salary">Highest salary</option><option value="relevance">Relevance</option></select></label>
      <div className="job-filter-actions"><button type="button" className="primary-button" onClick={() => { setPage(1); load(1, true); }}>Search jobs</button>{Object.entries(filters).some(([key, value]) => key !== "sort" && value) && <button type="button" className="text-button clear-filters" onClick={clearFilters}>Clear all</button>}</div>
    </div>
    <StatusMessage>{error}</StatusMessage><StatusMessage tone="success">{notice}</StatusMessage>
    {loading ? <LoadingIndicator label="Loading published jobs…"/> : error && !result.items.length ? <div className="job-load-error" role="alert"><p>{error}</p><button className="secondary-button" onClick={() => load(page, true)}>Try again</button></div> : result.items.length ? <><div className="job-grid">{result.items.map(job => <article className="job-card" key={job.id}>
      <div className="job-card-top">{jobLogo(job)}<span className="job-type">{job.job_type}</span></div>
      <h3>{job.title}</h3>{job.company_name && <p className="job-company-name">{job.company_name}</p>}<p className="muted">{[job.location, workModeLabel(job), job.experience_range].filter(Boolean).join(" · ")}</p>
      {(job.required_skills || []).length > 0 && <div className="tag-row">{job.required_skills.slice(0, 4).map(skill => <span key={skill}>{skill}</span>)}</div>}
      <div className="job-card-meta">{job.salary_range && <span>{job.salary_range}</span>}{job.created_at && <span>Posted {dateLabel(job.created_at)}</span>}{job.application_deadline && <span>Apply by {dateLabel(job.application_deadline)}</span>}</div>
      <div className="job-card-bottom"><button className="text-button" onClick={() => toggleSave(job.id)}>{savedIds.has(job.id) ? "♥ Saved" : "♡ Save"}</button><button className="secondary-button" onClick={() => openJob(job.id)}>View details →</button></div>
    </article>)}</div><Pagination page={page} pageCount={result.pages} onChange={nextPage => { pushPage.current = true; setPage(nextPage); }}/></> : user?.role === "candidate" && !Object.entries(filters).some(([key, value]) => key !== "sort" && value) ? <div className="empty-state"><div className="empty-icon">✦</div><h2>No jobs available right now.</h2><p>New opportunities will appear here when recruiters publish jobs.</p><div className="hero-actions"><button className="primary-button" onClick={() => load(1, true)}>Refresh jobs</button><button className="secondary-button" onClick={() => onNavigate("resume")}>Review your resume</button><button className="text-button" onClick={() => onNavigate("profile")}>Explore your profile</button></div></div> : <EmptyState title="No matching jobs" text="Adjust your search or clear some filters to see more results." action="Clear filters" onAction={clearFilters}/>}
  </section>;
}

export function JobDetail({ jobId, user, onNavigate }) {
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [resumes, setResumes] = useState([]);
  const [resumeId, setResumeId] = useState("");
  const [currentAnalysis, setCurrentAnalysis] = useState(null);
  const [alreadyApplied, setAlreadyApplied] = useState(false);

  useEffect(() => {
    let active = true;
    setJob(null);
    setLoading(true);
    setError("");
    setNotice("");
    setCurrentAnalysis(null);
    setAlreadyApplied(false);

    api(`/api/jobs/${jobId}`)
      .then(value => { if (active) setJob(value); })
      .catch(err => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });

    if (user?.role === "candidate") {
      api(`/api/jobs/${jobId}/view`, { method: "POST" }).catch(() => {});
      api("/api/jobs/saved/me")
        .then(items => {
          if (active) setSaved(items.some(item => item.id === jobId && item.is_available !== false));
        })
        .catch(() => {});
      api("/api/applications/me")
        .then(apps => {
          if (active && Array.isArray(apps)) {
            setAlreadyApplied(apps.some(item => (item.job_id === jobId || item.job?.id === jobId) && item.status !== "withdrawn"));
          }
        })
        .catch(() => {});
      api("/api/resumes")
        .then(resumeList => {
          if (!active) return;
          const items = resumeList || [];
          setResumes(items);
          setResumeId(current => (current && items.some(item => item.id === current)) ? current : (items.find(item => item.status === "completed")?.id || ""));
        })
        .catch(() => {});
    } else {
      setResumes([]);
      setResumeId("");
    }

    return () => { active = false; };
  }, [jobId, user]);

  async function toggleSave() {
    if (!user) return onNavigate("login");
    if (user.role !== "candidate") { setError("Only candidates can save jobs."); return; }
    setSaving(true);
    try {
      await api(`/api/jobs/${job.id}/save`, { method: saved ? "DELETE" : "POST" });
      setSaved(value => !value);
      setNotice(saved ? "Job removed from Saved Jobs." : "Job saved to your list.");
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const completedResumes = resumes.filter(item => item.status === "completed");
  const selectedResume = completedResumes.find(item => item.id === resumeId);
  const isCurrent = currentAnalysis && selectedResume && job && analysisIsCurrent(currentAnalysis, selectedResume, job);
  const activeAnalysis = isCurrent ? currentAnalysis : null;
  const applicable = Boolean(activeAnalysis && meetsAtsMinimum(activeAnalysis));

  async function analyzeResume() {
    if (!user) return onNavigate("login");
    if (user.role !== "candidate") { setError("Resume analysis is available to candidates."); return; }
    if (!selectedResume) { setError("Select a processed resume before analyzing this job."); return; }
    setAnalyzing(true);
    setError("");
    setNotice("");
    try {
      const analysis = await api(`/api/resume-analysis/analyze/${job.id}`, {
        method: "POST",
        body: JSON.stringify({ resume_id: selectedResume.id }),
      });
      setCurrentAnalysis(analysis);
      setNotice("This comparison was saved to your analysis history.");
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  }

  function applyNow() {
    if (!applicable || !activeAnalysis) return;
    rememberApplicationContext(job.id, activeAnalysis.resume_id, activeAnalysis.id);
    onNavigate(`apply-${job.id}`);
  }

  if (loading) return <section className="simple-page job-detail"><LoadingIndicator label="Loading job details…"/></section>;
  if (!job) return <section className="simple-page job-detail"><StatusMessage>{error || "This job is unavailable or no longer accepting applications."}</StatusMessage><button className="secondary-button" onClick={() => onNavigate("jobs")}>← Back to job search</button></section>;

  return <section className="simple-page job-detail">
    <button className="back-link" onClick={() => onNavigate("jobs")}>← Back to job search</button>
    <div className="job-detail-hero"><div><span className="eyebrow">{[job.company_name, job.company_location, job.location].filter(Boolean).join(" · ")}</span><h1>{job.title}</h1><p className="muted">{[job.job_type, workModeLabel(job), job.experience_range, job.salary_range].filter(Boolean).join(" · ")}</p></div>{jobLogo(job, "company-dot job-detail-logo")}</div>

    {user?.role === "candidate" && (
      <label className="filter-field ats-resume-picker">
        <span>Select resume to analyze</span>
        <select
          value={resumeId}
          onChange={event => {
            setResumeId(event.target.value);
            setCurrentAnalysis(null);
            setNotice("");
            setError("");
          }}
          disabled={!completedResumes.length}
        >
          <option value="">Select a processed resume</option>
          {completedResumes.map(item => <option value={item.id} key={item.id}>{item.original_name}</option>)}
        </select>
      </label>
    )}

    {user?.role === "candidate" && !completedResumes.length && (
      <p className="muted">Upload a resume and wait for processing before this job can be analyzed.</p>
    )}

    <div className="detail-actions">
      <button className="secondary-button" onClick={toggleSave} disabled={saving}>
        {saving ? "Saving…" : saved ? "♥ Saved · Remove" : "♡ Save job"}
      </button>

      {user?.role === "recruiter" ? (
        <button className="primary-button" disabled>Candidate applications only</button>
      ) : alreadyApplied ? (
        <button className="secondary-button" onClick={() => onNavigate("applications")}>
          ✓ Already Applied · View applications
        </button>
      ) : (
        <>
          <button
            className={applicable ? "secondary-button" : "primary-button"}
            onClick={analyzeResume}
            disabled={analyzing || (user?.role === "candidate" && !selectedResume)}
          >
            {analyzing
              ? "Analyzing resume…"
              : activeAnalysis
              ? "Analyze Resume again"
              : "Analyze Resume"}
          </button>
          {applicable && (
            <button className="primary-button" onClick={applyNow}>
              Apply Now
            </button>
          )}
        </>
      )}
    </div>

    {user?.role === "candidate" && !activeAnalysis && !alreadyApplied && (
      <p className="muted">
        Analyze your selected resume against this job before applying. An ATS score of {ATS_MINIMUM}% or higher is required.
      </p>
    )}

    {activeAnalysis && (
      <AtsDecision
        analysis={activeAnalysis}
        onApply={applicable && !alreadyApplied ? applyNow : undefined}
        onViewResult={() => onNavigate(`analysis-result-${activeAnalysis.id}`)}
      />
    )}

    {(error.toLowerCase().includes("resume") || (user?.role === "candidate" && !completedResumes.length)) && (
      <button className="text-button" onClick={() => onNavigate("resume")}>
        Review or upload a resume →
      </button>
    )}

    <StatusMessage>{error}</StatusMessage>
    <StatusMessage tone="success">{notice}</StatusMessage>

    <div className="detail-body job-detail-grid">
      <main>
        <h2>About the role</h2>
        {job.description && <p>{job.description}</p>}
        {job.responsibilities?.length > 0 && <><h2>Responsibilities</h2><ul>{job.responsibilities.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul></>}
        {job.requirements?.length > 0 && <><h2>Qualifications</h2><ul>{job.requirements.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul></>}
        {job.required_skills?.length > 0 && <><h2>Required skills</h2><div className="tag-row">{job.required_skills.map(skill => <span key={skill}>{skill}</span>)}</div></>}
        {job.preferred_skills?.length > 0 && <><h2>Preferred skills</h2><div className="tag-row">{job.preferred_skills.map(skill => <span key={skill}>{skill}</span>)}</div></>}
      </main>
      <aside className="company-info-card">
        <span className="eyebrow">Company</span>
        {job.company_logo && <img className="company-detail-logo" src={job.company_logo.startsWith("/") ? `${API_URL}${job.company_logo}` : job.company_logo} alt={`${job.company_name || "Company"} logo`} />}
        {job.company_name && <h2>{job.company_name}</h2>}
        {job.industry && <p className="muted">{job.industry}</p>}
        {job.company_description && <p>{job.company_description}</p>}
        {job.company_location && <p>{job.company_location}</p>}
        {job.website && <a href={job.website} target="_blank" rel="noreferrer">Company website ↗</a>}
        {(job.number_of_openings ?? job.openings) != null && <p><strong>Openings:</strong> {job.number_of_openings ?? job.openings}</p>}
        {job.created_at && <p><strong>Posted:</strong> {dateLabel(job.created_at)}</p>}
        {job.application_deadline && <p><strong>Apply by:</strong> {dateLabel(job.application_deadline)}</p>}
      </aside>
    </div>
  </section>;
}

export default Jobs;
