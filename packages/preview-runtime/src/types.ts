/**
 * Preview Runtime — typkontrakt.
 *
 * Canonical-namnen är låsta i naming-dictionary v17:
 *   - `Preview Runtime` (abstraktionen)
 *   - `PreviewRuntimeKind` (sluten typunion: "stackblitz" | "local" | "fly")
 *   - `PreviewRuntimeConfig` (kind, projectName, env)
 *   - `Preview Session` (id, url, kind, createdAt) — alias `PreviewSession`
 *   - `Preview File` (path + content) — alias `PreviewFile`
 *   - `Preview Result` (previewSession, previewUrl, startup-output, status)
 *
 * Filerna här är skelett. `start()`/`stop()` returnerar tills vidare en
 * `unsupported`-status med tydlig "Bite B-wiring saknas"-text. Faktisk
 * wiring mot `apps/viewser/lib/local-preview-server.ts` (LocalRuntime) och
 * `apps/viewser/lib/stackblitz-files.ts` (StackBlitzRuntime) sker i Bite B
 * när vi också konfigurerar tsconfig-path eller npm-workspace så viewser
 * kan importera härifrån.
 *
 * Se ADR 0028 (Runtime Ladder) för rollerna mellan local/stackblitz/fly och
 * ADR 0030 (Preview-Provider Portability) för adapter-checklistan som varje
 * ny adapter måste passera innan merge. Eventuell framtida `vercel-preview`-
 * adapter kräver naming-dictionary-bump till v18 (utöka `PreviewRuntimeKind`)
 * + egen ADR per ADR 0030 §"Vad ADR 0030 INTE beslutar".
 */

/**
 * Sluten typunion för giltiga Preview Runtime-värden. Definierad i
 * naming-dictionary v17:`previewRuntimeKind`. Får inte utökas utan naming-
 * dictionary-bump.
 */
export type PreviewRuntimeKind = "stackblitz" | "local" | "fly";

/**
 * En fil i den filuppsättning som monteras i Preview Runtime.
 * Canonical: `Preview File` (naming-dictionary v17:`previewFile`).
 */
export interface PreviewFile {
  path: string;
  content: string;
}

/**
 * Konfigurationsobjekt som skickas till `PreviewRuntime.start()`.
 * Canonical: `PreviewRuntimeConfig` (naming-dictionary v17).
 */
export interface PreviewRuntimeConfig {
  kind: PreviewRuntimeKind;
  projectName: string;
  env?: Record<string, string>;
  /** Sajt-id som matchar `data/runs/<runId>/build-result.json:siteId`. */
  siteId?: string;
  /** Builder-run-id, för spårbarhet. */
  runId?: string;
  /** Version-snapshot (`<siteId>.vN.project-input.json`). */
  versionId?: string;
  /** Path till genererad sajt på disk (för adaptrar som kör mot filer). */
  generatedFilesPath?: string;
  /** In-memory file-payload (för adaptrar som inte läser från disk). */
  files?: PreviewFile[];
}

/**
 * Aktiv session från en Preview Runtime.
 * Canonical: `Preview Session` (naming-dictionary v17:`previewSession`).
 */
export interface PreviewSession {
  id: string;
  url: string;
  kind: PreviewRuntimeKind;
  createdAt: string;
  /** Iframe-embeddable URL om den skiljer sig från `url`. */
  embedUrl?: string;
}

/**
 * Resultat från PreviewRuntime efter en Engine Run.
 * Canonical: `Preview Result` (naming-dictionary v17:`previewResult`).
 */
export interface PreviewResult {
  status: "ready" | "starting" | "failed" | "unsupported";
  previewSession?: PreviewSession;
  previewUrl?: string;
  /** Strukturerade startup-loggar för debugging. */
  logs?: string[];
  /** Mänsklig felförklaring vid `failed`/`unsupported`. */
  error?: string;
}

/**
 * Adapter-kontrakt som varje konkret Preview Runtime-implementation måste
 * uppfylla. Skelett-stubsen i `adapters/` returnerar `unsupported` tills
 * Bite B wirear dem mot befintlig kod i `apps/viewser/lib/`.
 *
 * Adapter-checklista (ADR 0030 §"Adapter-checklista"):
 *   1. Implementerar detta interface.
 *   2. Har en non-trivial fallback-strategi.
 *   3. `local` är primär för operator-bygda sajter; andra är fallbacks.
 *   4. Inga vendor-specifika begrepp läcker till `packages/generation/`.
 *   5. Genererad output kan startas lokalt utan adaptern.
 *   6. Adapter-specifika ENV-vars är opt-in.
 *   7. PR-beskrivning länkar till ADR 0030.
 */
export interface PreviewRuntime {
  readonly kind: PreviewRuntimeKind;
  readonly label: string;

  /** Snabb runtime-check (env + dependencies). */
  isAvailable(): Promise<boolean> | boolean;

  /** Starta preview-session för given config. */
  start(config: PreviewRuntimeConfig): Promise<PreviewResult>;

  /** Stoppa preview om adaptern äger pågående process/resurs. */
  stop?(sessionId: string): Promise<void>;
}
