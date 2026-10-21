/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import { buildStudentProfiles, STUDENT_ARCHETYPE_IDS } from "@/lib/acceptance/student-profiles";
import {
  simulateStudentProfile,
  summarizeMatrix,
} from "@/lib/acceptance/student-profile-simulation";

describe("100-student generic product matrix", () => {
  const profiles = buildStudentProfiles(100);

  it("covers every archetype at least once", () => {
    const seen = new Set(profiles.map((p) => p.archetype));
    for (const id of STUDENT_ARCHETYPE_IDS) {
      expect(seen.has(id)).toBe(true);
    }
  });

  it("passes all simulation dimensions for every profile", () => {
    const summary = summarizeMatrix(profiles);
    const failed = [...summary.profilePass.entries()].filter(([, ok]) => !ok);
    if (failed.length) {
      const sample = failed.slice(0, 3).map(([id]) => {
        const profile = profiles.find((p) => p.id === id)!;
        return {
          id,
          archetype: profile.archetype,
          failures: simulateStudentProfile(profile).filter((c) => !c.pass),
        };
      });
      expect(sample).toEqual([]);
    }
    expect(summary.passedCells).toBe(summary.totalCells);
    expect(summary.profilePass.size).toBe(100);
    expect([...summary.profilePass.values()].every(Boolean)).toBe(true);
  }, 60_000);
});
