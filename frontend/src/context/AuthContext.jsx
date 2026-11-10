import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";

const AuthContext = createContext(null);
const TOKEN_KEY = "skillsphere_token";

function readToken() {
  return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
}

function saveToken(token, remember) {
  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  (remember ? localStorage : sessionStorage).setItem(TOKEN_KEY, token);
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const clearExpiredSession = () => setUser(null);
    window.addEventListener("skillsphere:unauthorized", clearExpiredSession);
    return () => window.removeEventListener("skillsphere:unauthorized", clearExpiredSession);
  }, []);

  useEffect(() => {
    let mounted = true;
    if (!readToken()) {
      setLoading(false);
      return () => { mounted = false; };
    }
    api("/api/auth/me")
      .then((currentUser) => { if (mounted) setUser(currentUser); })
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        sessionStorage.removeItem(TOKEN_KEY);
        if (mounted) setUser(null);
      })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, []);

  async function login(credentials, remember = false) {
    const result = await api("/api/auth/login", { method: "POST", body: JSON.stringify(credentials) });
    saveToken(result.access_token, remember);
    setUser(result.user);
    return result.user;
  }

  async function register(details) {
    const payload = {
      full_name: details.full_name,
      email: details.email,
      password: details.password,
      confirm_password: details.confirm_password,
      contact_number: details.contact_number || null,
    };
    const endpoint = details.role === "recruiter"
      ? "/api/auth/register/recruiter"
      : "/api/auth/register/candidate";
    if (details.role === "recruiter") {
      payload.company_name = details.company_name;
      payload.company_website = details.company_website || null;
      payload.company_location = details.company_location;
    }
    return api(endpoint, { method: "POST", body: JSON.stringify(payload) });
  }

  async function logout() {
    try {
      if (readToken()) await api("/api/auth/logout", { method: "POST" });
    } catch {
      // Clear this browser session even when the server is already unreachable.
    } finally {
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
      setUser(null);
    }
  }

  const value = useMemo(() => ({ user, setUser, loading, login, register, logout }), [user, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}


