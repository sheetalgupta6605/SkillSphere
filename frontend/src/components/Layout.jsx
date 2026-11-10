import { useEffect, useState } from "react";
import { api } from "../lib/api";

const candidateLinks = [
  ["dashboard", "Dashboard", "⌂"], ["profile", "My Profile", "▤"],
  ["resume", "Resume", "▣"], ["jobs", "Find Jobs", "⌕"],
  ["saved", "Saved Jobs", "♡"], ["recently-viewed", "Recently Viewed", "◷"], ["applications", "My Applications", "☷"],
  ["analysis", "Resume Analysis", "◒"], ["job-matcher", "AI Job Matcher", "✧"], ["notifications", "Notifications", "♧"],
];
const recruiterLinks = [
  ["dashboard", "Dashboard", "⌂"], ["company", "Company Profile", "◇"], ["recruiter-profile", "Recruiter Profile", "♙"],
  ["jobs", "Manage Jobs", "▣"], ["post-job", "Post a Job", "＋"],
  ["applicants", "Applicants", "◎"],
  //  ["resume-search", "Resume Search", "⌕"],
  ["notifications", "Notifications", "♧"],
];
const adminLinks = [
  ["dashboard", "Dashboard", "⌂"], ["admin-users", "Manage Users", "♙"],
  ["admin-candidates", "Candidates", "♙"], ["admin-recruiters", "Recruiters", "♙"],
  ["admin-companies", "Companies", "◇"], ["admin-jobs", "Job Approvals", "▣"],
  ["admin-applications", "Applications", "☷"], ["admin-reports", "Reports", "▤"],
  ["notifications", "Notifications", "♧"],
];

export function ThemeButton({ theme, setTheme }) {
  return <button className="icon-button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="Toggle theme">{theme === "dark" ? "☼" : "☾"}</button>;
}

export function Navbar({ theme, setTheme, user, onNavigate, onLogout }) {
  const [menuOpen, setMenuOpen] = useState(false);
  function go(target) { setMenuOpen(false); onNavigate(target); }
  return <nav className="navbar"><button className="brand" onClick={() => go("home")}><span className="brand-mark">S</span> SkillSphere</button><div className={`nav-links ${menuOpen ? "open" : ""}`}><button onClick={() => go("jobs")}>Explore Jobs</button><button onClick={() => go("recruiters")}>For Recruiters</button><button onClick={() => go("about")}>About</button></div><div className="nav-actions"><ThemeButton theme={theme} setTheme={setTheme}/>{user ? <><button className="nav-user" onClick={() => go("dashboard")}>{user.full_name}</button><button className="text-button" onClick={onLogout}>Logout</button></> : <><button className="text-button" onClick={() => go("login")}>Login</button><button className="primary-button small" onClick={() => go("register")}>Get Started</button></>}<button className="menu-toggle" onClick={() => setMenuOpen(!menuOpen)} aria-label="Toggle navigation" aria-expanded={menuOpen}>{menuOpen ? "×" : "☰"}</button></div></nav>;
}

