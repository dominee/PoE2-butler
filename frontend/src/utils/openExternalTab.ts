/** Open a placeholder tab synchronously so popup blockers allow navigation after async work. */
export function prepareExternalTab(): Window | null {
  const tab = window.open("about:blank", "_blank");
  if (tab) {
    try {
      tab.opener = null;
    } catch {
      // noopener equivalent; may fail after cross-origin navigation
    }
  }
  return tab;
}

/**
 * Write a minimal loading page into a tab opened by `prepareExternalTab`.
 * Call this immediately after `prepareExternalTab()` so the user sees feedback
 * while the async trade-search POST completes.
 */
export function showExternalTabLoading(tab: Window | null, message: string): void {
  if (!tab || tab.closed) return;
  try {
    const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Opening PoE2 Trade…</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0d0f14;color:#c8b99a;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;flex-direction:column;gap:1rem}
  .spinner{width:2rem;height:2rem;border:3px solid #2a2e3a;border-top-color:#c84b1a;border-radius:50%;animation:spin .8s linear infinite}
  @keyframes spin{to{transform:rotate(360deg)}}
  p{font-size:.95rem;opacity:.75}
</style>
</head>
<body>
<div class="spinner"></div>
<p>${message.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</p>
</body>
</html>`;
    tab.document.open();
    tab.document.write(html);
    tab.document.close();
  } catch {
    // May fail if tab was closed or cross-origin restrictions apply; ignore
  }
}

/** Navigate a tab from prepareExternalTab; falls back to a direct window.open. */
export function navigateExternalTab(tab: Window | null, url: string): boolean {
  if (tab && !tab.closed) {
    try {
      tab.location.href = url;
      return true;
    } catch {
      // tab blocked or detached
    }
  }
  const fallback = window.open(url, "_blank", "noopener,noreferrer");
  return fallback !== null;
}

export function closeExternalTab(tab: Window | null): void {
  if (tab && !tab.closed) {
    try {
      tab.close();
    } catch {
      // ignore
    }
  }
}
