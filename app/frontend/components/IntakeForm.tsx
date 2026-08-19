"use client";

import { useEffect, useRef, useState } from "react";
import { geocode, GeocodeResult, ReadingRequest } from "@/lib/api";

export default function IntakeForm({
  onSubmit,
}: {
  onSubmit: (req: ReadingRequest) => void;
}) {
  const [name, setName] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [birthTime, setBirthTime] = useState("");
  const [placeQuery, setPlaceQuery] = useState("");
  const [placeOptions, setPlaceOptions] = useState<GeocodeResult[]>([]);
  const [place, setPlace] = useState<GeocodeResult | null>(null);
  const [showOptions, setShowOptions] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (place && placeQuery === place.label) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const results = await geocode(placeQuery);
        setPlaceOptions(results);
      } catch {
        setPlaceOptions([]);
      }
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [placeQuery]);

  const ready = name.trim().length > 0 && birthDate && birthTime && place;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!ready || !place) return;
    onSubmit({
      name: name.trim(),
      birth_date: birthDate,
      birth_time: `${birthTime}:00`,
      latitude: place.latitude,
      longitude: place.longitude,
      timezone_name: place.timezone,
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full max-w-md rounded-3xl p-8 sm:p-10 flex flex-col gap-6"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--line)",
        boxShadow: "0 30px 60px -30px rgba(36,31,46,0.25)",
      }}
    >
      <div>
        <p
          className="text-[11px] uppercase tracking-[0.16em] mb-2"
          style={{ color: "var(--accent)", fontFamily: "var(--font-body)" }}
        >
          Your details
        </p>
        <h2 className="font-display text-3xl" style={{ color: "var(--text)" }}>
          Cast your chart
        </h2>
      </div>

      <Field label="Name">
        <input
          className="field-input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="What should we call you?"
          maxLength={80}
          required
        />
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Birth date">
          <input
            className="field-input"
            type="date"
            value={birthDate}
            onChange={(e) => setBirthDate(e.target.value)}
            required
          />
        </Field>
        <Field label="Birth time">
          <input
            className="field-input"
            type="time"
            value={birthTime}
            onChange={(e) => setBirthTime(e.target.value)}
            required
          />
        </Field>
      </div>
      <p className="text-xs -mt-4" style={{ color: "var(--text-faint)" }}>
        As exact as you can — even a few minutes changes your rising sign and houses.
      </p>

      {/* Not a <Field>/<label> wrapper on purpose: a <label> implicitly
          re-focuses its associated control whenever anything inside it is
          clicked, including the dropdown's option buttons -- which would
          re-fire onFocus and reopen the dropdown right after a selection. */}
      <div className="flex flex-col gap-1.5">
        <span
          className="text-[11px] uppercase tracking-[0.1em]"
          style={{ color: "var(--text-faint)" }}
        >
          Birthplace
        </span>
        <div className="relative">
          <input
            className="field-input"
            value={placeQuery}
            onChange={(e) => {
              setPlaceQuery(e.target.value);
              setPlace(null);
              setShowOptions(true);
            }}
            onFocus={() => setShowOptions(true)}
            placeholder="City, country"
            aria-label="Birthplace"
            required
          />
          {showOptions && placeOptions.length > 0 && (
            <ul
              className="absolute z-10 mt-2 w-full rounded-2xl overflow-hidden max-h-56 overflow-y-auto"
              style={{
                background: "var(--surface)",
                border: "1px solid var(--line)",
                boxShadow: "0 20px 40px -20px rgba(36,31,46,0.3)",
              }}
            >
              {placeOptions.map((opt, i) => (
                <li key={i}>
                  <button
                    type="button"
                    className="w-full text-left px-4 py-3 text-sm transition-colors"
                    style={{ color: "var(--text)" }}
                    onClick={() => {
                      setPlace(opt);
                      setPlaceQuery(opt.label);
                      setShowOptions(false);
                    }}
                  >
                    {opt.label}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <button
        type="submit"
        disabled={!ready}
        className="mt-2 rounded-full py-3.5 text-sm font-semibold tracking-wide transition-opacity disabled:opacity-40"
        style={{
          background: "var(--accent)",
          color: "var(--surface)",
          fontFamily: "var(--font-body)",
        }}
      >
        Reveal my season ahead
      </button>

      <style jsx>{`
        .field-input {
          width: 100%;
          padding: 0.7rem 0.9rem;
          border-radius: 0.9rem;
          border: 1px solid var(--line);
          background: var(--surface-2);
          color: var(--text);
          font-family: var(--font-body);
          font-size: 0.95rem;
        }
        .field-input:focus {
          outline: none;
          border-color: var(--accent);
        }
      `}</style>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span
        className="text-[11px] uppercase tracking-[0.1em]"
        style={{ color: "var(--text-faint)" }}
      >
        {label}
      </span>
      {children}
    </label>
  );
}
