"use client";

import { useEffect, useState } from "react";
import { CheckIn, getCheckInHistory } from "@/lib/api";

function formatDate(iso: string) {
  return new Date(iso + "T00:00:00Z").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" });
}

export default function JournalScreen() {
  const [checkIns, setCheckIns] = useState<CheckIn[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getCheckInHistory().then(setCheckIns).catch((e) => setError(e instanceof Error ? e.message : "Something went wrong."));
  }, []);

  return (
    <div className="w-full max-w-2xl flex flex-col gap-6 pb-28">
      <div className="flex flex-col gap-1 text-center">
        <p className="text-[11px] uppercase tracking-[0.16em]" style={{ color: "var(--accent)" }}>Your record</p>
        <h1 className="font-display text-4xl" style={{ color: "var(--text)" }}>Journal</h1>
      </div>

      {error && <p className="text-sm text-center" style={{ color: "var(--text-dim)" }}>{error}</p>}

      {checkIns && checkIns.length === 0 && (
        <p className="text-sm text-center" style={{ color: "var(--text-faint)" }}>
          No check-ins yet — they&apos;ll show up here once you start.
        </p>
      )}

      <div className="flex flex-col gap-3">
        {checkIns?.map((c) => (
          <div
            key={c.checkin_date}
            className="rounded-2xl px-5 py-4 flex flex-col gap-1"
            style={{ background: "var(--surface)", border: "1px solid var(--line)" }}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-[11px] uppercase tracking-[0.08em]" style={{ color: "var(--text-faint)" }}>
                {formatDate(c.checkin_date)}
              </span>
              <span className="text-sm font-medium" style={{ color: "var(--text)" }}>{c.mood}</span>
            </div>
            {c.life_area && (
              <p className="text-xs" style={{ color: "var(--text-faint)" }}>Focused on: {c.life_area}</p>
            )}
            {c.note && <p className="text-sm mt-1" style={{ color: "var(--text-dim)" }}>{c.note}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
