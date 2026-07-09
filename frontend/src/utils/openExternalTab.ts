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
