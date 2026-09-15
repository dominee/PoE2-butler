/**
 * NotificationToast — fixed bottom-right panel showing admin-managed
 * persistent app notifications. Users dismiss them individually; dismissed IDs
 * are stored in Zustand (persisted to localStorage).
 */
import type { AppNotification } from "@/api/types";
import { useNotifications } from "@/api/hooks";
import { useUIStore } from "@/store/uiStore";

const TYPE_STYLES: Record<string, string> = {
  info: "border-blue-500/60 bg-blue-950/90",
  warning: "border-amber-500/60 bg-amber-950/90",
  error: "border-red-500/60 bg-red-950/90",
};

const TYPE_TITLE_STYLES: Record<string, string> = {
  info: "text-blue-300",
  warning: "text-amber-300",
  error: "text-red-300",
};

const TYPE_ICONS: Record<string, string> = {
  info: "ℹ",
  warning: "⚠",
  error: "✖",
};

function NotificationCard({
  notification,
  onDismiss,
}: {
  notification: AppNotification;
  onDismiss: (id: string) => void;
}) {
  const t = notification.notification_type;
  const borderClass = TYPE_STYLES[t] ?? TYPE_STYLES.info;
  const titleClass = TYPE_TITLE_STYLES[t] ?? TYPE_TITLE_STYLES.info;
  const icon = TYPE_ICONS[t] ?? TYPE_ICONS.info;

  return (
    <div
      role="alert"
      className={`relative rounded border p-3 text-sm shadow-lg backdrop-blur ${borderClass}`}
    >
      <button
        aria-label="Dismiss notification"
        onClick={() => onDismiss(notification.id)}
        className="absolute right-2 top-2 text-ui-muted hover:text-parchment-100"
      >
        ✕
      </button>
      <p className={`mb-1 font-semibold ${titleClass}`}>
        <span className="mr-1.5">{icon}</span>
        {notification.title}
      </p>
      <p className="pr-4 text-parchment-200/80">{notification.message}</p>
    </div>
  );
}

export function NotificationToast() {
  const { data: notifications } = useNotifications();
  const dismissedIds = useUIStore((s) => s.dismissedNotificationIds);
  const dismissNotification = useUIStore((s) => s.dismissNotification);

  const visible = (notifications ?? []).filter(
    (n: AppNotification) => !dismissedIds.includes(n.id),
  );

  if (visible.length === 0) return null;

  return (
    <div
      aria-live="polite"
      className="fixed bottom-4 right-4 z-50 flex max-h-[80vh] w-80 flex-col gap-2 overflow-y-auto"
    >
      {visible.map((n: AppNotification) => (
        <NotificationCard key={n.id} notification={n} onDismiss={dismissNotification} />
      ))}
    </div>
  );
}
