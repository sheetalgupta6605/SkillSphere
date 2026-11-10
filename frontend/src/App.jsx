import { useEffect, useRef, useState } from "react";
import { BrowserRouter, Route, Routes, useLocation, useNavigate as useRouterNavigate, useNavigationType } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { AdminLayout, CandidateLayout, Navbar, RecruiterLayout } from "./components/Layout";
import { PageChrome } from "./components/PageChrome";
import { Landing, About, Recruiters } from "./pages/Public";
import { Login, Signup } from "./pages/auth/index.js";
import { AdminAnalytics } from "./pages/admin/Analytics";
import { AdminDashboard } from "./pages/admin/Dashboard";
import { AdminUsers } from "./pages/admin/Users";
import { AdminApplications, AdminCandidates, AdminCompanies, AdminJobApprovals, AdminRecruiters, AdminReports } from "./pages/admin/Management";
import {
  Analysis, Applications, CandidateDashboard, InterviewPrep, JobDetail, JobMatcher, Jobs,
  LearningCentre, Messages, Notifications, OCRResults, PersonalDetails, Profile,
  Resume, ResumeBuilder, SavedJobs, SettingsPage, RecentlyViewed,
} from "./pages/candidate";
import { ApplicantDetails, Applicants, Company, ManageJobPage, PostJob, RecruiterAnalysisDetails, RecruiterDashboard, RecruiterJobs, RecruiterProfile, ResumeSearch } from "./pages/recruiter";
import { ApplyJobPage, ApplicationDetailPage } from "./pages/candidate/Applications";
import "./styles.css";

const rolePages = {
  candidate: ["personal-details", "profile", "resume", "ocr", "analysis", "job-matcher", "jobs", "saved", "recently-viewed", "applications", "resume-builder", "learning", "interview-prep"],
  recruiter: ["post-job", "company", "recruiter-profile", "jobs", "applicants", "recruiter-analytics", "resume-search"],
  admin: ["admin-users", "admin-jobs", "admin-analytics", "admin-candidates", "admin-recruiters", "admin-companies", "admin-applications", "admin-analyses", "admin-reports"],
};
const sharedPages = ["messages", "notifications", "settings"];
const knownPages = new Set([
  "home", "dashboard", "login", "register", "jobs", "about", "recruiters",
  ...sharedPages, ...Object.values(rolePages).flat(),
]);
const comingSoonTitles = {
  "admin-analyses": "Resume Analyses",
};

function pageFromPath(pathname) {
  const path = pathname.replace(/^\/+|\/+$/g, "");
  const nested = path.match(/^(candidate|recruiter|admin)\/(.+)$/);
  return nested ? nested[2] : path || "home";
}

function UnauthorizedPage({ onNavigate }) {
  return <section className="not-found-page"><span className="eyebrow">Unauthorized access</span><h1>You don’t have access to this page.</h1><p>Your account role does not include this area.</p><button className="primary-button" onClick={() => onNavigate("dashboard")}>Go to your dashboard</button></section>;
}

function NotFoundPage({ onNavigate }) {
  return <section className="not-found-page"><span className="not-found-code">404</span><h1>We couldn’t find that page.</h1><p>Check the address or return to a page available to your account.</p><button className="primary-button" onClick={() => onNavigate("dashboard")}>Go to dashboard</button></section>;
}

function ComingSoonPage({ page, onNavigate }) {
  return <section className="not-found-page"><span className="eyebrow">Planned for a later phase</span><h1>{comingSoonTitles[page]}</h1><p>This area is not available yet. No placeholder records or actions are shown here.</p><button className="secondary-button" onClick={() => onNavigate("dashboard")}>Back to dashboard</button></section>;
}

