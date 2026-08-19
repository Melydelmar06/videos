const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8420";

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
