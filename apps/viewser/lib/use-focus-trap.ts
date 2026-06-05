import { useEffect, type RefObject } from "react";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  'input:not([disabled]):not([type="hidden"])',
  "select:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

/**
 * Fångar Tab-fokus inom `containerRef` medan `active` är true.
 *
 * För custom overlay-dialoger (role="dialog" aria-modal="true") som INTE går
 * genom Radix/base-ui-dialogkomponenten och därför saknar inbyggd focus-trap — t.ex.
 * AI-bildgeneratorn och wizardens kortkommando-overlay. Utan trappen kan en
 * tangentbordsanvändare Tab:a ut bakom modalen och interagera med dolt
 * innehåll. Vi wrappar fokus från sista → första elementet (och tvärtom med
 * Shift+Tab). Esc-stängning + initial-fokus ägs av respektive anropare.
 */
export function useFocusTrap(
  containerRef: RefObject<HTMLElement | null>,
  active: boolean,
): void {
  useEffect(() => {
    if (!active) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Tab") return;
      const container = containerRef.current;
      if (!container) return;
      const focusable = Array.from(
        container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      ).filter(
        (el) => el.offsetParent !== null || el === document.activeElement,
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const activeEl = document.activeElement as HTMLElement | null;
      const outside = !activeEl || !container.contains(activeEl);
      if (event.shiftKey) {
        if (outside || activeEl === first) {
          event.preventDefault();
          last.focus();
        }
      } else if (outside || activeEl === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [active, containerRef]);
}
