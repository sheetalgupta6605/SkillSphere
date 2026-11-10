import { useEffect, useState } from "react";

export function Landing({ onNavigate }) {
  const [backendStatus, setBackendStatus] = useState("Checking backend...");
  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"}/health`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data) => setBackendStatus(data.status === "success" ? "Backend connected" : "Backend unavailable"))
      .catch(() => setBackendStatus("Backend unavailable"));
  }, []);
  return <><section className="hero"><div className="hero-copy"><span className="pill">AI-powered career intelligence</span><h1>Your next opportunity <em>starts here.</em></h1><p>Discover opportunities, unlock your potential, and let AI connect your skills with the right career.</p><div className="hero-actions"><button className="primary-button" onClick={() => onNavigate("jobs")}>Explore Jobs <span>→</span></button><button className="secondary-button" onClick={() => onNavigate("register")}>Upload Resume</button></div><div className="trust-row"><span>{backendStatus}</span><span>Trusted by ambitious talent</span><b>2.4k+ matches made</b></div></div><div className="hero-visual"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="match-card"><div className="match-card-top"><span>Resume analysis</span><span className="live-dot">● Live</span></div><div className="score-ring"><strong>87</strong><small>% match</small></div><p>Senior Product Designer</p><span className="muted">Figma · Research · Strategy</span><div className="skill-bars"><i/><i/><i/></div></div><div className="float-card top-float">✦ <span>Perfect match found</span></div><div className="float-card bottom-float">↗ <span>12 new opportunities</span></div></div></section><section className="section centered"><span className="eyebrow">The smarter way forward</span><h2>Career growth, with <em>clarity.</em></h2><p className="section-lead">Everything you need to find work that fits who you are and where you want to go.</p><div className="feature-grid"><Feature icon="✦" title="AI-powered matching" text="See how your real skills align with every opportunity."/><Feature icon="◎" title="One profile, many paths" text="Tell your story once and discover roles that get it."/><Feature icon="↗" title="Move with confidence" text="Track every application and take the next right step."/></div></section>
  <section className="cta-section">
    <div><span className="eyebrow">Your next chapter</span><h2>Make your skills<br/><em>impossible to miss.</em></h2></div><button className="primary-button" onClick={() => onNavigate("register")}>Create free profile →</button></section></>;
}
function Feature({ icon, title, text }) { return <div className="feature-card"><div className="feature-icon">{icon}</div><h3>{title}</h3><p>{text}</p></div>; }
export function About() { return <section className="simple-page"><span className="eyebrow">About SkillSphere</span><h1>Find work that feels like <em>you.</em></h1><p>SkillSphere connects people and possibilities through transparent, skill-based career discovery.</p></section>; }
export function Recruiters() { return <section className="simple-page"><span className="eyebrow">For recruiters</span><h1>Meet the talent behind the <em>potential.</em></h1><p>Publish roles, understand applicants, and build stronger teams with practical matching intelligence.</p></section>; }


