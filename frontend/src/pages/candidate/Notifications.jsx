// import { useEffect, useState } from "react";
// import { api } from "../../lib/api";

// const filters = ["all", "unread"];
// const targetPage = (item) => {
//   const type = item.notification_type || item.type;
//   if (type === "recruiter_message") return "messages";
//   if (["new_application", "application_withdrawn"].includes(type)) return "applicants";
//   if (type === "job_update") return "jobs";
//   if (item.related_id && ["application_update", "interview_scheduled"].includes(type)) return `application-${item.related_id}`;
//   return (item.href || "").replace(/^\//, "") || "notifications";
// };

// export function Notifications({ onNavigate }) {
//   const [items, setItems] = useState(null); const [filter, setFilter] = useState("all"); const [error, setError] = useState(""); const [skip, setSkip] = useState(0); const [more, setMore] = useState(true);
//   async function load(reset = false) {
//     const offset = reset ? 0 : skip;
//     try { const result = await api(`/api/notifications/me?limit=25&skip=${offset}${filter === "unread" ? "&unread_only=true" : ""}`); setItems(current => reset ? result : [...(current || []), ...result]); setSkip(offset + result.length); setMore(result.length === 25); setError(""); }
//     catch (err) { setError(err.message); if (reset) setItems([]); }
//   }
//   useEffect(() => { setItems(null); setSkip(0); load(true); }, [filter]);
//   async function markRead(item) { try { await api(`/api/notifications/${encodeURIComponent(item.id)}/read`, { method: "PATCH" }); setItems(current => current.map(value => value.id === item.id ? { ...value, is_read: true } : value)); } catch (err) { setError(err.message); } }
//   async function markAllRead() { try { await api("/api/notifications/read-all", { method: "PATCH" }); setItems(current => current.map(value => ({ ...value, is_read: true }))); } catch (err) { setError(err.message); } }
//   async function open(item) { if (!item.is_read) await markRead(item); onNavigate?.(targetPage(item)); }
//   return <section className="dashboard-page inbox-page">
//     <div className="inbox-heading"><div><span className="eyebrow">Your updates</span><h1>Notifications</h1><p className="muted page-intro">Application updates, messages, and hiring activity.</p></div><button className="secondary-button" onClick={markAllRead} disabled={!items?.some(item => !item.is_read)}>Mark all read</button></div>
//     <div className="inbox-filters" role="tablist" aria-label="Filter notifications">{filters.map(value => <button key={value} className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>{value === "all" ? "All" : "Unread"}</button>)}</div>
//     {error && <div className="error-box">{error}</div>}
//     <div className="inbox-list">{items === null ? <div className="loading">Loading notifications…</div> : items.length ? items.map(item => <article className={`inbox-item ${item.is_read ? "" : "unread"}`} key={item.id}>
//       <span className="inbox-marker" aria-hidden="true">{item.is_read ? "✓" : "•"}</span><button className="inbox-item-body inbox-open" onClick={() => open(item)}><div className="inbox-item-meta"><span className="inbox-type">{(item.notification_type || item.type || "Update").replaceAll("_", " ")}</span><time>{new Date(item.created_at).toLocaleString()}</time></div><h2>{item.title}</h2><p>{item.message}</p><span className="text-button">Open update →</span></button>{!item.is_read && <button className="text-button" onClick={() => markRead(item)}>Mark read</button>}</article>) : <div className="empty-state compact-empty"><div className="empty-icon">✦</div><h3>{filter === "unread" ? "No unread notifications" : "You're all caught up"}</h3><p>New activity will appear here.</p></div>}</div>
//     {items?.length > 0 && more && <button className="secondary-button" onClick={() => load(false)}>Load more</button>}
//   </section>;
// }



import { useEffect, useState } from "react";
import { api } from "../../lib/api";

const filters = ["all", "unread"];

const targetPage = (item) => {
  const type = item.notification_type || item.type;

  if (type === "recruiter_message") return "messages";

  if (["new_application", "application_withdrawn"].includes(type)) {
    return "applicants";
  }

  if (type === "job_update") return "jobs";

  if (
    item.related_id &&
    ["application_update", "interview_scheduled"].includes(type)
  ) {
    return `application-${item.related_id}`;
  }

  return (item.href || "").replace(/^\//, "") || "notifications";
};

function InterviewDetails({ item }) {
  const interview = item.data?.interview;

  if (!interview) return null;

  const scheduledDate = interview.scheduled_at
    ? new Date(interview.scheduled_at)
    : null;

  const validDate =
    scheduledDate && !Number.isNaN(scheduledDate.getTime());

  const online = interview.interview_type === "online";

  return (
    <div className="interview-notification-details">
      <h3>Interview Details</h3>

      <p>
        <strong>Company:</strong>{" "}
        {item.data?.company_name || "Not available"}
      </p>

      <p>
        <strong>Job:</strong>{" "}
        {item.data?.job_title || "Not available"}
      </p>

      <p>
        <strong>Date:</strong>{" "}
        {validDate
          ? scheduledDate.toLocaleDateString()
          : "Not available"}
      </p>

      <p>
        <strong>Time:</strong>{" "}
        {validDate
          ? scheduledDate.toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })
          : "Not available"}
      </p>

      <p>
        <strong>Interview type:</strong>{" "}
        {online ? "Online" : "In person"}
      </p>

      {online && interview.meeting_link && (
        <p>
          <strong>Meeting link:</strong>{" "}
          <a
            href={interview.meeting_link}
            target="_blank"
            rel="noopener noreferrer"
          >
            Join Interview
          </a>
        </p>
      )}

      {!online && interview.location && (
        <p>
          <strong>Location:</strong> {interview.location}
        </p>
      )}

      {interview.recruiter_name && (
        <p>
          <strong>Recruiter:</strong> {interview.recruiter_name}
        </p>
      )}

      {interview.instructions && (
        <div className="interview-instructions">
          <strong>Instructions</strong>
          <p>{interview.instructions}</p>
        </div>
      )}
    </div>
  );
}

