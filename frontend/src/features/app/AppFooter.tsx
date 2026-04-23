const GGG_DISCLAIMER = "This product isn't affiliated with or endorsed by Grinding Gear Games in any way.";

interface AppFooterProps {
  className?: string;
}

export function AppFooter({ className = "" }: AppFooterProps) {
  return (
    <footer className={className} aria-label="Legal disclaimer">
      <p className="mx-auto max-w-5xl px-4 text-center text-xs text-ink-500">{GGG_DISCLAIMER}</p>
    </footer>
  );
}

