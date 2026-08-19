import { getSessionToken } from "@/lib/session";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8420";

async function authedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getSessionToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body) headers.set("Content-Type", "application/json");
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    throw new Error("Your session has expired — please sign in again.");
  }
  return res;
}

async function serviceUnavailableOr(res: Response, fallbackMessage: string): Promise<never> {
  if (res.status === 503) {
    throw new Error("Our reading service is temporarily unavailable. Please try again in a moment.");
  }
  const detail = await res.json().catch(() => null);
  throw new Error(detail?.detail ?? fallbackMessage);
}

export type GeocodeResult = {
  label: string;
  latitude: number;
  longitude: number;
  timezone: string;
};

export async function geocode(query: string): Promise<GeocodeResult[]> {
  if (query.trim().length < 2) return [];
  const res = await fetch(`${API_BASE}/api/geocode?q=${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error("place lookup failed");
  return res.json();
}

export type ReadingRequest = {
  name: string;
  birth_date: string; // YYYY-MM-DD
  birth_time: string; // HH:MM:SS
  latitude: number;
  longitude: number;
  timezone_name: string;
};

export type WhyPanel = {
  tier: "strong signal" | "notable" | "minor undertone" | "quiet";
  independent_systems: number;
  main_window: string | null;
  themes_involved: string[];
};

export type CategoryReading = {
  label: string;
  headline: string;
  body: string;
  confidence: "strong signal" | "notable" | "minor undertone" | "quiet";
  why: WhyPanel;
};

export type BiggerPicture = {
  headline: string;
  body: string;
};

export type Timeline = {
  now: string | null;
  next: string | null;
  later: string | null;
};

export type Reading = {
  natal_summary: string;
  window: { start: string; end: string };
  categories: Record<string, CategoryReading>;
  bigger_picture: BiggerPicture;
  timeline: Timeline;
};

export async function createReading(req: ReadingRequest): Promise<Reading> {
  const res = await fetch(`${API_BASE}/api/reading`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    if (res.status === 503) {
      // service-level failure (e.g. the reading model is unavailable) --
      // never surface the raw backend detail (API key/config internals)
      // to an end user.
      throw new Error("Our reading service is temporarily unavailable. Please try again in a moment.");
    }
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? "We couldn't generate your reading — please check your details and try again.");
  }
  return res.json();
}

export const CATEGORY_ORDER = [
  "love_relationships",
  "work_career",
  "money_finance",
  "home_family",
  "health_wellbeing",
  "personal_growth",
];

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export async function requestMagicLink(email: string): Promise<{ dev_mode: boolean; dev_magic_token: string | null }> {
  const res = await fetch(`${API_BASE}/api/auth/request-link`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }),
  });
  if (!res.ok) return serviceUnavailableOr(res, "Couldn't send a sign-in link — please try again.");
  return res.json();
}

export async function consumeMagicLink(token: string): Promise<{ session_token: string }> {
  const res = await fetch(`${API_BASE}/api/auth/consume`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }),
  });
  if (!res.ok) return serviceUnavailableOr(res, "That link didn't work — please request a new one.");
  return res.json();
}

// ---------------------------------------------------------------------------
// Profile
// ---------------------------------------------------------------------------

export type ProfileStatus = { has_profile: boolean; name?: string };

export async function getProfileStatus(): Promise<ProfileStatus> {
  const res = await authedFetch("/api/profile");
  if (!res.ok) return serviceUnavailableOr(res, "Couldn't check your profile.");
  return res.json();
}

export async function saveProfile(req: ReadingRequest): Promise<ProfileStatus> {
  const res = await authedFetch("/api/profile", { method: "POST", body: JSON.stringify(req) });
  if (!res.ok) return serviceUnavailableOr(res, "Couldn't save your birth details.");
  return res.json();
}

// ---------------------------------------------------------------------------
// Today (Understand)
// ---------------------------------------------------------------------------

export type DimensionReading = {
  label: string;
  tier: "strong signal" | "notable" | "minor undertone" | "quiet";
  character: "expansive" | "contractive" | "mixed" | null;
  text: string | null;
};

export type TodayReading = {
  date: string;
  natal_summary: string;
  overall_note: string | null;
  dimensions: Record<string, DimensionReading>;
};

export async function getToday(): Promise<TodayReading> {
  const res = await authedFetch("/api/today");
  if (!res.ok) return serviceUnavailableOr(res, "Couldn't load today's reading.");
  return res.json();
}

// ---------------------------------------------------------------------------
// Check-ins (Reflect)
// ---------------------------------------------------------------------------

export const MOODS = ["Energised", "Calm", "Happy", "Flat", "Anxious", "Emotional", "Irritable", "Overwhelmed", "Exhausted"] as const;
export const LIFE_AREAS = ["Relationship", "Work", "Money", "Family", "Health", "Myself", "Something else", "I don't know"] as const;

export type CheckIn = {
  checkin_date: string;
  mood: string;
  life_area: string | null;
  note: string | null;
  created_at: string;
  updated_at?: string;
};

export async function getTodayCheckIn(): Promise<CheckIn | null> {
  const res = await authedFetch("/api/checkin");
  if (!res.ok) return serviceUnavailableOr(res, "Couldn't load your check-in.");
  const data = await res.json();
  return Object.keys(data).length ? data : null;
}

export async function submitCheckIn(mood: string, life_area: string | null, note: string | null): Promise<CheckIn> {
  const res = await authedFetch("/api/checkin", { method: "POST", body: JSON.stringify({ mood, life_area, note }) });
  if (!res.ok) return serviceUnavailableOr(res, "Couldn't save your check-in.");
  return res.json();
}

export async function getCheckInHistory(): Promise<CheckIn[]> {
  const res = await authedFetch("/api/checkin/history");
  if (!res.ok) return serviceUnavailableOr(res, "Couldn't load your check-in history.");
  const data = await res.json();
  return data.check_ins;
}

// ---------------------------------------------------------------------------
// Regulate
// ---------------------------------------------------------------------------

export type RegulateRecommendation = {
  practice_type: string;
  alternates: string[];
  human_chart_mismatch: boolean;
  driven_by: "human_reported" | "chart_only";
  intro: string;
  practice_title: string;
  practice_body: string;
};

export async function getRegulate(): Promise<RegulateRecommendation> {
  const res = await authedFetch("/api/regulate");
  if (!res.ok) return serviceUnavailableOr(res, "Couldn't load today's practice.");
  return res.json();
}

// ---------------------------------------------------------------------------
// Season (cached) + Prepare
// ---------------------------------------------------------------------------

export async function getSeason(refresh = false): Promise<Reading> {
  const res = await authedFetch(`/api/season${refresh ? "?refresh=true" : ""}`);
  if (!res.ok) return serviceUnavailableOr(res, "Couldn't load your season ahead.");
  return res.json();
}

export type PrepareNudge = { days_away: number; message: string } | Record<string, never>;

export async function getPrepare(): Promise<PrepareNudge> {
  const res = await authedFetch("/api/prepare");
  if (!res.ok) return serviceUnavailableOr(res, "Couldn't check what's ahead.");
  return res.json();
}
