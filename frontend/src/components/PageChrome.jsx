const pageNames = {
  home: "Home", dashboard: "Dashboard", "personal-details": "Personal details", profile: "My profile",
  resume: "Resume", ocr: "Resume scan", analysis: "Skill analysis", saved: "Saved jobs",
  applications: "Applications", messages: "Messages", notifications: "Notifications",
  jobs: "Find jobs", settings: "Settings", "resume-builder": "Resume builder",
  learning: "Learning centre", "interview-prep": "Interview prep", company: "Company profile",
  applicants: "Applicants", "post-job": "Post a job", "recruiter-analytics": "Analytics",
  "recruiter-profile": "Recruiter profile",
  "admin-users": "User management", "admin-jobs": "Job approvals", "admin-analytics": "Reports",
  "admin-candidates": "Candidates", "admin-recruiters": "Recruiters",
  "admin-companies": "Companies", "admin-applications": "Applications",
  "admin-analyses": "Resume analyses", "admin-reports": "Reports", 
  // "resume-search": "Resume search",
};

export function PageChrome({ page, user, onBack, onNavigate }) {
  const label = page.startsWith("job-") ? "Job details" : page.startsWith("analysis-result-") ? "Analysis result" : page.startsWith("apply-") ? "Apply for a job" : page.startsWith("application-") ? "Application details" : page.startsWith("recruiter-job-") ? "Manage job" : page.startsWith("recruiter-app-") ? "Applicant details" : page.startsWith("recruiter-analysis-") ? "Saved match analysis" : pageNames[page] || page.replaceAll("-", " ");
  const parent = user ? `${user.role[0].toUpperCase()}${user.role.slice(1)} workspace` : "SkillSphere";
  return <nav className="page-chrome" aria-label="Page navigation">
    <button className="back-link" onClick={onBack}>← <span>Back</span></button>
    <div className="breadcrumbs"><button onClick={() => onNavigate(user ? "dashboard" : "home")}>{parent}</button><span aria-hidden="true">/</span><span aria-current="page">{label}</span></div>
    {user && <button className="dashboard-shortcut" onClick={() => onNavigate("dashboard")}>⌂ <span>Dashboard</span></button>}
  </nav>;
}