export function DashboardLayout({ user, theme, setTheme, onNavigate, onLogout, activePage, children, role: roleOverride }) {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("skillsphere_sidebar_collapsed") === "true");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const role = roleOverride || user?.role;
  const links = role === "recruiter" ? recruiterLinks : role === "admin" ? adminLinks : candidateLinks;
  const profilePage = role === "candidate" ? "profile" : role === "recruiter" ? "company" : "admin-users";
  const activeLabel = links.find(([key]) => key === activePage)?.[1] || (activePage === "settings" ? "Settings" : activePage?.replaceAll("-", " ") || "Dashboard");

  useEffect(() => {
    let alive = true;
    const refresh = () => api("/api/notifications/unread-count").then(value => { if (alive) setUnreadCount(value.count || 0); }).catch(() => {});
    refresh();
    const timer = window.setInterval(refresh, 30000);
    return () => { alive = false; window.clearInterval(timer); };
  }, [user?._id, user?.id]);

  function toggleSidebar() {
    setCollapsed((value) => {
      localStorage.setItem("skillsphere_sidebar_collapsed", String(!value));
      return !value;
    });
  }
  function toggleNavigation() {
    if (window.matchMedia("(max-width: 760px)").matches) setMobileOpen(value => !value);
    else toggleSidebar();
  }
  function navigateFromSidebar(target) {
    setMobileOpen(false);
    if (target !== activePage) onNavigate(target);
  }

  return <div className={`dashboard-shell ${collapsed ? "sidebar-collapsed" : ""} ${mobileOpen ? "mobile-sidebar-open" : ""}`}>
    <button className="mobile-sidebar-backdrop" aria-label="Close menu" onClick={() => setMobileOpen(false)} />
    <aside className="sidebar" aria-label={`${role || "user"} navigation`}>
      <button title={collapsed ? "SkillSphere" : undefined} className="brand side-brand" onClick={() => navigateFromSidebar("dashboard")}><span className="brand-mark">S</span><span className="brand-name">SkillSphere</span></button>
      <button className="sidebar-toggle" onClick={toggleSidebar} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>{collapsed ? "→" : "←"}</button>
      <div className="side-label">{role} workspace</div>
      {links.map(([key, label, icon, comingSoon]) => comingSoon
        ? <div key={key} className="side-link side-link-disabled" aria-disabled="true" title="Planned for a later phase"><span className="side-icon">{icon}</span><span>{label}</span><small>Later</small></div>
        : <button key={key} title={collapsed ? label : undefined} className={`side-link ${activePage === key ? "active" : ""}`} aria-current={activePage === key ? "page" : undefined} onClick={() => navigateFromSidebar(key)}><span className="side-icon">{icon}</span><span>{label}</span></button>)}
      <div className="side-bottom">
        <button title={collapsed ? "Settings" : undefined} className={`side-link ${activePage === "settings" ? "active" : ""}`} onClick={() => navigateFromSidebar("settings")}><span className="side-icon">⚙</span><span>Settings</span></button>
        <button title={collapsed ? "Logout" : undefined} className="side-link" onClick={onLogout}><span className="side-icon">↪</span><span>Logout</span></button>
      </div>
    </aside>
    <main className="dashboard-main">
      <div className="dashboard-top">
        {/* <button className="mobile-sidebar-toggle" onClick={toggleNavigation} aria-label={mobileOpen ? "Close navigation" : collapsed ? "Expand sidebar" : "Collapse sidebar"} title={collapsed ? "Expand sidebar" : "Toggle navigation"}>{mobileOpen ? "×" : "☰"}</button> */}
        <span className="eyebrow dashboard-page-title">{activeLabel}</span>
        <div className="top-actions">
          <ThemeButton theme={theme} setTheme={setTheme}/>
          <button className="icon-button notification-bell" onClick={() => onNavigate("notifications")} aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ""}`} title="Notifications">♧{unreadCount > 0 && <span className="notification-count">{unreadCount > 99 ? "99+" : unreadCount}</span>}</button>
          <div className="profile-menu">
            <button className="profile-menu-trigger" aria-haspopup="menu" aria-expanded={profileOpen} onClick={() => setProfileOpen((value) => !value)}>
              <span className="avatar">{user?.full_name?.[0] || "U"}</span><span className="profile-menu-name">{user?.full_name || "Account"}</span><span aria-hidden="true">⌄</span>
            </button>
            {profileOpen && <div className="profile-menu-panel" role="menu">
              <div className="profile-menu-summary"><strong>{user?.full_name}</strong><small>{user?.email}</small><small>{role}</small></div>
              <button role="menuitem" onClick={() => { setProfileOpen(false); onNavigate(profilePage); }}>Profile</button>
              <button role="menuitem" onClick={() => { setProfileOpen(false); onNavigate("settings"); }}>Settings</button>
              <button role="menuitem" onClick={() => { setProfileOpen(false); onLogout(); }}>Logout</button>
            </div>}
          </div>
        </div>
      </div>
      {children}
    </main>
  </div>;
}

export function CandidateLayout(props) { return <DashboardLayout {...props} role="candidate" />; }
export function RecruiterLayout(props) { return <DashboardLayout {...props} role="recruiter" />; }
export function AdminLayout(props) { return <DashboardLayout {...props} role="admin" />; }

export function StatCard({ label, value, hint, accent = "pink" }) { return <div className={`stat-card ${accent}`}><span>{label}</span><strong>{value}</strong><small>{hint}</small></div>; }
export function EmptyState({ title, text, action, onAction }) { return <div className="empty-state"><div className="empty-icon">✦</div><h3>{title}</h3><p>{text}</p>{action && <button className="primary-button" onClick={onAction}>{action}</button>}</div>; }

