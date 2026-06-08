import { useEffect, useState } from "react";

/**
 * useKeyboardInset — returnerar antalet pixlar som virtuella tangent-
 * bordet täcker av viewporten på iOS Safari. Driver bottom-offset på
 * bottom-sheet-panelen så att composern aldrig hamnar under tangent-
 * bordet när operatören skriver.
 *
 * Implementation via `window.visualViewport`-API:t som specifikt rapporterar
 * sektionen som faktiskt är synlig för användaren (inte hela window).
 * Skillnaden `innerHeight - visualViewport.height - visualViewport.offsetTop`
 * = höjden av det som ligger nedanför synlig viewport, dvs keyboard.
 *
 * Disabled när `enabled` är false (vi vill inte lyssna på dessa events
 * när chatten är minimerad eller desktop-läge är aktivt).
 */
export function useKeyboardInset(enabled: boolean): number {
  const [inset, setInset] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    if (typeof window === "undefined") return;
    const vv = window.visualViewport;
    if (!vv) return;
    const update = () => {
      const offset = window.innerHeight - vv.height - vv.offsetTop;
      setInset(Math.max(0, Math.round(offset)));
    };
    update();
    vv.addEventListener("resize", update);
    vv.addEventListener("scroll", update);
    return () => {
      vv.removeEventListener("resize", update);
      vv.removeEventListener("scroll", update);
    };
  }, [enabled]);
  return inset;
}
