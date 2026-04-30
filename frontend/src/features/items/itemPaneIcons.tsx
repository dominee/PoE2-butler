/** Small stroke icons for item detail pane and image export actions (`currentColor`). */

const c = "h-4 w-4 shrink-0";

export function IconClose({ className }: { className?: string }) {
  return (
    <svg
      className={`${c} ${className ?? ""}`.trim()}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M18 6L6 18M6 6l12 12" />
    </svg>
  );
}

export function IconLinkShare({ className }: { className?: string }) {
  return (
    <svg
      className={`${c} ${className ?? ""}`.trim()}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M10 13a5 5 0 0 0 7.07 0l1.42-1.42a5 5 0 0 0-7.07-7.07l-.74.74" />
      <path d="M14 11a5 5 0 0 0-7.07 0L5.5 12.42a5 5 0 0 0 7.07 7.07l.74-.74" />
    </svg>
  );
}

export function IconLinkOff({ className }: { className?: string }) {
  return (
    <svg
      className={`${c} ${className ?? ""}`.trim()}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M9 17H7A5 5 0 0 1 7 7" />
      <path d="M15 7h2a5 5 0 0 1 4 8M9 17l8-8" />
      <line x1="4" y1="4" x2="20" y2="20" />
    </svg>
  );
}

export function IconClipboard({ className }: { className?: string }) {
  return (
    <svg
      className={`${c} ${className ?? ""}`.trim()}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <rect x="8" y="2" width="8" height="4" rx="1" />
      <path d="M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2" />
      <path d="M8 12h8M8 16h6" />
    </svg>
  );
}

export function IconSave({ className }: { className?: string }) {
  return (
    <svg
      className={`${c} ${className ?? ""}`.trim()}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
      <polyline points="17 21 17 13 7 13 7 21" />
      <polyline points="7 3 7 8 15 8" />
    </svg>
  );
}

export function IconSearchExact({ className }: { className?: string }) {
  return (
    <svg
      className={`${c} ${className ?? ""}`.trim()}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <circle cx="11" cy="11" r="8" />
      <path d="M21 21l-4.3-4.3" />
    </svg>
  );
}

export function IconChevronsUp({ className }: { className?: string }) {
  return (
    <svg
      className={`${c} ${className ?? ""}`.trim()}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="m17 11-5-5-5 5M17 18l-5-5-5 5" />
    </svg>
  );
}

/** Compact / detail PNG copy actions (slightly smaller for paired toolbar). */
export function IconImageExport({ className }: { className?: string }) {
  const s = "h-3.5 w-3.5 shrink-0";
  return (
    <svg
      className={`${s} ${className ?? ""}`.trim()}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <circle cx="8.5" cy="10" r="1.5" fill="currentColor" stroke="none" />
      <path d="m21 15-3.5-3.5a2 2 0 0 0-2.83 0L10 17" />
    </svg>
  );
}
