/**
 * ui-tokens — delade Tailwind-klassträngar för interaktiva element.
 *
 * Vi har många custom-buttons utöver shadcn-Button (chips, pills,
 * IconButton-varianter, dropzones). Att duplicera focus/hover-mönster
 * i varje fil leder till inconsistent UX. Dessa klasssträngar är en
 * central source-of-truth som komponenter kan importera och spreada
 * via ``cn()``.
 *
 * Designprinciper:
 *   - ``motion-safe:`` runt allt som rör sig så reduced-motion-
 *     användare aldrig ser scale/translate-effekter.
 *   - Focus-ring matchar Buttons ``focus-visible:ring-3 ring-ring/50``
 *     mönster (från components/ui/button.tsx) så alla interaktiva
 *     element känns som en familj.
 *   - Active-state har ``translate-y-px`` (default Button-mönstret)
 *     ELLER ``scale-[0.97]`` (mer kompakt för pills/chips). Aldrig
 *     båda samtidigt — det blir för mycket rörelse.
 */

/**
 * Standard focus-ring för alla interaktiva element. Använd när
 * komponenten är en knapp/button-liknande icke-Button-element.
 *
 * Använd som:
 *   <button className={cn("...", FOCUS_RING)}>...
 */
export const FOCUS_RING =
  "focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:border-ring outline-none";

/**
 * Standard hover/active för primärknappar (mörk bakgrund, ljus text).
 * Subtil scale-down på active + opacity-shift på hover. Matchar
 * Apple-like minimalism — inga shadow-bumps eller färgskift.
 */
export const PRIMARY_INTERACTIONS =
  "motion-safe:transition-transform motion-safe:active:scale-[0.97] hover:opacity-90";

/**
 * Standard hover/active för sekundärknappar (ghost / outline).
 * Mindre opacity-skift men samma scale-mönster så hela ekosystemet
 * känns konsekvent när operatören klickar runt.
 */
export const SECONDARY_INTERACTIONS =
  "motion-safe:transition-transform motion-safe:active:scale-[0.97] hover:bg-foreground/[0.04]";

/**
 * Hover/active för pill/chip-knappar (små, runda, ofta i grupper).
 * Mindre rörelse än primary för att inte distrahera när det är
 * många chips i samma rad.
 */
export const CHIP_INTERACTIONS =
  "motion-safe:transition-all motion-safe:active:scale-[0.96] hover:border-foreground/30";
