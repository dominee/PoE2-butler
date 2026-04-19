export function LandingPage() {
  return (
    <main className="flex min-h-full flex-col items-center justify-center p-8 text-center">
      <h1 className="font-display text-5xl text-ember-400 sm:text-6xl">
        PoE2 Hideout Butler
      </h1>
      <p className="mt-4 max-w-xl text-parchment-100/80">
        Sign in with your GGG account to browse your characters, equipped gear,
        and stash tabs with price estimates and one-click PoE2 Trade links.
      </p>
      <a href="/api/auth/login" className="btn-primary mt-8">
        Sign in with GGG
      </a>
      <p className="mt-4 text-xs uppercase tracking-wide text-ink-500">
        M0 foundations build
      </p>
    </main>
  );
}
