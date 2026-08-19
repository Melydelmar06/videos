const KEY = "aphelion_session_token";

export function getSessionToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(KEY);
}

export function setSessionToken(token: string) {
  window.localStorage.setItem(KEY, token);
}

export function clearSessionToken() {
  window.localStorage.removeItem(KEY);
}