export function Notifications({ onNavigate }) {
  const [items, setItems] = useState(null);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");
  const [skip, setSkip] = useState(0);
  const [more, setMore] = useState(true);

  async function load(reset = false) {
    const offset = reset ? 0 : skip;

    try {
      const result = await api(
        `/api/notifications/me?limit=25&skip=${offset}${
          filter === "unread" ? "&unread_only=true" : ""
        }`
      );

      setItems((current) =>
        reset ? result : [...(current || []), ...result]
      );

      setSkip(offset + result.length);
      setMore(result.length === 25);
      setError("");
    } catch (err) {
      setError(err.message);

      if (reset) setItems([]);
    }
  }

  useEffect(() => {
    setItems(null);
    setSkip(0);
    load(true);
  }, [filter]);

  async function markRead(item) {
    try {
      await api(
        `/api/notifications/${encodeURIComponent(item.id)}/read`,
        { method: "PATCH" }
      );

      setItems((current) =>
        current.map((value) =>
          value.id === item.id
            ? { ...value, is_read: true }
            : value
        )
      );
    } catch (err) {
      setError(err.message);
    }
  }

  async function markAllRead() {
    try {
      await api("/api/notifications/read-all", {
        method: "PATCH",
      });

      setItems((current) =>
        current.map((value) => ({
          ...value,
          is_read: true,
        }))
      );
    } catch (err) {
      setError(err.message);
    }
  }

  async function open(item) {
    if (!item.is_read) {
      await markRead(item);
    }

    onNavigate?.(targetPage(item));
  }

  return (
    <section className="dashboard-page inbox-page">
      <div className="inbox-heading">
        <div>
          <span className="eyebrow">Your updates</span>
          <h1>Notifications</h1>
          <p className="muted page-intro">
            Application updates, messages, and hiring activity.
          </p>
        </div>

        <button
          className="secondary-button"
          onClick={markAllRead}
          disabled={!items?.some((item) => !item.is_read)}
        >
          Mark all read
        </button>
      </div>

      <div className="inbox-filters" role="tablist">
        {filters.map((value) => (
          <button
            key={value}
            className={filter === value ? "active" : ""}
            onClick={() => setFilter(value)}
          >
            {value === "all" ? "All" : "Unread"}
          </button>
        ))}
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="inbox-list">
        {items === null ? (
          <div className="loading">Loading notifications…</div>
        ) : items.length ? (
          items.map((item) => (
            <article
              className={`inbox-item ${
                item.is_read ? "" : "unread"
              }`}
              key={item.id}
            >
              <span className="inbox-marker" aria-hidden="true">
                {item.is_read ? "✓" : "•"}
              </span>

              <div className="inbox-item-body">
                <div className="inbox-item-meta">
                  <span className="inbox-type">
                    {(
                      item.notification_type ||
                      item.type ||
                      "Update"
                    ).replaceAll("_", " ")}
                  </span>

                  <time>
                    {new Date(item.created_at).toLocaleString()}
                  </time>
                </div>

                <h2>{item.title}</h2>
                <p>{item.message}</p>

                {item.notification_type === "interview_scheduled" && (
                  <InterviewDetails item={item} />
                )}

                <button
                  className="text-button"
                  onClick={() => open(item)}
                >
                  Open update →
                </button>
              </div>

              {!item.is_read && (
                <button
                  className="text-button"
                  onClick={() => markRead(item)}
                >
                  Mark read
                </button>
              )}
            </article>
          ))
        ) : (
          <div className="empty-state compact-empty">
            <div className="empty-icon">✦</div>
            <h3>
              {filter === "unread"
                ? "No unread notifications"
                : "You're all caught up"}
            </h3>
            <p>New activity will appear here.</p>
          </div>
        )}
      </div>

      {items?.length > 0 && more && (
        <button
          className="secondary-button"
          onClick={() => load(false)}
        >
          Load more
        </button>
      )}
    </section>
  );
}
