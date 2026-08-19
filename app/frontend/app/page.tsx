"use client";

import { useEffect, useState } from "react";
import AuthScreen from "@/components/AuthScreen";
import BottomNav, { Tab } from "@/components/BottomNav";
import GradientAtmosphere from "@/components/GradientAtmosphere";
import IntakeForm from "@/components/IntakeForm";
import JournalScreen from "@/screens/JournalScreen";
import PatternsScreen from "@/screens/PatternsScreen";
import SeasonScreen from "@/screens/SeasonScreen";
import TodayScreen from "@/screens/TodayScreen";
import { ReadingRequest, saveProfile } from "@/lib/api";
import { clearSessionToken, getSessionToken } from "@/lib/session";

type Stage = "loading" | "auth" | "onboarding" | "app";

export default function Home() {
  const [stage, setStage] = useState<Stage>("loading");
  const [tab, setTab] = useState<Tab>("today");
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileError, setProfileError] = useState("");

  useEffect(() => {
    if (!getSessionToken()) {
      setStage("auth");
      return;
    }
    checkProfile();
  }, []);

  async function checkProfile() {
    try {
      const { getProfileStatus } = await import("@/lib/api");
      const status = await getProfileStatus();
      setStage(status.has_profile ? "app" : "onboarding");
    } catch {
      clearSessionToken();
      setStage("auth");
    }
  }

  async function handleOnboardingSubmit(req: ReadingRequest) {
    setSavingProfile(true);
    setProfileError("");
    try {
      await saveProfile(req);
      setStage("app");
    } catch (e) {
      setProfileError(e instanceof Error ? e.message : "Something went wrong.");
      setSavingProfile(false);
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden">
      <GradientAtmosphere />

      <div className="relative flex flex-col items-center px-6 py-16 sm:py-24" style={{ zIndex: 1 }}>
        <nav className="w-full max-w-5xl flex items-center justify-between mb-16 sm:mb-24">
          <span className="font-display text-xl" style={{ color: "var(--text)" }}>aphelion</span>
          <span className="hidden sm:inline text-[11px] uppercase tracking-[0.14em]" style={{ color: "var(--text-faint)" }}>
            a personal operating system for your inner life
          </span>
        </nav>

        {stage === "loading" && (
          <div className="w-10 h-10 rounded-full animate-spin" style={{ border: "3px solid var(--line)", borderTopColor: "var(--accent)" }} />
        )}

        {stage === "auth" && <AuthScreen onSignedIn={checkProfile} />}

        {stage === "onboarding" && (
          <div className="flex flex-col items-center gap-4">
            <IntakeForm onSubmit={handleOnboardingSubmit} />
            {savingProfile && <p className="text-sm" style={{ color: "var(--text-dim)" }}>Casting your chart…</p>}
            {profileError && <p className="text-sm" style={{ color: "var(--tier-strong)" }}>{profileError}</p>}
          </div>
        )}

        {stage === "app" && (
          <>
            {tab === "today" && <TodayScreen />}
            {tab === "season" && <SeasonScreen />}
            {tab === "journal" && <JournalScreen />}
            {tab === "patterns" && <PatternsScreen />}
            <BottomNav active={tab} onChange={setTab} />
          </>
        )}
      </div>
    </main>
  );
}
