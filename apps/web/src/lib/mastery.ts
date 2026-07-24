// Pure display helpers (unit-tested with vitest).

export function masteryLabel(level: number): string {
  if (level <= 0) return "Not started";
  if (level === 1) return "Learning";
  if (level === 2) return "Solid";
  return "Mastered";
}

export function masteryEmoji(level: number): string {
  if (level <= 0) return "⚪";
  if (level === 1) return "🟡";
  if (level === 2) return "🟢";
  return "⭐";
}

/** Share of a module's skills at or above the Phase 1 mastery bar (level 1). */
export function moduleCompletion(skills: { mastery_level: number }[]): number {
  if (skills.length === 0) return 0;
  const done = skills.filter((s) => s.mastery_level >= 1).length;
  return Math.round((done / skills.length) * 100);
}
