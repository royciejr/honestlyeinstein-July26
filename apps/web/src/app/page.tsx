"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useApi } from "@/lib/api";
import type { Child, Progress } from "@/lib/types";
import { ChildPicker } from "@/components/child-picker";
import { ModuleMap } from "@/components/module-map";

export default function HomePage() {
  const { request } = useApi();
  const [childrenList, setChildrenList] = useState<Child[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    request<Child[]>("/children")
      .then((kids) => {
        setChildrenList(kids);
        if (kids.length > 0) setSelectedId(kids[0].id);
      })
      .catch((e) => setError(String(e.message ?? e)));
  }, [request]);

  const loadProgress = useCallback(
    (childId: string) => {
      setProgress(null);
      request<Progress>(`/children/${childId}/progress`)
        .then(setProgress)
        .catch((e) => setError(String(e.message ?? e)));
    },
    [request],
  );

  useEffect(() => {
    if (selectedId) loadProgress(selectedId);
  }, [selectedId, loadProgress]);

  if (error) {
    return (
      <div className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
        Couldn&apos;t reach the API: {error}
      </div>
    );
  }
  if (childrenList === null) return <p className="text-slate-500">Loading…</p>;
  if (childrenList.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
        <p className="mb-3 text-slate-600">No child profiles yet.</p>
        <Link
          href="/children"
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white"
        >
          Add your first child
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <ChildPicker
        childrenList={childrenList}
        selectedId={selectedId}
        onSelect={setSelectedId}
      />
      {progress ? <ModuleMap progress={progress} /> : <p className="text-slate-500">Loading map…</p>}
    </div>
  );
}
