import { CategoryReading } from "@/lib/api";

const TIER_TOKEN: Record<CategoryReading["confidence"], string> = {
  "strong signal": "strong",
  notable: "notable",
  "minor undertone": "minor",
  quiet: "quiet",
};

export default function CategoryCard({ reading }: { reading: CategoryReading }) {
  const tier = TIER_TOKEN[reading.confidence];
  const { why } = reading;

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

      <details className="group mt-1">
        <summary
          className="cursor-pointer select-none text-xs inline-flex items-center gap-1.5 w-fit"
          style={{ color: "var(--text-faint)" }}
        >
          <span className="underline underline-offset-4 decoration-dotted">
            Why am I seeing this?
          </span>
          <span className="transition-transform group-open:rotate-90">›</span>
        </summary>
        <dl
          className="mt-3 pt-3 text-xs flex flex-col gap-1.5"
          style={{ borderTop: "1px solid var(--line-soft)", color: "var(--text-faint)" }}
        >
          <Row label="Signal">
            <span style={{ color: `var(--tier-${tier})` }}>{capitalize(reading.confidence)}</span>
          </Row>
          <Row label="Timing systems">
            {why.independent_systems} independent {why.independent_systems === 1 ? "system" : "systems"}
          </Row>
          {why.main_window && <Row label="Main window">{why.main_window}</Row>}
          {why.themes_involved.length > 0 && (
            <Row label="Also shows up in">{why.themes_involved.join(" + ")}</Row>
          )}
        </dl>
      </details>
    </article>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      <dt className="w-32 shrink-0 uppercase tracking-[0.06em]" style={{ fontSize: "10.5px" }}>
        {label}
      </dt>
      <dd style={{ color: "var(--text-dim)" }}>{children}</dd>
    </div>
  );
}

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
