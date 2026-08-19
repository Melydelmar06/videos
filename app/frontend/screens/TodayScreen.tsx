"use client";

import { useCallback, useEffect, useState } from "react";
import CheckInFlow from "@/components/CheckInFlow";
import DimensionCard from "@/components/DimensionCard";
import PrepareNudgeCard from "@/components/PrepareNudgeCard";
import RegulateCard from "@/components/RegulateCard";
import {
  CheckIn, PrepareNudge, RegulateRecommendation, TodayReading,
  getPrepare, getRegulate, getToday, getTodayCheckIn,
} from "@/lib/api";

function formatToday() {
  return new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
}

export default function TodayScreen() {
  const [today, setToday] = useState<TodayReading | null>(null);
  const [checkIn, setCheckIn] = useState<CheckIn | null | undefined>(undefined);
  const [regulate, setRegulate] = useState<RegulateRecommendation | null>(null);
  const [prepare, setPrepare] = useState<PrepareNudge | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadRegulate = useCallback(async () => {
    try {
      setRegulate(await getRegulate());
    } catch (e) {
      // Regulate is a bonus card, not core -- fail quietly rather than
      // blocking the whole Today screen if only this call errors.
      setRegulate(null);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [t, c, p] = await Promise.all([getToday(), getTodayCheckIn(), getPrepare().catch(() => ({}))]);
        setToday(t);
        setCheckIn(c);
        setPrepare(p as PrepareNudge);
        await loadRegulate();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Something went wrong.");
      } finally {
        setLoading(false);
      }
    })();
  }, [loadRegulate]);

  if (loading) {
    return (
      <div className="flex flex-col items-center gap-4 py-24">
        <div className="w-10 h-10 rounded-full animate-spin" style={{ border: "3px solid var(--line)", borderTopColor: "var(--accent)" }} />
        <p className="text-sm" style={{ color: "var(--text-dim)" }}>Reading today&apos;s sky…</p>
      </div>
    );
  }

  if (error || !today) {
    return <p className="text-sm text-center py-24" style={{ color: "var(--text-dim)" }}>{error || "Couldn't load today."}</p>;
  }

  const activeDimensions = Object.values(today.dimensions).filter((d) => d.tier !== "quiet" && d.text);

  return (
    <div className="w-full max-w-2xl flex flex-col gap-6 pb-28">
      <div className="flex flex-col gap-1 text-center">
        <p className="text-[11px] uppercase tracking-[0.16em]" style={{ color: "var(--accent)" }}>{formatToday()}</p>
        <h1 className="font-display text-4xl" style={{ color: "var(--text)" }}>Today</h1>
      </div>

      {activeDimensions.length === 0 ? (
        <div className="rounded-3xl p-6 text-center" style={{ background: "var(--surface)", border: "1px solid var(--line)" }}>
          <p className="text-sm" style={{ color: "var(--text-dim)" }}>{today.overall_note ?? "A quiet, steady day."}</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {activeDimensions.map((d) => <DimensionCard key={d.label} dimension={d} />)}
        </div>
      )}

      {checkIn === null && (
        <CheckInFlow onDone={(c) => { setCheckIn(c); loadRegulate(); }} />
      )}
      {checkIn && (
        <div className="rounded-2xl px-5 py-3 text-sm flex items-center justify-between" style={{ background: "var(--surface-2)", color: "var(--text-dim)" }}>
          <span>You said you&apos;re feeling <b style={{ color: "var(--text)" }}>{checkIn.mood.toLowerCase()}</b> today.</span>
          <button onClick={() => setCheckIn(null)} className="underline underline-offset-4 text-xs" style={{ color: "var(--text-faint)" }}>edit</button>
        </div>
      )}

      {regulate && <RegulateCard recommendation={regulate} />}
      {prepare && <PrepareNudgeCard nudge={prepare} />}
    </div>
  );
}
