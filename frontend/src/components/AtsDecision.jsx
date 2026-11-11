import { ATS_MINIMUM, meetsAtsMinimum, rejectionReason } from "../lib/ats";

export function AtsDecision({ analysis, onViewResult, onApply }) {
  if (!analysis) return null;
  const minimum = analysis.ats_minimum ?? ATS_MINIMUM;
  const applicable = meetsAtsMinimum(analysis);
  const score = analysis.percentage == null ? "Not scored" : `${analysis.percentage}%`;
  const suggestions = analysis.improvement_suggestions || [];

  return (
    <section
      className={`ats-decision ${applicable ? "ats-applicable" : "ats-blocked"}`}
      aria-live="polite"
    >
      <div className="ats-decision-header">
        <span
          className={`status-badge ${
            applicable
              ? "status-selected ats-status-applicable"
              : "status-rejected ats-status-not-applicable"
          }`}
        >
          {applicable ? "Applicable" : "Not Applicable"}
        </span>
      </div>

      <p>
        <strong>Current ATS score:</strong> {score}
      </p>
      <p>
        <strong>Required score:</strong> {minimum}%
      </p>

      {!applicable && (
        <>
          <p className="ats-rejection-reason">
            <strong>Reason:</strong> {rejectionReason(analysis)}
          </p>
          <h3>Improvement suggestions</h3>
          {suggestions.length ? (
            <ul className="analysis-suggestions">
              {suggestions.map((suggestion, index) => {
                const text = typeof suggestion === "object" && suggestion !== null
                  ? (suggestion.text || suggestion.suggestion || suggestion.message || JSON.stringify(suggestion))
                  : String(suggestion);
                return <li key={`${index}-${text}`}>{text}</li>;
              })}
            </ul>
          ) : (
            <p className="muted">
              Update your resume with evidence that matches this job’s listed
              requirements, then analyze it again.
            </p>
          )}
        </>
      )}

      <div className="detail-actions ats-decision-actions" style={{ marginTop: "14px" }}>
        {applicable && onApply && (
          <button className="primary-button" type="button" onClick={onApply}>
            Apply Now
          </button>
        )}
        {onViewResult && (
          <button className="secondary-button" type="button" onClick={onViewResult}>
            View result
          </button>
        )}
      </div>
    </section>
  );
}
