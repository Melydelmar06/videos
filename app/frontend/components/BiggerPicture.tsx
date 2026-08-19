import { BiggerPicture as BiggerPictureType } from "@/lib/api";

export default function BiggerPicture({ picture }: { picture: BiggerPictureType }) {
  return (
    <section
      className="rounded-3xl p-8 sm:p-10 flex flex-col gap-4"
      style={{
        background: "linear-gradient(155deg, var(--accent-soft), transparent 70%), var(--surface)",
        border: "1px solid var(--line)",
      }}
    >
      <p
        className="text-[11px] uppercase tracking-[0.16em]"
        style={{ color: "var(--accent)" }}
      >
        The bigger picture
      </p>
      <h2 className="font-display text-[32px] sm:text-[36px] leading-tight" style={{ color: "var(--text)" }}>
        {picture.headline}
      </h2>
      <div
        className="flex flex-col gap-3 text-[15.5px] leading-relaxed max-w-[64ch]"
        style={{ color: "var(--text-dim)" }}
      >
        {picture.body
          .split(/\n+/)
          .filter(Boolean)
          .map((para, i) => (
            <p key={i}>{para}</p>
          ))}
      </div>
    </section>
  );
}
