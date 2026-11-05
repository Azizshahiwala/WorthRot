const VIDEO_ID_PATTERN = /^[A-Za-z0-9_-]{11}$/;

export function isValidYouTubeUrl(value) {
  if (typeof value !== "string" || !value.trim()) return false;

  try {
    const url = new URL(value.trim());
    const hostname = url.hostname.toLowerCase();
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.username ||
      url.password ||
      !["", "80", "443"].includes(url.port)
    ) {
      return false;
    }

    let videoId = "";
    if (hostname === "youtu.be" || hostname.endsWith(".youtu.be")) {
      videoId = url.pathname.split("/").filter(Boolean)[0] || "";
    } else if (
      hostname === "youtube.com" ||
      hostname.endsWith(".youtube.com")
    ) {
      if (url.pathname === "/watch") {
        videoId = url.searchParams.get("v") || "";
      } else {
        const parts = url.pathname.split("/").filter(Boolean);
        if (
          parts.length === 2 &&
          ["embed", "shorts", "live"].includes(parts[0])
        ) {
          videoId = parts[1];
        }
      }
    }
    return VIDEO_ID_PATTERN.test(videoId);
  } catch {
    return false;
  }
}
