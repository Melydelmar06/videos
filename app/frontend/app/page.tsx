"use client";

import { useState } from "react";
import GradientAtmosphere from "@/components/GradientAtmosphere";
import IntakeForm from "@/components/IntakeForm";
import ReadingResult from "@/components/ReadingResult";
import { createReading, Reading, ReadingRequest } from "@/lib/api";

type Stage = "intro" | "form" | "loading" | "result" | "error";

export default function Home() {
  const [stage, setStage] = useState<Stage>("intro");
  const [reading, setReading] = useState<Reading | null>(null);
  const [error, setError] = useState<string>("");

  async function handleSubmit(req: ReadingRequest) {
    setStage("loading");
    try {
      const result = await createReading(req);
      setReading(result);
      setStage("result");
    } catch (e) {
      setError(e instanceof Error ? e.message : "something went wrong");
      setStage("error");
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden">
      <GradientAtmosphere />

      <div className="relative flex flex-col items-center px-6 py-16 sm:py-24" style={{ zIndex: 1 }}>
        <nav className="w-full max-w-5xl flex items-center justify-between mb-16 sm:mb-24">
          <span className="font-display text-xl" style={{ color: "var(--text)" }}>
            aphelion
          </span>
          <span
            className="text-[11px] uppercase tracking-[0.14em]"
            style={{ color: "var(--text-faint)" }}
          >
            a reading for the season ahead
          </span>
        </nav>

        {stage === "intro" && (
          <div className="flex flex-col items-center text-center gap-8 max-w-xl">
            <h1 className="font-display text-5xl sm:text-6xl leading-[1.05]" style={{ color: "var(--text)" }}>
              what does your chart<br />say is coming?
            </h1>
            <p className="text-base max-w-md" style={{ color: "var(--text-dim)" }}>
              A structured reading of the season ahead — love, work, money, home, health,
              and growth — grounded in your actual chart, not generic sun-sign copy.
            </p>
            <button
              onClick={() => setStage("form")}
              className="rounded-full px-8 py-3.5 text-sm font-semibold tracking-wide"
              style={{ background: "var(--accent)", color: "var(--surface)" }}
            >
              Begin
            </button>
          </div>
        )}

        {stage === "form" && <IntakeForm onSubmit={handleSubmit} />}

        {stage === "loading" && (
          <div className="flex flex-col items-center gap-5 text-center">
            <div
              className="w-14 h-14 rounded-full animate-spin"
              style={{
                border: "3px solid var(--line)",
                borderTopColor: "var(--accent)",
              }}
            />
            <p className="text-sm" style={{ color: "var(--text-dim)" }}>
              Charting your sky and reading the season ahead…
            </p>
          </div>
        )}

        {stage === "result" && reading && (
          <ReadingResult reading={reading} onRestart={() => setStage("form")} />
        )}

        {stage === "error" && (
          <div className="flex flex-col items-center gap-5 text-center max-w-md">
            <h2 className="font-display text-3xl" style={{ color: "var(--text)" }}>
              We couldn&apos;t chart that
            </h2>
            <p className="text-sm" style={{ color: "var(--text-dim)" }}>{error}</p>
            <button
              onClick={() => setStage("form")}
              className="rounded-full px-6 py-3 text-sm font-semibold"
              style={{ background: "var(--surface)", border: "1px solid var(--line)", color: "var(--text)" }}
            >
              Try again
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
