import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { ATS_MINIMUM, meetsAtsMinimum } from "../../lib/ats";
import { ConfirmDialog, LoadingIndicator, StatusMessage } from "../../components/ui";

function ScoreBar({ label, score, weight }) {
  return <div className="analysis-component"><div className="analysis-component-heading"><strong>{label}</strong><span>{score == null ? "Not scored" : `${score}%`} · {weight}% weight</span></div>{score != null && <div className="progress-track" role="progressbar" aria-label={`${label} score`} aria-valuenow={score} aria-valuemin="0" aria-valuemax="100"><span style={{ width: `${score}%` }}/></div>}</div>;
}

function SkillGroup({ title, items, tone, empty }) {
  return (
    <section className="analysis-result-section">
      <h2>{title}</h2>
      {items?.length ? (
        <div className="tag-row">
          {items.map((skill, index) => {
            const text = typeof skill === "object" && skill !== null ? (skill.name || skill.skill || JSON.stringify(skill)) : String(skill);
            return (
              <span className={`analysis-skill ${tone}`} key={`${text}-${index}`}>
                {text}
              </span>
            );
          })}
        </div>
      ) : (
        <p className="muted">{empty}</p>
      )}
    </section>
  );
}

export function Analysis({ analysisId, onNavigate }) {
  const [history, setHistory] = useState(null); const [historyTotal, setHistoryTotal] = useState(0); const [result, setResult] = useState(null); const [loading, setLoading] = useState(true); const [error, setError] = useState(""); const [deleteTarget, setDeleteTarget] = useState(null); const [deleting, setDeleting] = useState(false);
  const loadHistory = useCallback(async () => {
    const data = await api("/api/resume-analysis/me?limit=50");
    setHistory(data.items || []); setHistoryTotal(data.total || 0);
  }, []);
  useEffect(() => {
    let active = true; setLoading(true); setError("");
    const request = analysisId ? api(`/api/resume-analysis/${analysisId}`).then(value => { if (active) setResult(value); }) : loadHistory();
    request.catch(err => { if (active) setError(err.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [analysisId, loadHistory]);

  async function deleteAnalysis() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api(`/api/resume-analysis/${deleteTarget.id}`, { method: "DELETE" });
      setHistory(current => current.filter(item => item.id !== deleteTarget.id)); setHistoryTotal(total => Math.max(0, total - 1)); setDeleteTarget(null); setError("");
    } catch (err) { setError(err.message); }
    finally { setDeleting(false); }
  }
  async function retryHistory() {
    setLoading(true); setError("");
    try { await loadHistory(); } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }

  if (loading) return <section className="dashboard-page"><LoadingIndicator label="Loading resume analysis…"/></section>;
  if (error && analysisId) return <section className="dashboard-page"><span className="eyebrow">Resume analysis</span><h1>Analysis <em>unavailable.</em></h1><StatusMessage>{error}</StatusMessage><button className="secondary-button" onClick={() => onNavigate("analysis")}>← Back to analysis history</button></section>;

  if (analysisId && result) {
    const preferred = result.preferred_skill_results || { matched: [], missing: [], available: false };
    const components = result.components || [];
    const experience = result.experience_comparison || {};
    const education = result.education_comparison || {};
    return <section className="dashboard-page candidate-form-page analysis-page">
      <button className="back-link" onClick={() => onNavigate("analysis")}>← Back to analysis history</button>
      <span className="eyebrow">Saved resume-to-job comparison</span><h1>{result.job_snapshot?.title || "Job analysis"}</h1><p className="muted page-intro">{[result.job_snapshot?.company_name, result.job_snapshot?.location, result.resume_name].filter(Boolean).join(" · ")}</p>
      <span className={`status-badge ${meetsAtsMinimum(result) ? "status-selected" : "status-rejected"}`}>{meetsAtsMinimum(result) ? "Applicable" : "Not Applicable"}</span><p className="muted">Current score: {result.percentage == null ? "not scored" : `${result.percentage}%`} · Required score: {result.ats_minimum ?? ATS_MINIMUM}%</p>
      <section className="analysis-score-card"><div className="analysis-score-value">{result.percentage == null ? "—" : `${result.percentage}%`}</div><div><h2>{result.percentage == null ? "Not enough job requirements to score" : "Requirement overlap"}</h2><p className="muted">{result.explanation}</p><p className="analysis-disclaimer">{result.disclaimer}</p></div></section>
      {result.percentage != null && <div className="progress-track analysis-overall-bar" role="progressbar" aria-label="Overall requirement overlap" aria-valuenow={result.percentage} aria-valuemin="0" aria-valuemax="100"><span style={{ width: `${result.percentage}%` }}/></div>}
      <section className="editor-block"><div className="section-heading"><div><span className="eyebrow">Transparent scoring</span><h2>Score breakdown</h2></div></div>{components.length ? components.map(item => <ScoreBar key={item.key} label={item.key.replaceAll("_", " ")} score={item.score} weight={item.weight}/>) : <p className="muted">The job did not list scorable requirements.</p>}{result.excluded_categories?.length > 0 && <p className="muted">Not included because the listing did not specify them: {result.excluded_categories.join(", ")}.</p>}</section>
      <div className="analysis-result-grid"><section className="editor-block"><SkillGroup title="Matched required skills" items={result.matched_skills} tone="good" empty="No required skills were confirmed in the extracted resume text."/><SkillGroup title="Missing required skills" items={result.missing_skills} tone="missing" empty="No required skills are missing."/></section>
        <section className="editor-block"><SkillGroup title="Preferred skills found" items={preferred.matched} tone="good" empty={preferred.available ? "No preferred skills were found in the resume." : "The job listing does not specify preferred skills."}/><SkillGroup title="Preferred skills not found" items={preferred.missing} tone="missing" empty={preferred.available ? "All listed preferred skills were found." : "No preferred skills were listed."}/></section></div>
      <div className="analysis-result-grid"><section className="editor-block"><span className="eyebrow">Experience comparison</span><h2>Experience</h2>{experience.available ? <><p><strong>Job requirement:</strong> {experience.requirement}</p><p><strong>Resume evidence:</strong> {experience.candidate_years_found == null ? "No explicit number of years was found." : `${experience.candidate_years_found} years mentioned`}</p><p className="muted">{experience.status === "meets" ? "The stated experience meets the listed minimum." : experience.status === "below" ? "The resume states less experience than the listed minimum." : "This comparison is limited to explicit evidence in the resume text."}</p></> : <p className="muted">No experience requirement was provided in the job listing.</p>}</section>
        <section className="editor-block"><span className="eyebrow">Education comparison</span><h2>Education</h2>{education.available ? <><p><strong>Job requirement:</strong> {education.requirements.join("; ")}</p><p><strong>Resume evidence:</strong> {education.evidence?.length ? education.evidence.join(" · ") : "No education section was extracted."}</p><p className="muted">{education.status === "meets" || education.status === "matches" ? "Matching education evidence was found." : education.status === "below" ? "The extracted degree level is below the listed requirement." : education.status === "field_mismatch" ? "The degree level is present, but the listed field of study was not found." : "No matching education evidence was found."}</p></> : <p className="muted">No education requirement was provided in the job listing.</p>}</section></div>
      <section className="editor-block"><span className="eyebrow">Next steps</span><h2>Suggestions</h2><ul className="analysis-suggestions">{result.improvement_suggestions?.map((suggestion, index) => <li key={`${index}-${suggestion}`}>{suggestion}</li>)}</ul></section>
      <div className="detail-actions"><button className="secondary-button" onClick={() => onNavigate("analysis")}>Analysis history</button><button className="primary-button" onClick={() => onNavigate(`job-${result.job_id}`)}>Back to job details →</button></div>
    </section>;
  }

  return <section className="dashboard-page candidate-form-page analysis-page"><div className="page-heading"><div><span className="eyebrow">Local rule-based matching</span><h1>Resume <em>analysis.</em></h1><p className="muted">{historyTotal} saved comparisons. Scores show resume evidence against the job listing; they are not hiring predictions.</p></div><button className="primary-button" onClick={() => onNavigate("jobs")}>Find a job to analyze →</button></div>
    <StatusMessage>{error}</StatusMessage>{history === null ? error ? <button className="secondary-button" onClick={retryHistory}>Try loading again</button> : <LoadingIndicator label="Loading analysis history…"/> : history.length ? <div className="analysis-history-list">{history.map(item => <article className="analysis-history-card" key={item.id}><div className="analysis-history-score">{item.percentage == null ? "—" : `${item.percentage}%`}</div><div className="row-main"><strong>{item.job_snapshot?.title || "Job analysis"}</strong><small>{[item.job_snapshot?.company_name, item.resume_name, item.created_at ? new Date(item.created_at).toLocaleString() : ""].filter(Boolean).join(" · ")}</small></div><span className={`status-badge ${meetsAtsMinimum(item) ? "status-selected" : "status-rejected"}`}>{meetsAtsMinimum(item) ? "Applicable" : "Not Applicable"}</span><button className="secondary-button" onClick={() => onNavigate(`analysis-result-${item.id}`)}>View result</button><button className="text-button danger-text" onClick={() => setDeleteTarget(item)}>Delete</button></article>)}</div> : <div className="empty-state compact-empty"><div className="empty-icon">◒</div><h3>No analyses saved yet</h3><p>Open any published job and choose Analyze Resume to compare it with a processed resume.</p><button className="secondary-button" onClick={() => onNavigate("jobs")}>Find jobs</button></div>}
    <ConfirmDialog open={Boolean(deleteTarget)} title="Delete this analysis?" message="This saved comparison will be permanently removed from your history." confirmLabel="Delete analysis" busy={deleting} onCancel={() => setDeleteTarget(null)} onConfirm={deleteAnalysis}/>
  </section>;
}

export default Analysis;