function AppContent() {
  const { user, setUser, loading: authLoading, logout: endSession } = useAuth();
  const [theme, setTheme] = useState(() => localStorage.getItem("skillsphere_theme") || "light");
  const [page, setPage] = useState(() => pageFromPath(window.location.pathname));
  const historyRef = useRef([]);
  const pageRef = useRef(page);
  const routerNavigate = useRouterNavigate();
  const location = useLocation();
  const navigationType = useNavigationType();

  useEffect(() => {
    const nextPage = pageFromPath(location.pathname);
    if (navigationType === "POP") {
      if (historyRef.current.at(-1) === nextPage) historyRef.current.pop();
      else if (pageRef.current !== nextPage) historyRef.current.push(pageRef.current);
    }
    pageRef.current = nextPage;
    setPage(nextPage);
  }, [location.pathname, location.key, navigationType]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("skillsphere_theme", theme);
  }, [theme]);

  function pathForPage(nextPage, role = user?.role) {
    if (nextPage === "home") return "/";
    if (nextPage === "dashboard" && ["candidate", "recruiter", "admin"].includes(role)) return `/${role}/dashboard`;
    if (nextPage === "jobs" && ["candidate", "recruiter"].includes(role)) return `/${role}/jobs`;
    if (role === "candidate" && nextPage.startsWith("job-")) return `/${role}/${nextPage}`;
    if (role === "candidate" && (nextPage.startsWith("analysis-result-") || nextPage.startsWith("apply-") || nextPage.startsWith("application-"))) return `/${role}/${nextPage}`;
    if (role === "recruiter" && (nextPage.startsWith("recruiter-job-") || nextPage.startsWith("recruiter-app-") || nextPage.startsWith("recruiter-analysis-"))) return `/${role}/${nextPage}`;
    if (role && (rolePages[role]?.includes(nextPage) || sharedPages.includes(nextPage))) return `/${role}/${nextPage}`;
    return `/${nextPage}`;
  }

  function navigate(nextPage, role = user?.role, replace = false, recordHistory = true) {
    const target = pathForPage(nextPage, role);
    if (nextPage === page && location.pathname === target) return;
    if (!replace && recordHistory && pageRef.current !== nextPage) historyRef.current.push(pageRef.current);
    pageRef.current = nextPage;
    setPage(nextPage);
    routerNavigate(target, { replace });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  useEffect(() => {
    if (authLoading || !user) return;
    if (["login", "register"].includes(page)) {
      navigate("dashboard", user.role, true, false);
      return;
    }
    if (page === "dashboard" && location.pathname !== `/${user.role}/dashboard`) {
      routerNavigate(`/${user.role}/dashboard`, { replace: true });
    }
  }, [authLoading, user, page, location.pathname]);

  function goBack() {
    let previousPage = historyRef.current.pop();
    while (["home", "login", "register"].includes(previousPage)) previousPage = historyRef.current.pop();
    navigate(previousPage || (user ? "dashboard" : "jobs"), user?.role, false, false);
  }

  function loadSignedInUser(signedInUser, returnPage = "dashboard") {
    setUser(signedInUser);
    navigate(returnPage, signedInUser.role);
  }

  async function logout() {
    await endSession();
    historyRef.current = [];
    pageRef.current = "home";
    setPage("home");
    routerNavigate("/", { replace: true });
  }

  function content() {
    if (page === "login") return <Login onSuccess={(signedInUser) => loadSignedInUser(signedInUser)} onNavigate={navigate} />;
    if (page === "register") return <Signup onSuccess={loadSignedInUser} onNavigate={navigate} />;
    const isAnalysisResult = page.startsWith("analysis-result-");
    const isApplyPage = page.startsWith("apply-");
    const isApplicationDetail = page.startsWith("application-");
    const isRecruiterJob = page.startsWith("recruiter-job-");
    const isRecruiterApplication = page.startsWith("recruiter-app-");
    const isRecruiterAnalysis = page.startsWith("recruiter-analysis-");
    if (!knownPages.has(page) && !page.startsWith("job-") && !isAnalysisResult && !isApplyPage && !isApplicationDetail && !isRecruiterJob && !isRecruiterApplication && !isRecruiterAnalysis) return <NotFoundPage onNavigate={navigate} />;
    if (!user && (isAnalysisResult || isApplyPage || isApplicationDetail || isRecruiterJob || isRecruiterApplication || isRecruiterAnalysis || rolePages.candidate.includes(page) || rolePages.recruiter.includes(page) || rolePages.admin.includes(page) || sharedPages.includes(page))) {
      return <Login onSuccess={(signedInUser) => loadSignedInUser(signedInUser, page)} onNavigate={navigate} />;
    }
    const pathRole = location.pathname.match(/^\/(candidate|recruiter|admin)(?:\/|$)/)?.[1];
    const requiredRole = isAnalysisResult || isApplyPage || isApplicationDetail ? "candidate" : isRecruiterJob || isRecruiterApplication || isRecruiterAnalysis ? "recruiter" : pathRole && (rolePages[pathRole]?.includes(page) || pathRole === "candidate" && page.startsWith("job-")) ? pathRole : !pathRole && page !== "jobs" ? Object.entries(rolePages).find(([, pages]) => pages.includes(page))?.[0] : undefined;
    if (user && requiredRole && user.role !== requiredRole) return <UnauthorizedPage onNavigate={navigate} />;
    if (comingSoonTitles[page]) return <ComingSoonPage page={page} onNavigate={navigate} />;
    if (page === "jobs" && user?.role === "recruiter") return <RecruiterJobs />;
    if (page === "jobs") return <Jobs user={user} onNavigate={navigate} />;
    if (page.startsWith("job-")) return <JobDetail jobId={page.slice(4)} user={user} onNavigate={navigate} />;
    if (isApplyPage && user?.role === "candidate") return <ApplyJobPage jobId={page.slice("apply-".length)} onNavigate={navigate} />;
    if (isApplicationDetail && user?.role === "candidate") return <ApplicationDetailPage applicationId={page.slice("application-".length)} onNavigate={navigate} />;
    if (page === "about") return <About />;
    if (page === "recruiters") return <Recruiters />;
    if (page === "personal-details" && user?.role === "candidate") return <PersonalDetails user={user} />;
    if (page === "profile" && user?.role === "candidate") return <Profile user={user} />;
    if (page === "resume" && user?.role === "candidate") return <Resume />;
    if (page === "ocr" && user?.role === "candidate") return <OCRResults />;
    if (page === "analysis" && user?.role === "candidate") return <Analysis onNavigate={navigate} />;
    if (page === "job-matcher" && user?.role === "candidate") return <JobMatcher onNavigate={navigate} />;
    if (isAnalysisResult && user?.role === "candidate") return <Analysis analysisId={page.slice("analysis-result-".length)} onNavigate={navigate} />;
    if (page === "saved" && user?.role === "candidate") return <SavedJobs onNavigate={navigate} />;
    if (page === "recently-viewed" && user?.role === "candidate") return <RecentlyViewed onNavigate={navigate} />;
    if (page === "applications" && user?.role === "candidate") return <Applications onNavigate={navigate} />;
    if (page === "messages" && user) return <Messages />;
    if (page === "notifications" && user) return <Notifications onNavigate={navigate} />;
    if (page === "resume-builder" && user?.role === "candidate") return <ResumeBuilder onNavigate={navigate} />;
    if (page === "learning" && user?.role === "candidate") return <LearningCentre onNavigate={navigate} />;
    if (page === "interview-prep" && user?.role === "candidate") return <InterviewPrep onNavigate={navigate} />;
    if (page === "settings" && user) return <SettingsPage user={user} theme={theme} setTheme={setTheme} onLogout={logout} onNavigate={navigate} />;
    if (page === "post-job" && user?.role === "recruiter") return <PostJob onNavigate={navigate} />;
    if (page === "company" && user?.role === "recruiter") return <Company />;
    if (page === "recruiter-profile" && user?.role === "recruiter") return <RecruiterProfile />;
    if (page === "applicants" && user?.role === "recruiter") return <Applicants onNavigate={navigate} />;
    if (page === "resume-search" && user?.role === "recruiter") return <ResumeSearch />;
    if (isRecruiterJob && user?.role === "recruiter") return <ManageJobPage jobId={page.slice("recruiter-job-".length)} onNavigate={navigate} />;
    if (isRecruiterApplication && user?.role === "recruiter") return <ApplicantDetails applicationId={page.slice("recruiter-app-".length)} onNavigate={navigate} />;
    if (isRecruiterAnalysis && user?.role === "recruiter") return <RecruiterAnalysisDetails analysisId={page.slice("recruiter-analysis-".length)} onNavigate={navigate} />;
    if (page === "recruiter-analytics" && user?.role === "recruiter") return <RecruiterDashboard user={user} onNavigate={navigate} />;
    if (page === "admin-users" && user?.role === "admin") return <AdminUsers user={user} />;
    if (["admin-analytics", "admin-reports"].includes(page) && user?.role === "admin") return <AdminReports />;
    if (page === "admin-candidates" && user?.role === "admin") return <AdminCandidates />;
    if (page === "admin-recruiters" && user?.role === "admin") return <AdminRecruiters />;
    if (page === "admin-companies" && user?.role === "admin") return <AdminCompanies />;
    if (page === "admin-jobs" && user?.role === "admin") return <AdminJobApprovals />;
    if (page === "admin-applications" && user?.role === "admin") return <AdminApplications />;
    if (page === "dashboard" && user?.role === "candidate") return <CandidateDashboard user={user} onNavigate={navigate} />;
    if (page === "dashboard" && user?.role === "recruiter") return <RecruiterDashboard user={user} onNavigate={navigate} />;
    if (page === "dashboard" && user?.role === "admin") return <AdminDashboard user={user} onNavigate={navigate} />;
    return <Landing onNavigate={navigate} />;
  }

  if (authLoading) return <section className="auth-page"><div className="auth-panel" role="status" aria-live="polite">Checking your session…</div></section>;

  const workspaceRoute = /^\/(candidate|recruiter|admin)(?:\/|$)/.test(location.pathname);
  const dashboard = user && page !== "home" && (! ["jobs", "about", "recruiters", "login", "register"].includes(page) || workspaceRoute);
  const RoleLayout = user?.role === "candidate" ? CandidateLayout : user?.role === "recruiter" ? RecruiterLayout : AdminLayout;
  const renderedContent = <div key={page} className="route-view"><PageChrome page={page} user={user} onBack={goBack} onNavigate={navigate} />{content()}</div>;

  return dashboard
    ? <RoleLayout user={user} activePage={page} theme={theme} setTheme={setTheme} onNavigate={navigate} onLogout={logout}>{renderedContent}</RoleLayout>
    : <><Navbar user={user} theme={theme} setTheme={setTheme} onNavigate={navigate} onLogout={logout} />{renderedContent}<footer><span className="brand"><span className="brand-mark">S</span> SkillSphere</span><span>Discover. Match. Apply. Grow.</span></footer></>;
}

export default function App() {
  return <BrowserRouter><Routes>
    <Route path="/" element={<AppContent />} />
    <Route path="/candidate/*" element={<AppContent />} />
    <Route path="/recruiter/*" element={<AppContent />} />
    <Route path="/admin/*" element={<AppContent />} />
    <Route path="/:page" element={<AppContent />} />
    <Route path="*" element={<AppContent />} />
  </Routes></BrowserRouter>;
}
