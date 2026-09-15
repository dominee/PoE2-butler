/**
 * NotificationBell — a bell icon button in the app header that shows the
 * count of undismissed admin notifications as a badge.  Clicking opens a
 * persistent dropdown panel where users can read and dismiss each notification.
 *
 * Notifications are fetched from GET /api/notifications (public, no auth) and
 * polled every 5 minutes.  Dismissed IDs are stored in Zustand (persisted to
 * localStorage) so they survive page reloads.
 */
import { useEffect, useRef, useState } from "react";

import type { AppNotification } from "@/api/types";
import { useNotifications } from "@/api/hooks";
import { useUIStore } from "@/store/uiStore";

// ── type-colour maps ─────────────────────────────────────────────────────────

const TYPE_BORDER: Record<string, string> = {
  info: "border-l-blue-500",
  warning: "border-l-amber-500",
  error: "border-l-red-500",
};

const TYPE_TITLE: Record<string, string> = {
  info: "text-blue-300",
  warning: "text-amber-300",
  error: "text-red-300",
};

const TYPE_ICON: Record<string, string> = {
  info: "ℹ",
  warning: "⚠",
  error: "✖",
};

// ── individual notification card ─────────────────────────────────────────────

function NotificationCard({
  notification,
  onDismiss,
}: {
  notification: AppNotification;
  onDismiss: (id: string) => void;
}) {
  const t = notification.notification_type;
  const borderClass = TYPE_BORDER[t] ?? TYPE_BORDER.info;
  const titleClass = TYPE_TITLE[t] ?? TYPE_TITLE.info;
  const icon = TYPE_ICON[t] ?? TYPE_ICON.info;

  return (
    <div
      role="alert"
      className={`relative rounded-sm border border-ink-700 border-l-2 bg-ink-900 px-3 py-2 text-sm ${borderClass}`}
    >
      <button
        aria-label="Dismiss notification"
        onClick={() => onDismiss(notification.id)}
        className="absolute right-2 top-2 text-[11px] text-ui-muted hover:text-parchment-100"
        title="Dismiss"
      >
        ✕
      </button>
      <p className={`mb-0.5 font-semibold leading-snug ${titleClass}`}>
        <span className="mr-1">{icon}</span>
        {notification.title}
      </p>
      <p className="pr-4 text-[12px] leading-snug text-parchment-200/80">
        {notification.message}
      </p>
    </div>
  );
}

// ── bell icon SVG ─────────────────────────────────────────────────────────────

function BellIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

// ── main exported component ───────────────────────────────────────────────────

/**
 * Renders a bell button for the app header.  Clicking toggles the notification
 * panel.  A numeric badge appears when there are undismissed notifications.
 */
export function NotificationBell() {
  const { data: notifications } = useNotifications();
  const dismissedIds = useUIStore((s) => s.dismissedNotificationIds);
  const dismissNotification = useUIStore((s) => s.dismissNotification);

  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const visible = (notifications ?? []).filter(
    (n: AppNotification) => !dismissedIds.includes(n.id),
  );
  const count = visible.length;

  // Close panel on click outside.
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  // Don't render the bell at all when there are no notifications ever loaded.
  if (!notifications?.length && count === 0) return null;

  return (
    <div ref={containerRef} className="relative">
      {/* Bell button */}
      <button
        type="button"
        aria-label={`Notifications${count > 0 ? ` (${count} unread)` : ""}`}
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
        className={[
          "btn-ghost relative flex h-8 w-8 items-center justify-center rounded",
          open ? "bg-ink-700/60 text-parchment-100" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        title="Notifications"
      >
        <BellIcon className="h-4.5 w-4.5" />
        {count > 0 && (
          <span
            aria-hidden
            className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-ember-500 px-0.5 text-[9px] font-bold leading-none text-white"
          >
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          className="absolute right-0 top-[calc(100%+8px)] z-[200] flex w-80 flex-col gap-1.5 rounded-lg border border-ink-600 bg-ink-950 p-2 shadow-2xl"
        >
          <h2 className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-widest text-parchment-50/60">
            Notifications
          </h2>
          {visible.length === 0 ? (
            <p className="px-1 py-2 text-[12px] text-ui-muted">
              No new notifications.
            </p>
          ) : (
            visible.map((n: AppNotification) => (
              <NotificationCard key={n.id} notification={n} onDismiss={dismissNotification} />
            ))
          )}
        </div>
      )}
    </div>
  );
}

// Keep legacy export name so any import of `NotificationToast` still resolves.
/** @deprecated Use NotificationBell instead. */
export const NotificationToast = NotificationBell;
