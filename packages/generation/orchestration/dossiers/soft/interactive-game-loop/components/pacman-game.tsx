"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type Status = "idle" | "playing" | "won" | "lost";
type Direction = "up" | "down" | "left" | "right";

type Position = {
  x: number;
  y: number;
};

type Ghost = Position & { id: string; direction: Direction };

type GameState = {
  status: Status;
  score: number;
  player: Position;
  playerDirection: Direction;
  ghosts: Ghost[];
  pellets: Set<string>;
};

const TILE_MAP = [
  "###############",
  "#.............#",
  "#.###.###.###.#",
  "#.............#",
  "#.###.#.#.###.#",
  "#.....#.#.....#",
  "###.#.#.#.#.###",
  "#...#.....#...#",
  "###.#.###.#.###",
  "#.....#.#.....#",
  "#.###.#.#.###.#",
  "#.............#",
  "#.###.###.###.#",
  "#.............#",
  "###############",
];

const BOARD_WIDTH = TILE_MAP[0].length;
const BOARD_HEIGHT = TILE_MAP.length;
const TICK_MS = 180;

const PLAYER_START: Position = { x: 1, y: 1 };
const GHOST_STARTS: Ghost[] = [
  { id: "blinky", x: 13, y: 1, direction: "left" },
  { id: "pinky", x: 13, y: 13, direction: "up" },
  { id: "inky", x: 1, y: 13, direction: "right" },
  { id: "clyde", x: 7, y: 7, direction: "left" },
];

function keyFor(pos: Position): string {
  return `${pos.x},${pos.y}`;
}

function isWall(pos: Position): boolean {
  if (pos.x < 0 || pos.x >= BOARD_WIDTH || pos.y < 0 || pos.y >= BOARD_HEIGHT) {
    return true;
  }
  return TILE_MAP[pos.y][pos.x] === "#";
}

function move(pos: Position, direction: Direction): Position {
  if (direction === "up") return { x: pos.x, y: pos.y - 1 };
  if (direction === "down") return { x: pos.x, y: pos.y + 1 };
  if (direction === "left") return { x: pos.x - 1, y: pos.y };
  return { x: pos.x + 1, y: pos.y };
}

function pelletSet(): Set<string> {
  const pellets = new Set<string>();
  for (let y = 0; y < BOARD_HEIGHT; y += 1) {
    for (let x = 0; x < BOARD_WIDTH; x += 1) {
      if (TILE_MAP[y][x] === ".") {
        pellets.add(`${x},${y}`);
      }
    }
  }
  pellets.delete(keyFor(PLAYER_START));
  return pellets;
}

function initialGameState(): GameState {
  return {
    status: "idle",
    score: 0,
    player: { ...PLAYER_START },
    playerDirection: "right",
    ghosts: GHOST_STARTS.map((ghost) => ({ ...ghost })),
    pellets: pelletSet(),
  };
}

function chooseGhostDirection(ghost: Ghost): Direction {
  const all: Direction[] = ["up", "down", "left", "right"];
  const possible = all.filter((direction) => !isWall(move(ghost, direction)));
  if (possible.length === 0) return ghost.direction;
  if (possible.includes(ghost.direction) && Math.random() > 0.35) return ghost.direction;
  return possible[Math.floor(Math.random() * possible.length)];
}

function hasCollision(player: Position, ghosts: Ghost[]): boolean {
  return ghosts.some((ghost) => ghost.x === player.x && ghost.y === player.y);
}

