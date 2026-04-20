/**
 * PoE2 mod text helpers.
 *
 * The GGG API embeds tag annotations in modifier strings, e.g.:
 *   "+171 to [Accuracy|Accuracy] Rating"
 *   "[Gain] 10% of [ElementalDamage|Elemental Damage] as Extra [Cold] Damage"
 *
 * Syntax:
 *   [InternalId|Human label]  → render "Human label"
 *   [InternalId]              → render "InternalId" (single-word tags, element types, etc.)
 */

/** Strip GGG tag annotations, returning plain display text. */
export function stripTags(text: string): string {
  return text
    .replace(/\[([^\]|]+)\|([^\]]+)\]/g, (_m, _id, display: string) => display)
    .replace(/\[([^\]]+)\]/g, (_m, id: string) => id);
}

/** A text run: either a plain string or a numeric value to be highlighted. */
export interface ModPart {
  text: string;
  isNum: boolean;
}

/**
 * Split a (already tag-stripped) mod string into plain/numeric runs.
 * Numbers include optional sign, decimal part, damage ranges (120-280) and
 * percentage suffix, e.g.: `+171`, `-15%`, `120-280`, `24.5%`.
 */
const NUM_RE = /([+-]?\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?%?)/g;

export function parseModParts(raw: string): ModPart[] {
  const text = stripTags(raw);
  const parts: ModPart[] = [];
  let last = 0;
  const re = new RegExp(NUM_RE.source, "g");
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      parts.push({ text: text.slice(last, match.index), isNum: false });
    }
    parts.push({ text: match[0], isNum: true });
    last = match.index + match[0].length;
  }
  if (last < text.length) {
    parts.push({ text: text.slice(last), isNum: false });
  }
  return parts;
}
