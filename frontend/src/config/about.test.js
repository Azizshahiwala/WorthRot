import { describe, expect, it } from "vitest";
import { about } from "./about.js";

describe("about content", () => {
  it("exports each required section", () => {
    expect(about).toHaveProperty("hero");
    expect(about).toHaveProperty("steps");
    expect(about).toHaveProperty("principles");
    expect(about).toHaveProperty("limits");
    expect(about).toHaveProperty("builtWith");
    expect(about).toHaveProperty("author");
  });

  it("contains exactly three consecutively numbered steps", () => {
    expect(about.steps).toHaveLength(3);
    expect(about.steps.map((step) => step.number)).toEqual([1, 2, 3]);
  });

  it("has no empty required copy", () => {
    const requiredCopy = [
      about.hero.title,
      about.hero.subtitle,
      ...Object.values(about.sectionTitles),
      ...about.steps.flatMap((step) => [
        step.title,
        step.description,
      ]),
      ...about.principles.flatMap((principle) => [
        principle.title,
        principle.description,
      ]),
      ...about.limits,
      about.builtWith,
      about.author.githubLabel,
      about.author.projectRepoLabel,
    ];

    expect(requiredCopy.every((copy) => copy.trim().length > 0)).toBe(true);
  });

  it("keeps author links empty or HTTPS URLs", () => {
    for (const field of ["githubUrl", "projectRepoUrl"]) {
      const link = about.author[field];
      expect(typeof link).toBe("string");
      if (link) {
        expect(new URL(link).protocol).toBe("https:");
      }
    }
  });

  it("states the upload privacy behavior and media limits", () => {
    expect(
      about.principles.find(({ title }) => title === "Private by default")
        .description,
    ).toBe("No accounts, no cookies. Uploaded files are deleted after processing.");
    expect(about.limits).toContain(
      "The Other tab accepts MP4 and MP3 files up to a size and length cap.",
    );
  });
});
