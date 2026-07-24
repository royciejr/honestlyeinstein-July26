"use client";

import type { Child } from "@/lib/types";

export function ChildPicker({
  childrenList,
  selectedId,
  onSelect,
}: {
  childrenList: Child[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (childrenList.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {childrenList.map((child) => (
        <button
          key={child.id}
          onClick={() => onSelect(child.id)}
          className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
            child.id === selectedId
              ? "bg-indigo-600 text-white"
              : "bg-white text-slate-700 ring-1 ring-slate-300 hover:ring-indigo-400"
          }`}
        >
          {child.display_name}
        </button>
      ))}
    </div>
  );
}
