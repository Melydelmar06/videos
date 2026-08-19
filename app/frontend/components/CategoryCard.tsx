import { CategoryReading } from "@/lib/api";

const TIER_TOKEN: Record<CategoryReading["confidence"], string> = {
  "strong signal": "strong",
  notable: "notable",
  "minor undertone": "minor",
  quiet: "quiet",
};

export default function CategoryCard({ reading }: { reading: CategoryReading }) {
  const tier = TIER_TOKEN[reading.confidence];
  return (
    <article
      className="rounded-3xl p-7 sm:p-9 flex flex-col gap-4"
      style={{ background: "var(--surface)", border: "1px solid var(--line)" }}
    >
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <p
          className="text-[11px] uppercase tracking-[0.14em]"
          style={{ color: "var(--text-faint)" }}
        >
          {reading.label}
        </p>
        <span
          className="text-[11px] uppercase tracking-[0.08em] px-2.5 py-1 rounded-full whitespace-nowrap"
          style={{
            color: `var(--tier-${tier})`,
            background: `var(--tier-${tier}-soft)`,
          }}
        >
          {reading.confidence}
        </span>
      </div>
      <h3 className="font-display text-[28px] sm:text-[32px] leading-tight" style={{ color: "var(--text)" }}>
        {reading.headline}
      </h3>
      <div
        className="flex flex-col gap-3 text-[15px] leading-relaxed max-w-[62ch]"
        style={{ color: "var(--text-dim)" }}
      >
        {reading.body
          .split(/\n+/)
          .filter(Boolean)
          .map((para, i) => (
            <p key={i}>{para}</p>
          ))}
      </div>
    </article>
  );
}
