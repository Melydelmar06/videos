"use client";

import { useState } from "react";
import { CheckIn, LIFE_AREAS, MOODS, submitCheckIn } from "@/lib/api";

export default function CheckInFlow({ onDone }: { onDone: (checkIn: CheckIn) => void }) {
  const [step, setStep] = useState<1 | 2>(1);
  const [mood, setMood] = useState<string | null>(null);
  const [lifeArea, setLifeArea] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function finish(skipLifeArea = false) {
    if (!mood) return;
    setSubmitting(true);
    try {
      const result = await submitCheckIn(mood, skipLifeArea ? null : lifeArea, note.trim() || null);
      onDone(result);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="rounded-3xl p-6 sm:p-7 flex flex-col gap-4"
      style={{ background: "var(--surface)", border: "1px solid var(--line)" }}
    >
      <p className="text-[11px] uppercase tracking-[0.14em]" style={{ color: "var(--accent)" }}>
        Check in
      </p>

      {step === 1 && (
        <>
          <h3 className="font-display text-2xl" style={{ color: "var(--text)" }}>
            How are you today?
          </h3>
          <div className="flex flex-wrap gap-2">
            {MOODS.map((m) => (
              <button
                key={m}
                onClick={() => {
                  setMood(m);
                  setStep(2);
                }}
                className="px-4 py-2 rounded-full text-sm transition-colors"
                style={{
                  background: mood === m ? "var(--accent)" : "var(--surface-2)",
                  color: mood === m ? "var(--surface)" : "var(--text)",
                  border: "1px solid var(--line)",
                }}
              >
                {m}
              </button>
            ))}
          </div>
        </>
      )}

      {step === 2 && (
        <>
          <h3 className="font-display text-2xl" style={{ color: "var(--text)" }}>
            What&apos;s taking up the most space?
          </h3>
          <div className="flex flex-wrap gap-2">
            {LIFE_AREAS.map((area) => (
              <button
                key={area}
                onClick={() => setLifeArea(area)}
                className="px-4 py-2 rounded-full text-sm transition-colors"
                style={{
                  background: lifeArea === area ? "var(--accent)" : "var(--surface-2)",
                  color: lifeArea === area ? "var(--surface)" : "var(--text)",
                  border: "1px solid var(--line)",
                }}
              >
                {area}
              </button>
            ))}
          </div>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Anything you want to note (optional)"
            maxLength={2000}
            rows={2}
            className="w-full px-4 py-3 rounded-2xl text-sm resize-none"
            style={{ background: "var(--surface-2)", border: "1px solid var(--line)", color: "var(--text)" }}
          />
          <div className="flex gap-3">
            <button
              onClick={() => finish(false)}
              disabled={submitting || !lifeArea}
              className="flex-1 rounded-full py-3 text-sm font-semibold disabled:opacity-40"
              style={{ background: "var(--accent)", color: "var(--surface)" }}
            >
              {submitting ? "Saving…" : "Done"}
            </button>
            <button
              onClick={() => finish(true)}
              disabled={submitting}
              className="text-sm underline underline-offset-4"
              style={{ color: "var(--text-faint)" }}
            >
              Skip
            </button>
          </div>
        </>
      )}
    </div>
  );
}
