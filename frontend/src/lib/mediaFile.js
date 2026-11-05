import { MAX_UPLOAD_MB } from "../config/limits.js";

const ALLOWED_MEDIA_TYPES = new Set(["video/mp4", "audio/mpeg"]);

export function validateMediaFile(file) {
  if (!file) {
    return "Choose an MP4 or MP3 file.";
  }
  if (!ALLOWED_MEDIA_TYPES.has(file.type)) {
    return "Choose an MP4 or MP3 file.";
  }
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    return `Files must be ${MAX_UPLOAD_MB} MB or smaller.`;
  }
  return "";
}
