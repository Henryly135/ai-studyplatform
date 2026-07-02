import { describe, expect, it } from "vitest";

import type { Identity } from "../../types/auth";
import { getAllowedHomeSections } from "./homeConfig";

const sectionIdsFor = (identity: Identity) =>
  getAllowedHomeSections(identity).map((section) => section.id);

const sectionPathsFor = (identity: Identity) =>
  getAllowedHomeSections(identity).map((section) => section.path);

describe("home role section matrix", () => {
  it("keeps learner navigation focused on learning tasks", () => {
    expect(sectionIdsFor("Learner")).toEqual([
      "course-center",
      "my-courses",
      "progress",
      "communication",
      "ai",
    ]);
  });

  it("keeps educator navigation focused on owned course operations and teaching AI", () => {
    expect(sectionIdsFor("Educator")).toEqual([
      "course-center",
      "managed-courses",
      "analytics",
      "ai",
      "communication",
    ]);
  });

  it("keeps admin navigation focused on platform governance", () => {
    expect(sectionIdsFor("Admin")).toEqual([
      "course-center",
      "course-management",
      "user-management",
      "ai",
    ]);
  });

  it("does not expose management-only sections to learners or educators", () => {
    const adminOnlySections = [
      "course-management",
      "user-management",
    ];

    expect(sectionIdsFor("Learner")).not.toEqual(
      expect.arrayContaining(adminOnlySections)
    );
    expect(sectionIdsFor("Educator")).not.toEqual(
      expect.arrayContaining(adminOnlySections)
    );
  });

  it("uses stable unique ids and paths for every role", () => {
    const identities: Identity[] = ["Learner", "Educator", "Admin"];

    identities.forEach((identity) => {
      const sectionIds = sectionIdsFor(identity);
      const sectionPaths = sectionPathsFor(identity);

      expect(new Set(sectionIds).size).toBe(sectionIds.length);
      expect(new Set(sectionPaths).size).toBe(sectionPaths.length);
      expect(sectionPaths).not.toContain("");
    });
  });
});
