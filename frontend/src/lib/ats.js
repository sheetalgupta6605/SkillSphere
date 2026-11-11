export const ATS_MINIMUM = 70;

export function versionKey(value) {
  if (value == null || value === "") return "";
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? String(value) : String(time);
}

export function meetsAtsMinimum(analysis) {
  if (!analysis) return false;
  if (typeof analysis.meets_ats_minimum === "boolean") return analysis.meets_ats_minimum;
  const minimum = analysis.ats_minimum ?? ATS_MINIMUM;
  return typeof analysis.percentage === "number" && analysis.percentage >= minimum;
}

export function analysisIsCurrent(analysis, resume, job) {
  if (!analysis || !resume || !job) return false;
  if (analysis.resume_id !== resume.id || analysis.job_id !== job.id) return false;
  const resumeVersion = resume.ocr_corrected_at || resume.processed_at;
  const jobVersion = job.updated_at || job.created_at;
  if (!resumeVersion || !jobVersion || analysis.resume_version == null || analysis.job_version == null) return false;
  return versionKey(analysis.resume_version) === versionKey(resumeVersion) && versionKey(analysis.job_version) === versionKey(jobVersion);
}

export function latestCurrentAnalysis(analyses, resume, job) {
  return (analyses || [])
    .filter(item => analysisIsCurrent(item, resume, job))
    .sort((left, right) => new Date(right.created_at || 0) - new Date(left.created_at || 0))[0] || null;
}

export function rejectionReason(analysis) {
  const minimum = analysis?.ats_minimum ?? ATS_MINIMUM;
  if (analysis?.percentage == null) {
    return `This comparison did not produce an ATS score, so it does not meet the ${minimum}% required to apply.`;
  }
  const missing = analysis.missing_skills?.length ? ` Missing required skills: ${analysis.missing_skills.join(", ")}.` : "";
  const explanation = analysis.explanation ? ` ${analysis.explanation}` : "";
  return `Your ATS score is ${analysis.percentage}%, which is below the ${minimum}% required to apply.${missing}${explanation}`;
}

export function rememberApplicationContext(jobId, resumeId, analysisId) {
  sessionStorage.setItem(`skillsphere_apply_${jobId}`, JSON.stringify({ resumeId, analysisId }));
}

export function readApplicationContext(jobId) {
  try {
    return JSON.parse(sessionStorage.getItem(`skillsphere_apply_${jobId}`) || "null");
  } catch {
    return null;
  }
}
