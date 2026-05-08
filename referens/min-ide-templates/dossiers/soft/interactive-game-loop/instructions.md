# When to use

Use this dossier when the prompt asks for a playable mini-game, not a visual mockup. Triggers include `spel`, `game`, `playable`, `Pac-Man`, `Snake`, `Tetris`, `platformer`, `arcade`, `mini-game`, `quiz-game`, `interactive canvas`, keyboard/touch controls, score, lives, collision, win/lose.

Best fit:

- A single-route arcade page with a playable area, score and restart.
- A small quiz/reaction game embedded in a section of an otherwise static site.
- A Pac-Man / Snake / Breakout / platformer clone with thematic skin.

Do not use for:

- Decorative 3D that happens to move — that is `visual-3d` (`three-fiber-canvas`).
- Physics mock-ups with bouncing/gravity/collisions but no win/lose — that is `physics-3d` (`three-fiber-physics`).
- Carousel/slideshow, parallax, or form-wizard — those have their own dossiers.

# How to integrate

A game output MUST deliver all six contract points — anything less ships as a static mockup:

1. **State.** Explicit React state with at least `score`, `status: "idle" | "playing" | "won" | "lost"`, and whatever domain state the mechanic needs (e.g. `player`, `enemies`, `board`, `tick`). Never fake a game with CSS-only transitions or pure mock data.
2. **Loop.** A deterministic update loop: either a `setInterval` / `requestAnimationFrame` inside `useEffect` with proper `clearInterval` / `cancelAnimationFrame` cleanup, or a keyboard-driven state-transition model (Snake/Tetris-style) that advances on input. The loop MUST stop when `status !== "playing"` and MUST pause when the tab is hidden (`document.visibilityState`).
3. **Controls.** Keyboard handlers on `window` (`keydown` + remove on unmount) AND a visible fallback for touch — either arrow-buttons, swipe gestures, or tap-to-move. The game-mount component MUST be a Client Component (`"use client"` at top). Input focus is captured on mount; explicit instructions are visible on screen.
4. **Collision / resolution.** Collision via axis-aligned bounding box (`a.x < b.x + b.w && a.x + a.w > b.x && ...`) or distance check (`Math.hypot(dx, dy) < r`). Do NOT add `@react-three/rapier` or other physics libraries unless the prompt also triggers `needsPhysics`.
5. **Score + win/lose + restart.** A visible score area (large digit, top or corner). A clear win / lose transition when the mechanic demands it (score target, lives zero, board full). A restart button / key (press R / tap to restart) that resets state fully — no lingering refs.
6. **Accessibility.** `<output role="status" aria-live="polite">` around the score so screen readers announce updates. `<button>` for restart (never clickable div). If the scene is strictly visual (not keyboard reachable), a keyboard-only alternative path (e.g. reduced-motion check that renders a score-of-the-day summary) is better than nothing.

# Implementation skeleton

```tsx
// components/game/pacman-game.tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Status = "idle" | "playing" | "won" | "lost";

interface GameState {
  status: Status;
  score: number;
  // … mechanic-specific state (player pos, enemies, board)
}

export function PacmanGame() {
  const [state, setState] = useState<GameState>({ status: "idle", score: 0 });
  const rafRef = useRef<number | null>(null);

  const step = useCallback(() => {
    setState((s) => {
      if (s.status !== "playing") return s;
      // advance one tick: move player, move enemies, check collisions
      // return new object (never mutate)
      return { ...s, score: s.score + 1 };
    });
    rafRef.current = requestAnimationFrame(step);
  }, []);

  useEffect(() => {
    if (state.status !== "playing") return;
    rafRef.current = requestAnimationFrame(step);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, [state.status, step]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "r" || e.key === "R") {
        setState({ status: "playing", score: 0 });
      }
      // arrow keys / wasd → dispatch direction change
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <section aria-label="Pacman game">
      <output role="status" aria-live="polite" className="text-3xl font-bold">
        Score: {state.score}
      </output>
      {/* canvas / grid / svg rendering of the game world */}
      <button onClick={() => setState({ status: "playing", score: 0 })}>
        {state.status === "idle" ? "Start" : "Restart"}
      </button>
    </section>
  );
}
```

The skeleton is a pattern, not a template. Adapt the state shape, rendering primitive (`<canvas>`, SVG, grid of divs, R3F `<Canvas>` if `needs3D` is also true) and controls to the requested game. Keep the six contract points intact.

# Rendering primitive choice

| Game shape | Primitive |
|---|---|
| Grid-based (Snake, Tetris, tile puzzle) | CSS grid of `<div>`s or `<svg>` |
| Pixel arcade (Pac-Man, Space Invaders) | `<canvas>` with 2D context |
| 3D arcade (requires `needs3D` too) | R3F `<Canvas>` via `ThreeCanvasShell` |
| Reaction / quiz / clicker | React state + CSS transitions |

For `<canvas>` 2D: get `getContext("2d")` once in a ref, render inside `requestAnimationFrame`, size via `getBoundingClientRect` + devicePixelRatio. Wrap the whole game component in `"use client"`.

# UX rules

- Show the current score and status (playing / won / lost) in a large, high-contrast area — the player must always know how they are doing without decoding visuals.
- Instructions for controls must be visible on-screen on first mount, not hidden in a tooltip. One line ("Arrow keys to move, R to restart") is enough.
- Win / lose overlays must not block restart. Keep the restart button reachable via keyboard (Enter / R) even while the overlay is up.
- Respect `prefers-reduced-motion`: if the game has decorative motion beyond the core loop (background animations, score-pop effects), gate those with `motion-safe:` classes or a `useReducedMotion` check. The core game loop itself may still run — reduced-motion does not mean "no game".
- Touch controls must sit above the play area on narrow viewports, not overlap the playable surface.

# Avoid

- Do NOT ship a static illustration or a single `<canvas>` without `useEffect` + loop + state.
- Do NOT use `setInterval` without cleanup — the game keeps running after unmount.
- Do NOT mutate state (`state.score += 1`). Always return a new object from `setState`.
- Do NOT add physics libraries for simple AABB collision — it is 3-4 lines of math.
- Do NOT require the mouse — keyboard + touch MUST always work.
- Do NOT forget the restart path. A game with no restart is a demo, not a game.

# Verification

- Keyboard-only: arrow keys / WASD moves; R restarts; game is actually playable without a mouse.
- Visibility: switch tabs for 5 seconds, return — game should either pause or resume correctly, not have fast-forwarded.
- Score updates: screen reader announces score changes (verify via aria-live region).
- Restart: hit the restart button after lose — state resets fully, no lingering timers.
- Touch: on a mobile viewport, on-screen controls or swipe must drive the same mechanic.
