import { useEffect, useState } from "react";
import { api } from "../../lib/api";

function BackButton({ onNavigate, target = "dashboard", label = "Back to dashboard" }) { return <button className="back-link" onClick={() => onNavigate(target)}>← {label}</button>; }

export function ResumeBuilder({ onNavigate }) {
  const [profile, setProfile] = useState(null); const [form, setForm] = useState({ headline: "", summary: "", skills: "" }); const [message, setMessage] = useState("");
  useEffect(() => {
    api("/api/candidates/profile")
      .then((data) => {
        setProfile(data);
        const skillString = (data?.skills || [])
          .map((s) => (typeof s === "object" && s !== null ? (s.name || s.skill || s.title || "") : String(s || "")).trim())
          .filter(Boolean)
          .join(", ");
        setForm({ headline: data?.headline || "", summary: data?.summary || "", skills: skillString });
      })
      .catch((err) => setMessage(err?.message || "Failed to load profile for resume builder."));
  }, []);
  function update(key, value) { setForm(current => ({ ...current, [key]: value })); }
  async function save() {
    try {
      const skillsArray = form.skills.split(",").map(item => item.trim()).filter(Boolean);
      await api("/api/candidates/profile", {
        method: "PUT",
        body: JSON.stringify({
          ...profile,
          ...form,
          skills: skillsArray,
          linkedin: profile.linkedin || null,
          github: profile.github || null,
          portfolio: profile.portfolio || null
        })
      });
      setMessage("Builder details saved to your profile.");
    } catch (err) {
      setMessage(err?.message || (typeof err === "string" ? err : "Failed to save profile."));
    }
  }
  function download() { const education = (profile?.education || []).map(item => `${item.degree || item.qualification || "Education"} — ${item.institution || item.college || ""}`).join("\n"); const experience = (profile?.experience || []).map(item => `${item.job_title || "Role"} — ${item.company || item.company_name || ""}\n${item.description || ""}`).join("\n\n"); const content = `${profile?.full_name || "Your Name"}\n${form.headline}\n\nSUMMARY\n${form.summary}\n\nSKILLS\n${form.skills}\n\nEDUCATION\n${education}\n\nEXPERIENCE\n${experience}`; const blob = new Blob([content], { type: "text/plain" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "skillsphere-resume.txt"; link.click(); }
  if (!profile) return <section className="dashboard-page"><div className="loading">Loading resume builder…</div></section>;
  return <section className="dashboard-page builder-page"><BackButton onNavigate={onNavigate}/><span className="eyebrow">Resume builder</span><h1>Shape your <em>story.</em></h1><p className="muted page-intro">Build a clean, ATS-friendly resume from the profile information you already saved.</p><div className="builder-layout"><form className="profile-form builder-form" onSubmit={e => { e.preventDefault(); save(); }}><label>Professional headline<input value={form.headline} onChange={e => update("headline", e.target.value)} placeholder="Frontend Developer"/></label><label>Professional summary<textarea rows="7" value={form.summary} onChange={e => update("summary", e.target.value)} placeholder="A concise summary of your strengths and goals"/></label><label>Skills <small>comma separated</small><input value={form.skills} onChange={e => update("skills", e.target.value)}/></label>{message && <div className={message.includes("saved") ? "success-box" : "error-box"}>{message}</div>}<div className="detail-actions"><button className="primary-button">Save profile</button><button type="button" className="secondary-button" onClick={download}>Download TXT</button><button type="button" className="secondary-button" onClick={() => window.print()}>Print / Save PDF</button></div></form><article className="resume-preview"><span className="eyebrow">Live preview</span><h2>{profile.full_name || "Your Name"}</h2><p className="resume-preview-headline">{form.headline || "Professional headline"}</p><hr/><h3>Summary</h3><p>{form.summary || "Your summary will appear here."}</p><h3>Skills</h3><p>{form.skills || "Add skills in the editor."}</p>{profile.education?.length > 0 && <><h3>Education</h3>{profile.education.map((item, index) => <p key={index}><strong>{item.degree || item.qualification}</strong><br/>{item.institution || item.college}</p>)}</>}</article></div></section>;
}

const resources = [
  ["MDN Web Docs", "Web development reference and guides.", "https://developer.mozilla.org/"],
  ["freeCodeCamp", "Free hands-on coding curriculum.", "https://www.freecodecamp.org/learn/"],
  ["Microsoft Learn", "Free technical learning paths.", "https://learn.microsoft.com/training/"],
  ["Khan Academy", "Free computer science foundations.", "https://www.khanacademy.org/computing"],
];

export function LearningCentre({ onNavigate }) {
  const [completed, setCompleted] = useState(() => JSON.parse(localStorage.getItem("skillsphere_learning") || "[]"));
  function toggle(title) { const next = completed.includes(title) ? completed.filter(item => item !== title) : [...completed, title]; setCompleted(next); localStorage.setItem("skillsphere_learning", JSON.stringify(next)); }
  return <section className="dashboard-page"><BackButton onNavigate={onNavigate}/><span className="eyebrow">Learning centre</span><h1>Keep <em>growing.</em></h1><p className="muted page-intro">Reliable learning resources to build the skills your next opportunity asks for.</p><div className="resource-grid">{resources.map(([title, description, url]) => <article className="resource-card" key={title}><span className="resource-icon">↗</span><h2>{title}</h2><p className="muted">{description}</p><div className="resource-actions"><a className="secondary-button" href={url} target="_blank" rel="noreferrer">Open resource</a><button className={`text-button ${completed.includes(title) ? "completed" : ""}`} onClick={() => toggle(title)}>{completed.includes(title) ? "Completed ✓" : "Mark complete"}</button></div></article>)}</div></section>;
}

const interviewQuestions = { HR: ["Tell me about yourself.", "What is a project you are proud of and why?", "How do you handle feedback?"], Technical: ["Explain a difficult technical problem you solved.", "How do you test and review your code?", "How would you improve a slow API?"], Behavioral: ["Tell me about a time you disagreed with a teammate.", "Describe a time you had to learn something quickly.", "How do you prioritize competing deadlines?"] };

export function InterviewPrep({ onNavigate }) {
  const [category, setCategory] = useState("HR"); const [answers, setAnswers] = useState(() => JSON.parse(localStorage.getItem("skillsphere_interview_notes") || "{}"));
  function update(question, value) { const next = { ...answers, [question]: value }; setAnswers(next); localStorage.setItem("skillsphere_interview_notes", JSON.stringify(next)); }
  return <section className="dashboard-page"><BackButton onNavigate={onNavigate}/><span className="eyebrow">Interview preparation</span><h1>Walk in with <em>confidence.</em></h1><p className="muted page-intro">Practice clear answers and keep private notes as you prepare.</p><div className="prep-tabs">{Object.keys(interviewQuestions).map(item => <button className={category === item ? "active" : ""} key={item} onClick={() => setCategory(item)}>{item}</button>)}</div><div className="question-list">{interviewQuestions[category].map(question => <article className="question-card" key={question}><h2>{question}</h2><textarea rows="5" placeholder="Write your answer or talking points…" value={answers[question] || ""} onChange={e => update(question, e.target.value)}/><small className="muted">Tip: use a specific example and explain the result.</small></article>)}</div></section>;
}

export function SettingsPage({ user, theme, setTheme, onLogout, onNavigate }) {
  const [preferences, setPreferences] = useState(null); const [currentPassword, setCurrentPassword] = useState(""); const [newPassword, setNewPassword] = useState(""); const [confirmPassword, setConfirmPassword] = useState(""); const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [saving, setSaving] = useState(false);
  useEffect(() => { api("/api/notifications/preferences").then(setPreferences).catch(err => setError(err.message)); }, []);
  async function savePreferences(event) { event.preventDefault(); setSaving(true); setError(""); setNotice(""); try { setPreferences(await api("/api/notifications/preferences", { method: "PUT", body: JSON.stringify(preferences) })); setNotice("Notification preferences saved."); } catch (err) { setError(err.message); } finally { setSaving(false); } }
  async function changePassword(event) { event.preventDefault(); setError(""); setNotice(""); if (newPassword !== confirmPassword) { setError("New passwords do not match."); return; } setSaving(true); try { await api("/api/auth/change-password", { method: "PUT", body: JSON.stringify({ current_password: currentPassword, password: newPassword, confirm_password: confirmPassword }) }); setNotice("Password changed. Please sign in again."); setCurrentPassword(""); setNewPassword(""); setConfirmPassword(""); window.setTimeout(onLogout, 700); } catch (err) { setError(err.message); } finally { setSaving(false); } }
  return <section className="dashboard-page"><BackButton onNavigate={onNavigate}/><span className="eyebrow">Account settings</span><h1>Your space, <em>your way.</em></h1>{error && <div className="error-box" role="alert">{error}</div>}{notice && <div className="success-box" role="status">{notice}</div>}<div className="settings-list"><article className="settings-card"><div><h2>Appearance</h2><p className="muted">Choose the interface theme for this device.</p></div><button className="secondary-button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? "Use light theme" : "Use dark theme"}</button></article><article className="settings-card"><div><h2>Account and privacy</h2><p className="muted">{user?.email} · Profile visibility and personal details</p></div><div className="detail-actions"><button className="secondary-button" onClick={() => onNavigate("personal-details")}>Edit account details</button><button className="secondary-button" onClick={() => onNavigate("profile")}>Privacy & profile</button></div></article><form className="settings-card settings-password-form" onSubmit={changePassword}><div><h2>Change password</h2><p className="muted">Changing your password ends this session; sign in again with your new password.</p></div><label>Current password<input type="password" required autoComplete="current-password" value={currentPassword} onChange={event => setCurrentPassword(event.target.value)}/></label><label>New password<input type="password" required minLength="8" autoComplete="new-password" value={newPassword} onChange={event => setNewPassword(event.target.value)}/></label><label>Confirm new password<input type="password" required minLength="8" autoComplete="new-password" value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)}/></label><button className="primary-button" disabled={saving}>{saving ? "Saving…" : "Change password"}</button></form><form className="settings-card settings-preferences" onSubmit={savePreferences}><div><h2>In-app notification preferences</h2><p className="muted">Choose which updates are saved to your notification inbox.</p></div>{preferences ? <>{[["application_updates", "Application updates"], ["interview_reminders", "Interview reminders"], ["messages", "Messages"], ["platform_updates", "Platform updates"]].map(([key, label]) => <label className="checkbox-label" key={key}><input type="checkbox" checked={preferences[key]} onChange={event => setPreferences(value => ({ ...value, [key]: event.target.checked }))}/>{label}</label>)}<button className="primary-button" disabled={saving}>{saving ? "Saving…" : "Save preferences"}</button></> : <p className="muted">Loading notification preferences…</p>}</form><article className="settings-card danger-card"><div><h2>Sign out</h2><p className="muted">Securely end this browser session.</p></div><button className="secondary-button" onClick={onLogout}>Logout</button></article></div></section>;
}
