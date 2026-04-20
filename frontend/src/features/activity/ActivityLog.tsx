/**
 * Collapsable activity-log panel.
 *
 * Shows items that were added (green) or changed (amber) since the last
 * snapshot refresh, grouped by stash tab.  Clicking an item forwards the
 * selection to the parent via `onSelectItem`.
 *
 * The panel collapses to a narrow icon strip that still shows a badge with
 * the total count of activity events.
 */

import { useState } from "react";

import { useActivity } from "@/api/hooks";
import type { ActivityEntry, Item } from "@/api/types";
import { stripTags } from "@/utils/modText";

export interface ActivityLogProps {
  league: string | null;
  onSelectItem: (item: Item) => void;
}

// ── helpers ────────────────────────────────────────────────────────────────────

function ItemRow({
  item,
  status,
  onSelect,
}: {
  item: Item;
  status: "new" | "changed";
  onSelect: (item: Item) => void;
}) {
  const dot = status === "new" ? "bg-emerald-400" : "bg-amber-400";
  const label = item.name || item.type_line;

  return (
    <button
      type="button"
      onClick={() => onSelect(item)}
      className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-xs transition hover:bg-ink-700 focus:outline-none"
    >
      <span className={`mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
      <span className="min-w-0 truncate text-parchment-100/80">{stripTags(label)}</span>
    </button>
  );
}

function TabSection({
  entry,
  onSelect,
}: {
  entry: ActivityEntry;
  onSelect: (item: Item) => void;
}) {
  const total = entry.new_items.length + entry.changed_items.length + entry.removed_items.length;
  if (total === 0) return null;

  return (
    <div className="mt-1">
      <div className="px-2 text-[9px] font-semibold uppercase tracking-widest text-ink-500">
        {entry.tab_name}
      </div>
      {entry.new_items.map((item) => (
        <ItemRow key={item.id} item={item} status="new" onSelect={onSelect} />
      ))}
      {entry.changed_items.map(({ new: item }) => (
        <ItemRow key={item.id} item={item} status="changed" onSelect={onSelect} />
      ))}
    </div>
  );
}

// ── main component ─────────────────────────────────────────────────────────────

export function ActivityLog({ league, onSelectItem }: ActivityLogProps) {
  const [collapsed, setCollapsed] = useState(true);
  const activityQ = useActivity(league);
  const data = activityQ.data;
  const totalEvents = (data?.total_new ?? 0) + (data?.total_changed ?? 0);

  return (
    <aside
      className={[
        "flex flex-col border-r border-ink-700 bg-ink-900/60 transition-all duration-200",
        collapsed ? "w-9 min-w-[2.25rem]" : "w-52 min-w-[13rem]",
      ].join(" ")}
      aria-label="Activity log"
    >
      {/* Toggle button */}
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="flex items-center justify-between px-2 py-2 text-ink-400 transition hover:text-parchment-50 focus:outline-none"
        title={collapsed ? "Expand activity log" : "Collapse activity log"}
      >
        {/* Icon */}
        <span className="text-sm">&#9783;</span>
        {/* Badge */}
        {collapsed && totalEvents > 0 && (
          <span className="ml-0.5 rounded-full bg-ember-500 px-1 text-[9px] font-bold text-ink-950">
            {totalEvents > 99 ? "99+" : totalEvents}
          </span>
        )}
        {!collapsed && (
          <span className="text-[10px] uppercase tracking-widest text-ink-500">Activity</span>
        )}
        <span className="ml-auto text-xs">{collapsed ? "›" : "‹"}</span>
      </button>

      {/* Content — hidden when collapsed */}
      {!collapsed && (
        <div className="flex-1 overflow-y-auto px-1 pb-3">
          {activityQ.isLoading && (
            <p className="px-2 text-[11px] text-ink-500">Loading&hellip;</p>
          )}
          {data && !data.has_prev && (
            <p className="px-2 text-[11px] text-ink-500">
              No previous snapshot yet.
              <br />
              Refresh to start tracking changes.
            </p>
          )}
          {data?.has_prev && totalEvents === 0 && (
            <p className="px-2 text-[11px] text-ink-500">No changes since last refresh.</p>
          )}
          {data?.entries.map((entry) => (
            <TabSection key={entry.tab_id} entry={entry} onSelect={onSelectItem} />
          ))}
        </div>
      )}
    </aside>
  );
}
