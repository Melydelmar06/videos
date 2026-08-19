export default function PatternsScreen() {
  return (
    <div className="w-full max-w-md flex flex-col items-center text-center gap-4 pb-28 py-16">
      <p className="text-[11px] uppercase tracking-[0.16em]" style={{ color: "var(--accent)" }}>Patterns</p>
      <h1 className="font-display text-3xl" style={{ color: "var(--text)" }}>
        Not enough data yet
      </h1>
      <p className="text-sm leading-relaxed" style={{ color: "var(--text-dim)" }}>
        This is where Aphelion will eventually show you whether the astrological model actually
        tracks your own experience — or where it doesn&apos;t. That takes a real stretch of
        check-ins to say honestly, so keep checking in and come back here in a few weeks.
      </p>
    </div>
  );
}
