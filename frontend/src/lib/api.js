export function formatApiError(body) {
  if (!body) return "Something went wrong";
  if (typeof body === "string") return body;

  const detail = body.detail ?? body.message ?? body.error;
  if (!detail) return "Something went wrong";
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (!item) return "";
        if (typeof item === "string") return item;
        if (typeof item === "object") {
          const field = Array.isArray(item.loc)
            ? item.loc.filter((part) => part !== "body").join(".")
            : item.field || "";
          const msg = item.msg || item.message || JSON.stringify(item);
          return field ? `${field}: ${msg}` : msg;
        }
        return String(item);
      })
      .filter(Boolean);

    if (messages.length > 0) {
      return messages.join("; ");
    }
  }

  if (typeof detail === "object") {
    if (detail.msg || detail.message) return detail.msg || detail.message;
    try {
      return JSON.stringify(detail);
    } catch {
      return "Validation error";
    }
  }

  return String(detail);
}

const API_URL = (
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export async function api(path, options = {}) {
  const token =
    localStorage.getItem("skillsphere_token") ||
    sessionStorage.getItem("skillsphere_token");

  const headers = {
    ...(options.body instanceof FormData
      ? {}
      : { "Content-Type": "application/json" }),
    ...(options.headers || {})
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response;

  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers
    });
  } catch {
    throw new Error(
      `Cannot connect to SkillSphere API at ${API_URL}. ` +
      "Please make sure the FastAPI backend is running."
    );
  }

  const body = await response.json().catch(() => ({}));

  if (response.status === 401) {
    localStorage.removeItem("skillsphere_token");
    sessionStorage.removeItem("skillsphere_token");

    window.dispatchEvent(
      new Event("skillsphere:unauthorized")
    );
  }

  if (!response.ok) {
    throw new Error(formatApiError(body));
  }

  return body;
}

export { API_URL };
