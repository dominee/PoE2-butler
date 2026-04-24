const POE_CDN_HOST = "web.poecdn.com";

/**
 * Re-write official PoE CDNs to our API proxy so canvas/html-to-image can
 * read pixels. Cross-origin GGG images without CORS taint the canvas; with
 * `crossOrigin=anonymous` they often fail to load (no CORS on poecdn).
 * Same-origin proxy avoids both.
 */
export function itemIconForCanvasProxy(icon: string | null | undefined): string | null {
  if (!icon?.trim()) {
    return null;
  }
  const trimmed = icon.trim();
  try {
    const u = new URL(trimmed);
    if (u.protocol !== "https:" || u.hostname.toLowerCase() !== POE_CDN_HOST) {
      return icon;
    }
  } catch {
    return icon;
  }
  return `/api/cdn/poecdn?u=${encodeURIComponent(trimmed)}`;
}
