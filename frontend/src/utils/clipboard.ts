/**
 * Copy plain text. Uses the Clipboard API in secure contexts; on plain HTTP
 * (e.g. dev hostnames that are not localhost) `navigator.clipboard` is
 * undefined — fall back to `document.execCommand('copy')` from a user gesture.
 */
export async function copyTextToClipboard(text: string): Promise<void> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // e.g. NotAllowedError — try legacy path
    }
  }

  if (typeof document === "undefined") {
    throw new Error("no_document");
  }

  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.setAttribute("aria-hidden", "true");
  ta.style.position = "fixed";
  ta.style.left = "0";
  ta.style.top = "0";
  ta.style.width = "1px";
  ta.style.height = "1px";
  ta.style.padding = "0";
  ta.style.border = "none";
  ta.style.margin = "0";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  ta.setSelectionRange(0, text.length);
  const ok = document.execCommand("copy");
  document.body.removeChild(ta);
  if (!ok) {
    throw new Error("copy_failed");
  }
}
