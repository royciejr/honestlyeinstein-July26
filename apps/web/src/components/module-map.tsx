"use client";

import { masteryEmoji, masteryLabel, moduleCompletion } from "@/lib/mastery";
import type { Progress } from "@/lib/types";

export function ModuleMap({ progress }: { progress: Progress }) {
  if (progress.modules.length === 0) {
    return (
      <p className="text-slate-500">
        No modules yet — load the skill graph (see docs/RUNBOOK.md).
      </p>
    );
  }
  return (
    <ol className="space-y-4">
      {progress.modules.map((module) => (
        <li
          key={module.slug}
          className={`rounded-xl border bg-white p-4 shadow-sm ${
            module.unlocked ? "border-indigo-200" : "border-slate-200 opacity-60"
          }`}
        >
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">
              {module.unlocked ? "🌍" : "🔒"} {module.title}
            </h2>
            <span className="text-xs text-slate-500">
              {moduleCompletion(module.skills)}% complete
            </span>
          </div>
          <ul className="mt-3 flex flex-wrap gap-2">
            {module.skills.map((skill) => (
              <li
                key={skill.slug}
                title={`${masteryLabel(skill.mastery_level)} · elo ${skill.elo}`}
                className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700"
              >
                {masteryEmoji(skill.mastery_level)} {skill.title}
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ol>
  );
}
