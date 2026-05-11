"use client";

import { cn } from "@/lib/utils";

/**
 * Lightweight ShaderBackground stub för apps/web.
 *
 * Sajtmaskins original importerar `@paper-design/shaders-react` (~30 MB
 * canvas-shader-bibliotek). apps/web behöver bara samma render-API så
 * att `category/[type]/page.tsx` m.fl. inte bryts. Vi renderar en lugn
 * gradient + pris-konsekvent palette istället. Riktiga shaders kan
 * läggas tillbaka senare om designen kräver det.
 */

const SHADER_THEMES = {
  default: { color: "#01060C" },
  deep: { color: "#021522" },
  blue: { color: "#E67E22" },
  warm: { color: "#F07050" },
  amber: { color: "#F0A070" },
} as const;

export type ShaderTheme = keyof typeof SHADER_THEMES;

interface ShaderBackgroundProps {
  theme?: ShaderTheme;
  color?: string;
  speed?: number;
  opacity?: number;
  className?: string;
  shimmer?: boolean;
  shimmerSpeed?: number;
}

export function ShaderBackground({
  theme = "default",
  color,
  opacity = 0.4,
  className = "",
}: ShaderBackgroundProps) {
  const accent = color ?? SHADER_THEMES[theme].color;
  const opacityClass = getOpacityClass(opacity);

  return (
    <div
      className={cn(
        "shader-background bg-background fixed inset-0 -z-0 select-none",
        opacityClass,
        className,
      )}
      style={{
        backgroundImage: `radial-gradient(circle at 30% 20%, ${accent}33 0%, transparent 60%), radial-gradient(circle at 70% 80%, ${accent}1a 0%, transparent 55%)`,
      }}
    />
  );
}

function getOpacityClass(value: number | undefined): string {
  const normalized = Math.max(0, Math.min(value ?? 0.4, 1));
  const options: Array<{ value: number; cls: string }> = [
    { value: 0, cls: "opacity-0" },
    { value: 0.1, cls: "opacity-10" },
    { value: 0.2, cls: "opacity-20" },
    { value: 0.3, cls: "opacity-30" },
    { value: 0.4, cls: "opacity-40" },
    { value: 0.5, cls: "opacity-50" },
    { value: 0.6, cls: "opacity-60" },
    { value: 0.7, cls: "opacity-70" },
    { value: 0.8, cls: "opacity-80" },
    { value: 0.9, cls: "opacity-90" },
    { value: 1, cls: "opacity-100" },
  ];
  let closest = options[0];
  let minDistance = Math.abs(normalized - closest.value);
  for (const opt of options) {
    const distance = Math.abs(normalized - opt.value);
    if (distance < minDistance) {
      minDistance = distance;
      closest = opt;
    }
  }
  return closest.cls;
}
