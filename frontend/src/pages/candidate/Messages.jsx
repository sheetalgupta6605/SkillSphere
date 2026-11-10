import { useEffect, useRef, useState } from "react";
import { API_URL, api } from "../../lib/api";

export function Messages() {
  const [threads, setThreads] = useState([]);
  const [activeId, setActiveId] = useState("");
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  async function loadThreads() {
    try {
      const result = await api("/api/messages");
      setThreads(result);
      if (!activeId && result.length) setActiveId(result[0].peer_id);
    } catch (err) { setError(err.message); }
  }

  async function loadMessages(peerId) {
    if (!peerId) return;
    try {
      const result = await api(`/api/messages/${encodeURIComponent(peerId)}`);
      setMessages(result.messages || []);
      setError("");
    } catch (err) { setError(err.message); }
  }

  useEffect(() => { loadThreads(); }, []);
  useEffect(() => { loadMessages(activeId); }, [activeId]);
  useEffect(() => {
    const token = localStorage.getItem("skillsphere_token") || sessionStorage.getItem("skillsphere_token");
    if (!token) return;
    const socketUrl = API_URL.replace(/^http/, "ws") + "/ws";
    const socket = new WebSocket(socketUrl);
    socket.onopen = () => socket.send(JSON.stringify({ type: "auth", token }));
    socket.onmessage = event => {
      const payload = JSON.parse(event.data);
      if (payload.type === "message") {
        loadThreads();
        if (payload.message?.sender_id === activeId || payload.message?.recipient_id === activeId) loadMessages(activeId);
      }
    };
    return () => socket.close();
  }, [activeId]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function send(event) {
    event.preventDefault();
    const body = draft.trim();
    if (!activeId || !body) return;
    try {
      const saved = await api("/api/messages", { method: "POST", body: JSON.stringify({ recipient_id: activeId, body }) });
      setMessages(current => [...current, saved]);
      setDraft("");
      loadThreads();
    } catch (err) { setError(err.message); }
  }

  const active = threads.find(thread => thread.peer_id === activeId);
  return <section className="dashboard-page inbox-page messages-page">
    <div className="inbox-heading"><div><span className="eyebrow">Recruiter conversations</span><h1>Messages</h1><p className="muted page-intro">Keep your conversations and next steps together.</p></div></div>
    {error && <div className="error-box">{error}</div>}
    <div className="messenger">
      <aside className="thread-list" aria-label="Conversations">
        <div className="thread-list-heading">Inbox <span>{threads.length}</span></div>
        {threads.map(thread => <button key={thread.peer_id} className={`thread-item ${activeId === thread.peer_id ? "active" : ""}`} onClick={() => setActiveId(thread.peer_id)}>
          <span className="avatar">{thread.peer_name?.[0] || "?"}</span><span className="thread-copy"><strong>{thread.peer_name}</strong><small>{thread.last_message}</small></span>{thread.unread_count > 0 && <span className="unread-count">{thread.unread_count}</span>}
        </button>)}
        {!threads.length && <p className="muted thread-empty">Your recruiter conversations will appear here.</p>}
      </aside>
      <div className="chat-panel">
        {active ? <>
          <header className="chat-header"><span className="avatar">{active.peer_name?.[0] || "?"}</span><div><strong>{active.peer_name}</strong><small>SkillSphere member</small></div></header>
          <div className="chat-messages">{messages.map(message => <article key={message.id} className={`chat-bubble ${message.sender_id === activeId ? "incoming" : "outgoing"}`}><p>{message.body}</p><time>{new Date(message.created_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</time></article>)}<div ref={bottomRef}/></div>
          <form className="chat-compose" onSubmit={send}><label className="sr-only" htmlFor="message-draft">Write a message</label><textarea id="message-draft" rows="1" value={draft} onChange={event => setDraft(event.target.value)} placeholder="Write a message…" maxLength={5000}/><button className="primary-button" disabled={!draft.trim()}>Send</button></form>
        </> : <div className="empty-state compact-empty"><div className="empty-icon">✦</div><h3>No conversations yet</h3><p>When a recruiter contacts you, you can reply here.</p></div>}
      </div>
    </div>
  </section>;
}
