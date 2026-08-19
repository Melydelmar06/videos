"use client";

export type Tab = "today" | "season" | "journal" | "patterns";

const TABS: { key: Tab; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "season", label: "Season" },
  { key: "journal", label: "Journal" },
  { key: "patterns", label: "Patterns" },
];

export default function BottomNav({ active, onChange }: { active: Tab; onChange: (tab: Tab) => void }) {
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 flex justify-center px-6 pb-6 pt-2"
      style={{ zIndex: 20 }}
    >
      <div
        className="flex gap-1 rounded-full p-1.5"
        style={{ background: "var(--surface)", border: "1px solid var(--line)", boxShadow: "0 12px 30px -12px rgba(36,31,46,0.3)" }}
      >
        {TABS.map((tab) => {
          const isActive = tab.key === active;
          return (
            <button
              key={tab.key}
              onClick={() => onChange(tab.key)}
              className="px-5 py-2.5 rounded-full text-sm font-medium transition-colors"
              style={{
                background: isActive ? "var(--accent)" : "transparent",
                color: isActive ? "var(--surface)" : "var(--text-dim)",
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
