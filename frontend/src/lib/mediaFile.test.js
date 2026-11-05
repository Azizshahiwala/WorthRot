import { describe, expect, it } from "vitest";
import { MAX_UPLOAD_MB } from "../config/limits.js";
import { validateMediaFile } from "./mediaFile.js";

describe("validateMediaFile", () => {
  it("allows MP4 and MP3 files within the configured size", () => {
    expect(
      validateMediaFile(new File(["video"], "clip.mp4", { type: "video/mp4" })),
    ).toBe("");
    expect(
      validateMediaFile(new File(["audio"], "clip.mp3", { type: "audio/mpeg" })),
    ).toBe("");
  });

  it("rejects unsupported types and oversized files", () => {
    expect(
      validateMediaFile(new File(["image"], "photo.png", { type: "image/png" })),
    ).toMatch(/MP4 or MP3/);
    const bytes = new Uint8Array(MAX_UPLOAD_MB * 1024 * 1024 + 1);
    expect(
      validateMediaFile(
        new File([bytes], "too-large.mp4", { type: "video/mp4" }),
      ),
    ).toMatch(`${MAX_UPLOAD_MB} MB`);
  });

  it("requires a file", () => {
    expect(validateMediaFile(null)).toMatch(/Choose an MP4 or MP3/);
  });
});
