import { CATEGORY_ORDER, Reading } from "@/lib/api";
import CategoryCard from "./CategoryCard";

function formatDate(iso: string) {
  return new Date(iso + "T00:00:00Z").toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

export default function ReadingResult({
  reading,
  onRestart,
}: {
  reading: Reading;
  onRestart: () => void;
}) {
  return (
    <div className="w-full max-w-2xl flex flex-col gap-10">
      <div className="flex flex-col gap-3 text-center">
        <p
          className="text-[11px] uppercase tracking-[0.16em]"
          style={{ color: "var(--accent)" }}
        >
          {formatDate(reading.window.start)} — {formatDate(reading.window.end)}
        </p>
        <h1 className="font-display text-4xl sm:text-5xl" style={{ color: "var(--text)" }}>
          Your season ahead
        </h1>
        <p className="text-sm" style={{ color: "var(--text-faint)" }}>
          {reading.natal_summary}
        </p>
      </div>

      <div className="flex flex-col gap-5">
        {CATEGORY_ORDER.map((key) => {
          const cat = reading.categories[key];
          if (!cat) return null;
          return <CategoryCard key={key} reading={cat} />;
        })}
      </div>

      <button
        onClick={onRestart}
        className="self-center text-sm underline underline-offset-4"
        style={{ color: "var(--text-faint)" }}
      >
        Read another chart
      </button>
    </div>
  );
}
