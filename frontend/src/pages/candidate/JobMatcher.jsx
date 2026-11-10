// import { useEffect, useState } from "react";
// import { api } from "../../lib/api";
// import { EmptyState } from "../../components/Layout";

// export function JobMatcher({ onNavigate }) {
//   const [jobs, setJobs] = useState(null);
//   const [error, setError] = useState("");
//   const [hasResume, setHasResume] = useState(false);
//   useEffect(() => {
//     let active = true;
//     Promise.all([api("/api/jobs?limit=30&sort=newest"), api("/api/resumes")]).then(([result, resumes]) => { if (active) { setJobs(result.items || []); setHasResume(resumes.some(item => item.status === "completed")); } }).catch(err => { if (active) { setError(err.message); setJobs([]); } });
//     return () => { active = false; };
//   }, []);
//   return <section className="dashboard-page candidate-form-page">
//     <span className="eyebrow">Job matching</span><h1>AI Job <em>Matcher.</em></h1>
//     <div className="notice-box" role="status"><strong>AI matching is not configured.</strong><p>No model/API provider is configured in this project, so this page will not invent AI match scores. The existing resume analyzer provides transparent requirement comparisons and saved results.</p>{hasResume ? <button className="secondary-button" onClick={() => onNavigate("analysis")}>Open resume analysis history</button> : <button className="primary-button" onClick={() => onNavigate("resume")}>Upload a resume</button>}</div>
//     <div className="page-heading"><div><h2>Published opportunities</h2><p className="muted">These are real active jobs from the job listings API.</p></div><button className="text-button" onClick={() => onNavigate("jobs")}>Search all jobs →</button></div>
//     {error && <div className="error-box" role="alert">{error}</div>}{jobs === null ? <p className="loading">Loading published jobs…</p> : jobs.length ? <div className="job-grid">{jobs.map(job => <article className="job-card" key={job.id || job._id}><span className="eyebrow">{job.company_name || "Company"}</span><h3>{job.title}</h3><p className="muted">{[job.location, job.work_mode, job.job_type, job.experience_range].filter(Boolean).join(" · ")}</p><div className="job-card-bottom"><button className="secondary-button"
// onClick={() => onNavigate(`job-${job.id || job._id}`)}
//      >View details & analysis</button></div></article>)}</div> : <EmptyState title="No published jobs yet" text="New opportunities will appear here after recruiters publish them." action="Refresh jobs" onAction={() => { setJobs(null); api("/api/jobs?limit=30&sort=newest").then(result => setJobs(result.items || [])).catch(err => { setError(err.message); setJobs([]); }); }}/>}</section>;
// }



import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { EmptyState } from "../../components/Layout";

export function JobMatcher({ onNavigate }) {
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState("");

  async function loadMatches() {
    setJobs(null);
    setError("");

    try {
      const result = await api("/api/matching/job-matches");
      setJobs(result.items || []);
    } catch (err) {
      setError(err.message || "Unable to load AI job matches.");
      setJobs([]);
    }
  }

  useEffect(() => {
    loadMatches();
  }, []);

  return (
    <section className="dashboard-page candidate-form-page">
      <span className="eyebrow">AI-powered job matching</span>

      <h1>AI Job <em>Matcher.</em></h1>

      <p className="muted">
        Discover job opportunities that match your resume using Google Gemini AI.
      </p>

      {error && (
        <div className="error-box" role="alert">
          <strong>Unable to generate job matches.</strong>
          <p>{error}</p>

          <button className="secondary-button" onClick={loadMatches}>
            Try again
          </button>

          <button
            className="text-button"
            onClick={() => onNavigate("resume")}
          >
            Open my resume
          </button>
        </div>
      )}

      <div className="page-heading">
        <div>
          <h2>Your AI job matches</h2>
          <p className="muted">
            Published opportunities ranked according to your resume.
          </p>
        </div>

        <button
  className="secondary-button"
  onClick={loadMatches}
  disabled={jobs === null}
>
  Refresh matches
</button>
      </div>

      {jobs === null ? (
        <p className="loading">Gemini is analyzing your resume...</p>
      ) : jobs.length > 0 ? (
        <div className="job-grid">
          {jobs.map((job) => (
            <article className="job-card" key={job.id}>
              <span className="eyebrow">
                {job.company_name || "Company"}
              </span>

              <h3>{job.title}</h3>

              <p className="muted">
                {[
                  job.location,
                  job.work_mode,
                  job.job_type,
                  job.experience_range
                ].filter(Boolean).join(" · ")}
              </p>

              <div className="match-score">
                <strong>{job.percentage}% Match</strong>
              </div>

              <p>{job.summary}</p>

              <div>
                <strong>Matched skills</strong>
                <p>
                  {job.matched_skills?.join(", ") || "No matching skills found"}
                </p>
              </div>

              <div>
                <strong>Missing skills</strong>
                <p>
                  {job.missing_skills?.join(", ") || "No specific gaps identified"}
                </p>
              </div>

              <div>
                <strong>Improvement suggestions</strong>
                <ul>
                  {(job.improvements || []).map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              </div>

              <div className="job-card-bottom">
                <button
                  className="secondary-button"
                  onClick={() => onNavigate(`job-${job.id}`)}
                >
                  View job details
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        !error && (
          <EmptyState
            title="No job matches found"
            text="No matching published opportunities were returned. Try refreshing later."
            action="Refresh matches"
            onAction={loadMatches}
          />
        )
      )}

      <p className="muted">
        AI match scores are estimates based on resume evidence, not hiring guarantees.
      </p>
    </section>
  );
}
