"use client";

import { FormEvent, useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import type { Child } from "@/lib/types";

export default function ChildrenPage() {
  const { request } = useApi();
  const [childrenList, setChildrenList] = useState<Child[]>([]);
  const [displayName, setDisplayName] = useState("");
  const [country, setCountry] = useState<"UK" | "US">("UK");
  const [yearBand, setYearBand] = useState("Y4");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    request<Child[]>("/children").then(setChildrenList).catch((e) => setError(String(e.message)));
  }, [request]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const child = await request<Child>("/children", {
        method: "POST",
        body: JSON.stringify({ display_name: displayName, country, year_band: yearBand }),
      });
      setChildrenList((prev) => [...prev, child]);
      setDisplayName("");
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Child profiles</h1>

      <ul className="space-y-2">
        {childrenList.map((child) => (
          <li key={child.id} className="rounded-lg border border-slate-200 bg-white px-4 py-3">
            <span className="font-medium">{child.display_name}</span>{" "}
            <span className="text-sm text-slate-500">
              · {child.country} {child.year_band ?? ""}
            </span>
          </li>
        ))}
        {childrenList.length === 0 && (
          <li className="text-sm text-slate-500">None yet — add one below.</li>
        )}
      </ul>

      <form onSubmit={onSubmit} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="font-semibold">Add a child</h2>
        <p className="text-xs text-slate-500">
          First name or nickname only — this is the only personal detail stored.
        </p>
        <input
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Display name"
          required
          maxLength={80}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <div className="flex gap-3">
          <select
            value={country}
            onChange={(e) => setCountry(e.target.value as "UK" | "US")}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="UK">UK</option>
            <option value="US">US</option>
          </select>
          <select
            value={yearBand}
            onChange={(e) => setYearBand(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            {(country === "UK" ? ["Y4", "Y5", "Y6"] : ["G3", "G4", "G5"]).map((band) => (
              <option key={band} value={band}>
                {band}
              </option>
            ))}
          </select>
          <button
            disabled={busy || !displayName.trim()}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {busy ? "Adding…" : "Add"}
          </button>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>
    </div>
  );
}
