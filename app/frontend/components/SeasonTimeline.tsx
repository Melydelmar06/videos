import { Timeline } from "@/lib/api";

const STEPS: { key: keyof Timeline; label: string }[] = [
  { key: "now", label: "Now" },
  { key: "next", label: "Next 1–2 months" },
  { key: "later", label: "Later in the season" },
];

export default function SeasonTimeline({ timeline }: { timeline: Timeline }) {
  const active = STEPS.filter((s) => timeline[s.key]);
  if (active.length === 0) return null;

  return (
    <section className="flex flex-col gap-5">
      <p
        className="text-[11px] uppercase tracking-[0.16em] text-center"
        style={{ color: "var(--text-faint)" }}
      >
        How it unfolds
      </p>
      <div className="flex flex-col pl-1" style={{ borderLeft: "2px solid var(--line)" }}>
        {active.map((step) => (
          <div key={step.key} className="relative pl-6 pb-7 last:pb-0">
            <span
              className="absolute rounded-full"
              style={{
                left: "-7px",
                top: "3px",
                width: "10px",
                height: "10px",
                background: "var(--bg)",
                border: "2px solid var(--accent)",
              }}
            />
            <p
              className="text-[11px] uppercase tracking-[0.08em] mb-1.5"
              style={{ color: "var(--accent)" }}
            >
              {step.label}
            </p>
            <p className="text-sm leading-relaxed max-w-[56ch]" style={{ color: "var(--text-dim)" }}>
              {timeline[step.key]}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