export function PacmanGame() {
  const [state, setState] = useState<GameState>(() => initialGameState());
  const touchStart = useRef<Position | null>(null);

  const restart = useCallback(() => {
    setState({ ...initialGameState(), status: "playing" });
  }, []);

  const setDirection = useCallback((direction: Direction) => {
    setState((prev) => ({ ...prev, playerDirection: direction }));
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "r" || event.key === "R") {
        event.preventDefault();
        restart();
        return;
      }
      if (event.key === "ArrowUp") setDirection("up");
      if (event.key === "ArrowDown") setDirection("down");
      if (event.key === "ArrowLeft") setDirection("left");
      if (event.key === "ArrowRight") setDirection("right");
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [restart, setDirection]);

  useEffect(() => {
    if (state.status !== "playing") return;

    const intervalId = window.setInterval(() => {
      if (document.visibilityState === "hidden") {
        return;
      }

      setState((prev) => {
        if (prev.status !== "playing") return prev;

        const nextPlayerCandidate = move(prev.player, prev.playerDirection);
        const nextPlayer = isWall(nextPlayerCandidate) ? prev.player : nextPlayerCandidate;

        const pellets = new Set(prev.pellets);
        let score = prev.score;
        const playerCell = keyFor(nextPlayer);
        if (pellets.has(playerCell)) {
          pellets.delete(playerCell);
          score += 10;
        }

        const ghosts = prev.ghosts.map((ghost) => {
          const direction = chooseGhostDirection(ghost);
          const candidate = move(ghost, direction);
          if (isWall(candidate)) return { ...ghost, direction };
          return { ...ghost, ...candidate, direction };
        });

        if (hasCollision(nextPlayer, ghosts)) {
          return { ...prev, player: nextPlayer, ghosts, score, pellets, status: "lost" };
        }

        if (pellets.size === 0) {
          return { ...prev, player: nextPlayer, ghosts, score, pellets, status: "won" };
        }

        return {
          ...prev,
          player: nextPlayer,
          ghosts,
          score,
          pellets,
        };
      });
    }, TICK_MS);

    return () => window.clearInterval(intervalId);
  }, [state.status]);

  const grid = useMemo(() => {
    const ghostMap = new Map(state.ghosts.map((ghost) => [keyFor(ghost), ghost.id]));
    const playerCell = keyFor(state.player);

    return TILE_MAP.flatMap((row, y) =>
      row.split("").map((tile, x) => {
        const cellKey = `${x},${y}`;
        const hasPellet = state.pellets.has(cellKey);
        const ghost = ghostMap.get(cellKey);
        const isPlayer = cellKey === playerCell;
        return { cellKey, tile, hasPellet, ghost, isPlayer };
      }),
    );
  }, [state.ghosts, state.pellets, state.player]);

  return (
    <section className="mx-auto max-w-3xl rounded-xl border p-4 shadow-sm" aria-label="Pacman game">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm text-muted-foreground">Piltangenter eller touchknappar for att styra. R = restart.</p>
          <p className="text-sm font-medium">Status: {state.status}</p>
        </div>
        <output role="status" aria-live="polite" className="text-2xl font-bold">
          Score: {state.score}
        </output>
      </div>

      <div
        className="mx-auto grid w-full max-w-[420px] touch-pan-y rounded border bg-black p-2"
        style={{ gridTemplateColumns: `repeat(${BOARD_WIDTH}, minmax(0, 1fr))` }}
        onTouchStart={(event) => {
          const touch = event.touches[0];
          touchStart.current = { x: touch.clientX, y: touch.clientY };
        }}
        onTouchEnd={(event) => {
          if (!touchStart.current) return;
          const touch = event.changedTouches[0];
          const dx = touch.clientX - touchStart.current.x;
          const dy = touch.clientY - touchStart.current.y;
          touchStart.current = null;

          if (Math.abs(dx) < 12 && Math.abs(dy) < 12) return;
          if (Math.abs(dx) > Math.abs(dy)) {
            setDirection(dx > 0 ? "right" : "left");
          } else {
            setDirection(dy > 0 ? "down" : "up");
          }
        }}
      >
        {grid.map((cell) => (
          <div key={cell.cellKey} className="relative aspect-square">
            {cell.tile === "#" && <div className="h-full w-full rounded-[2px] bg-blue-800" />}
            {cell.tile !== "#" && cell.hasPellet && (
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-200" />
              </div>
            )}
            {cell.ghost && (
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="h-3 w-3 rounded-full bg-pink-500" />
              </div>
            )}
            {cell.isPlayer && (
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="h-3 w-3 rounded-full bg-yellow-300" />
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button className="rounded border px-3 py-1.5 text-sm" type="button" onClick={restart}>
          {state.status === "idle" ? "Starta spel" : "Starta om"}
        </button>
        <button className="rounded border px-3 py-1.5 text-sm" type="button" onClick={() => setDirection("up")}>
          Upp
        </button>
        <button className="rounded border px-3 py-1.5 text-sm" type="button" onClick={() => setDirection("left")}>
          Vanster
        </button>
        <button className="rounded border px-3 py-1.5 text-sm" type="button" onClick={() => setDirection("down")}>
          Ner
        </button>
        <button className="rounded border px-3 py-1.5 text-sm" type="button" onClick={() => setDirection("right")}>
          Hoger
        </button>
      </div>
    </section>
  );
}
