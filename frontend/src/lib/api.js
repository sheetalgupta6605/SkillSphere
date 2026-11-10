const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export async function api(path, options = {}) {
  const token = localStorage.getItem("skillsphere_token") || sessionStorage.getItem("skillsphere_token");
  const headers = { ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }), ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch {
    throw new Error(
      `SkillSphere API is unreachable at ${API_URL}. ` +
      `Make sure the FastAPI backend is running: open a terminal in the backend folder and run "uvicorn main:app --reload". ` +
      `Also ensure MongoDB Atlas is accessible.`
    );
  }
  const body = await response.json().catch(() => ({}));
  if (response.status === 401) {
    localStorage.removeItem("skillsphere_token");
    sessionStorage.removeItem("skillsphere_token");
    window.dispatchEvent(new Event("skillsphere:unauthorized"));
  }
  if (!response.ok) throw new Error(body.detail || "Something went wrong");
  return body;
}

export { API_URL };

