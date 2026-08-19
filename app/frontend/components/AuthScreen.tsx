"use client";

import { useState } from "react";
import { consumeMagicLink, requestMagicLink } from "@/lib/api";
import { setSessionToken } from "@/lib/session";

export default function AuthScreen({ onSignedIn }: { onSignedIn: () => void }) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    setError("");
    try {
      const link = await requestMagicLink(email.trim());
      if (link.dev_mode && link.dev_magic_token) {
        // Dev mode: no mail sender is configured, so the link is handed
        // back directly instead of emailed -- sign in immediately rather
        // than making the user paste a token by hand.
        const session = await consumeMagicLink(link.dev_magic_token);
        setSessionToken(session.session_token);
        onSignedIn();
        return;
      }
      setStatus("idle");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setStatus("error");
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full max-w-md rounded-3xl p-8 sm:p-10 flex flex-col gap-6"
      style={{ background: "var(--surface)", border: "1px solid var(--line)", boxShadow: "0 30px 60px -30px rgba(36,31,46,0.25)" }}
    >
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] mb-2" style={{ color: "var(--accent)" }}>
          Sign in
        </p>
        <h2 className="font-display text-3xl" style={{ color: "var(--text)" }}>
          What&apos;s your email?
        </h2>
        <p className="text-sm mt-2" style={{ color: "var(--text-faint)" }}>
          No password — we&apos;ll send a link to sign in.
        </p>
      </div>

      <input
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@example.com"
        className="w-full px-4 py-3 rounded-2xl text-sm"
        style={{ background: "var(--surface-2)", border: "1px solid var(--line)", color: "var(--text)" }}
      />

      {error && <p className="text-sm" style={{ color: "var(--tier-strong)" }}>{error}</p>}

      <button
        type="submit"
        disabled={status === "loading" || !email.trim()}
        className="rounded-full py-3.5 text-sm font-semibold tracking-wide disabled:opacity-40"
        style={{ background: "var(--accent)", color: "var(--surface)" }}
      >
        {status === "loading" ? "Signing in…" : "Continue"}
      </button>

      <p className="text-xs text-center" style={{ color: "var(--text-faint)" }}>
        Dev mode: no email sender is configured yet, so this signs you in instantly.
      </p>
    </form>
  );
}
