/**
 * When GGG does not send ``extended.mods`` magnitudes, show a best-effort range
 * read from the mod string (e.g. *Adds 5 to 12 …*).
 */

const TO_RE = /(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)/i;
const DASH_RE = /(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)/;

/** Human label like ``5 – 12`` for display, or null. */
export function modTextRangeHint(mod: string): string | null {
  const t = TO_RE.exec(mod);
  if (t) {
    return `${t[1]} – ${t[2]}`;
  }
  const d = DASH_RE.exec(mod);
  if (d) {
    return `${d[1]} – ${d[2]}`;
  }
  return null;
}
