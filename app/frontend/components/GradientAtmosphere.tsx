export default function GradientAtmosphere() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 overflow-hidden"
      style={{ zIndex: 0 }}
    >
      <div
        className="absolute rounded-full"
        style={{
          width: "56vmax",
          height: "56vmax",
          top: "-22vmax",
          left: "-16vmax",
          background:
            "radial-gradient(circle at 35% 35%, var(--orb-rose), transparent 60%)",
          filter: "blur(70px)",
          opacity: 0.55,
        }}
      />
      <div
        className="absolute rounded-full"
        style={{
          width: "48vmax",
          height: "48vmax",
          top: "-10vmax",
          right: "-18vmax",
          background:
            "radial-gradient(circle at 60% 40%, var(--orb-gold), transparent 62%)",
          filter: "blur(70px)",
          opacity: 0.45,
        }}
      />
      <div
        className="absolute rounded-full"
        style={{
          width: "50vmax",
          height: "50vmax",
          top: "8vmax",
          left: "20vmax",
          background:
            "radial-gradient(circle at 50% 50%, var(--orb-lavender), transparent 60%)",
          filter: "blur(80px)",
          opacity: 0.35,
        }}
      />
      <div
        className="absolute rounded-full"
        style={{
          width: "40vmax",
          height: "40vmax",
          top: "2vmax",
          left: "-6vmax",
          background:
            "radial-gradient(circle at 50% 50%, var(--orb-teal), transparent 62%)",
          filter: "blur(75px)",
          opacity: 0.3,
        }}
      />
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(180deg, transparent 0%, var(--bg) 62%)",
        }}
      />
    </div>
  );
}
