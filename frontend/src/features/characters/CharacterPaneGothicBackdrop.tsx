/**
 * Full-bleed abstract gothic fill for the character pane: dark base rising from
 * the bottom, fading upward, with a subtle lattice / coursing pattern.
 */

export function CharacterPaneGothicBackdrop({ className = "rounded-sm" }: { className?: string }) {
  return (
    <div
      className={`pointer-events-none absolute inset-0 z-0 overflow-hidden ${className}`.trim()}
      aria-hidden
      style={{
        backgroundImage: [
          "linear-gradient(to top, rgb(5,5,8) 0%, rgba(10,10,14,0.88) 18%, rgba(12,12,18,0.42) 52%, rgba(14,14,20,0.1) 82%, transparent 100%)",
          "repeating-linear-gradient(62deg, transparent 0 13px, rgba(200,170,130,0.04) 13px 14px)",
          "repeating-linear-gradient(-62deg, transparent 0 13px, rgba(175,150,110,0.032) 13px 14px)",
          "repeating-linear-gradient(90deg, transparent 0 22px, rgba(255,255,255,0.025) 22px 23px)",
        ].join(","),
      }}
    />
  );
}
