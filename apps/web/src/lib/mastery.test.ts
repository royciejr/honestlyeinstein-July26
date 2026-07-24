import { describe, expect, it } from "vitest";
import { masteryEmoji, masteryLabel, moduleCompletion } from "./mastery";

describe("masteryLabel", () => {
  it("maps levels to labels", () => {
    expect(masteryLabel(0)).toBe("Not started");
    expect(masteryLabel(1)).toBe("Learning");
    expect(masteryLabel(2)).toBe("Solid");
    expect(masteryLabel(3)).toBe("Mastered");
  });
});

describe("masteryEmoji", () => {
  it("never returns empty", () => {
    for (const level of [-1, 0, 1, 2, 3, 99]) {
      expect(masteryEmoji(level).length).toBeGreaterThan(0);
    }
  });
});

describe("moduleCompletion", () => {
  it("handles empty modules", () => {
    expect(moduleCompletion([])).toBe(0);
  });
  it("rounds the completed share", () => {
    expect(
      moduleCompletion([{ mastery_level: 1 }, { mastery_level: 0 }, { mastery_level: 2 }]),
    ).toBe(67);
  });
});
