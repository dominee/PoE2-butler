import { useParams } from "react-router-dom";

import { usePublicItem } from "@/api/hooks";
import { ApiError } from "@/api/client";
import { AppFooter } from "@/features/app/AppFooter";
import { ItemDetailPane } from "@/features/items/ItemDetailPane";

export function PublicItemPage() {
  const { shareId } = useParams<{ shareId: string }>();
  const q = usePublicItem(shareId);

  if (q.isLoading) {
    return (
      <div className="flex min-h-full flex-col">
        <main className="flex flex-1 items-center justify-center p-8 text-ink-500">
          Loading shared item&hellip;
        </main>
        <AppFooter className="pb-6" />
      </div>
    );
  }

  if (q.isError && q.error) {
    const st = q.error instanceof ApiError ? q.error.status : 0;
    return (
      <div className="flex min-h-full flex-col">
        <main className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
          <p className="text-parchment-100/90">
            {st === 404
              ? "This share link is invalid, expired, or was revoked."
              : "This shared item could not be loaded."}
          </p>
          <a className="btn-ghost text-sm" href="/">
            Home
          </a>
        </main>
        <AppFooter className="pb-6" />
      </div>
    );
  }

  if (!q.data) {
    return null;
  }

  return (
    <div className="flex min-h-full flex-col">
      <header className="shrink-0 border-b border-ink-800 bg-ink-900/60 px-4 py-3 text-sm text-parchment-100/80 backdrop-blur">
        <p className="text-[10px] uppercase tracking-widest text-ink-500">Public snapshot</p>
        <p className="mt-0.5 max-w-2xl text-ink-400">
          This page shows a read-only item snapshot. Anyone with the link can see it. Open the
          app to browse your private stash and create new share links.{" "}
          <a className="text-ember-400 hover:underline" href="/app">
            Go to PoE2 Butler
          </a>
        </p>
      </header>
      <div className="grid flex-1 min-h-0 place-items-stretch">
        <div className="mx-auto w-full max-w-lg min-h-0 max-h-dvh">
          <ItemDetailPane
            item={q.data.item}
            league={q.data.league}
            prefs={undefined}
            mode="public"
          />
        </div>
      </div>
      <AppFooter className="pb-6" />
    </div>
  );
}
