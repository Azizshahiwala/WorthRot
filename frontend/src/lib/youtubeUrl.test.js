import { describe, expect, it } from "vitest";
import { isValidYouTubeUrl } from "./youtubeUrl.js";

describe("isValidYouTubeUrl", () => {
  it.each([
    "https://www.youtube.com/watch?v=abcdefghijk",
    "https://youtu.be/abcdefghijk",
    "https://youtube.com/shorts/abcdefghijk",
  ])("accepts a YouTube video URL: %s", (url) => {
    expect(isValidYouTubeUrl(url)).toBe(true);
  });

  it.each([
    "https://youtube.com.evil.test/watch?v=abcdefghijk",
    "https://example.com/watch?v=abcdefghijk",
    "https://youtube.com/watch?v=short",
    "not a URL",
  ])("rejects an invalid video URL: %s", (url) => {
    expect(isValidYouTubeUrl(url)).toBe(false);
  });
});
