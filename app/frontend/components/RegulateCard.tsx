import { RegulateRecommendation } from "@/lib/api";

const PRACTICE_LABELS: Record<string, string> = {
  guided_meditation: "Guided meditation",
  breathing_exercise: "Breathing exercise",
  grounding_exercise: "Grounding exercise",
  journaling_prompt: "Journaling prompt",
  visualization: "Visualization",
  manifestation_intention: "Intention practice",
  affirmation: "Affirmation",
  movement: "Movement",
  rest_recovery: "Rest & recovery",
  creative_exercise: "Creative exercise",
  relationship_reflection: "Relationship reflection",
  gratitude: "Gratitude practice",
  nervous_system_regulation: "Nervous-system regulation",
  practical_behavioral_suggestion: "A practical suggestion",
  planning_action: "Planning & action",
  exploration: "Exploration",
};

export default function RegulateCard({ recommendation }: { recommendation: RegulateRecommendation }) {
  return (
    <div
      className="rounded-3xl p-6 sm:p-7 flex flex-col gap-3"
      style={{ background: "var(--surface)", border: "1px solid var(--line)" }}
    >
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-[11px] uppercase tracking-[0.14em]" style={{ color: "var(--accent)" }}>
          What might help today
        </p>
        <span className="text-[10px] uppercase tracking-[0.06em]" style={{ color: "var(--text-faint)" }}>
          {PRACTICE_LABELS[recommendation.practice_type] ?? recommendation.practice_type}
        </span>
      </div>
      <h3 className="font-display text-2xl" style={{ color: "var(--text)" }}>
        {recommendation.practice_title}
      </h3>
      <p className="text-sm leading-relaxed" style={{ color: "var(--text-dim)" }}>
        {recommendation.intro}
      </p>
      <div
        className="flex flex-col gap-2 text-sm leading-relaxed mt-1 pt-4"
        style={{ color: "var(--text)", borderTop: "1px solid var(--line-soft)" }}
      >
        {recommendation.practice_body
          .split(/\n+/)
          .filter(Boolean)
          .map((para, i) => (
            <p key={i}>{para}</p>
          ))}
      </div>
    </div>
  );
}
