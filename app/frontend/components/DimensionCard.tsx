import { DimensionReading } from "@/lib/api";
import { TIER_TOKEN } from "@/lib/tier";

export default function DimensionCard({ dimension }: { dimension: DimensionReading }) {
  const tier = TIER_TOKEN[dimension.tier] ?? "quiet";
  return (
    <div
      className="rounded-2xl px-5 py-4 flex flex-col gap-1.5"
      style={{ background: "var(--surface)", border: "1px solid var(--line)" }}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-[11px] uppercase tracking-[0.1em]" style={{ color: "var(--text-faint)" }}>
          {dimension.label}
        </span>
        <span
          className="text-[10px] uppercase tracking-[0.06em] px-2 py-0.5 rounded-full whitespace-nowrap"
          style={{ color: `var(--tier-${tier})`, background: `var(--tier-${tier}-soft)` }}
        >
          {dimension.tier}
        </span>
      </div>
      <p className="text-sm leading-relaxed" style={{ color: "var(--text)" }}>
        {dimension.text}
      </p>
    </div>
  );
}
