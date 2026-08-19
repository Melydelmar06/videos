"use client";

import { useEffect, useState } from "react";
import ReadingResult from "@/components/ReadingResult";
import { Reading, getSeason } from "@/lib/api";

export default function SeasonScreen() {
  const [reading, setReading] = useState<Reading | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load(refresh = false) {
    setLoading(true);
    setError("");
    try {
      setReading(await getSeason(refresh));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center gap-4 py-24">
        <div className="w-10 h-10 rounded-full animate-spin" style={{ border: "3px solid var(--line)", borderTopColor: "var(--accent)" }} />
        <p className="text-sm" style={{ color: "var(--text-dim)" }}>Charting your season…</p>
      </div>
    );
  }

  if (error || !reading) {
    return <p className="text-sm text-center py-24" style={{ color: "var(--text-dim)" }}>{error || "Couldn't load your season ahead."}</p>;
  }

  return (
    <div className="pb-28">
      <ReadingResult reading={reading} onRestart={() => load(true)} restartLabel="Refresh my season" />
    </div>
  );
}
