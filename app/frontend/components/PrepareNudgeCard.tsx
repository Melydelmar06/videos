import { PrepareNudge } from "@/lib/api";

export default function PrepareNudgeCard({ nudge }: { nudge: PrepareNudge }) {
  if (!("message" in nudge) || !nudge.message) return null;
  return (
    <div
      className="rounded-3xl p-6 sm:p-7 flex flex-col gap-2"
      style={{
        background: "linear-gradient(155deg, var(--accent-soft), transparent 70%), var(--surface)",
        border: "1px solid var(--line)",
      }}
    >
      <p className="text-[11px] uppercase tracking-[0.14em]" style={{ color: "var(--accent)" }}>
        What&apos;s ahead — {nudge.days_away} {nudge.days_away === 1 ? "day" : "days"} away
      </p>
      <p className="text-sm leading-relaxed" style={{ color: "var(--text)" }}>
        {nudge.message}
      </p>
    </div>
  );
}
