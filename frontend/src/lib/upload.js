import { API_URL, formatApiError } from "./api";

export function uploadWithProgress(path, body, onProgress = () => {}) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const token = localStorage.getItem("skillsphere_token") || sessionStorage.getItem("skillsphere_token");
    xhr.open("POST", `${API_URL}${path}`);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = event => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onerror = () => reject(new Error("Upload could not reach SkillSphere. Check your connection and try again."));
    xhr.onload = () => {
      let response = {};
      try { response = JSON.parse(xhr.responseText || "{}"); } catch { /* use the fallback below */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(response);
      else reject(new Error(formatApiError(response) || "Resume upload failed. Please try again."));
    };
    xhr.send(body);
  });
}
