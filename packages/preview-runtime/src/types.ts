/**
 * Preview Runtime — typkontrakt.
 *
 * Canonical-namnen är låsta i naming-dictionary (v19):
 *   - `Preview Runtime` (abstraktionen)
 *   - `PreviewRuntimeKind` (sluten typunion: "vercel-sandbox" | "local" |
 *     "stackblitz" | "fly")
 *   - `PreviewRuntimeConfig` (kind, projectName, env)
 *   - `Preview Session` (id, url, kind, createdAt) — alias `PreviewSession`
 *   - `Preview File` (path + content) — alias `PreviewFile`
 *   - `Preview Result` (previewSession, previewUrl, startup-output, status)
 *
 * Adaptrarna får sina konkreta handlers via dependency injection. Det håller
 * paketet fritt från app-importer samtidigt som `apps/viewser/lib` kan koppla
 * in sina befintliga server-helpers.
 *
 * Se ADR 0028 (Runtime Ladder) för rollerna mellan runtimes och ADR 0030
 * (Preview-Provider Portability) för adapter-checklistan som varje ny adapter
 * måste passera innan merge. ADR 0033 gör `vercel-sandbox` till primärt
 * förstahandsval (local-next fallback, stackblitz pausad) — fortfarande som
 * adapter bakom `PreviewRuntime`-kontraktet, aldrig hårdkodad specialväg.
 */

/**
 * Sluten typunion för giltiga Preview Runtime-värden. Definierad i
 * naming-dictionary v19:`previewRuntimeKind`. Får inte utökas utan naming-
 * dictionary-bump. `vercel-sandbox` är primärt förstahandsval (ADR 0033).
 */
export type PreviewRuntimeKind =
  | "vercel-sandbox"
  | "local"
  | "stackblitz"
  | "fly";

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
 * Fas-timing (ms) för en preview-start — adaptrar som mäter sin cold-start
 * (idag `vercel-sandbox`) rapporterar var tiden går så operatören kan se
 * skillnaden mellan t.ex. install- och build-fasen. Alla fält är optionella:
 * adaptrar utan mätning utelämnar hela objektet, och faser som hoppats över
 * (t.ex. `buildMs` på pre-built-vägen) utelämnas individuellt.
 */
export interface PreviewTimings {
  /**
   * Källinhämtningstid (G2, ADR 0058): tiden adaptern lade på att lösa
   * upp/ladda ner sajt-källan — fil-för-fil-vägens blob-listning+nedladdning
   * respektive preview-bundle-vägens pekarläsning+HEAD-probe (tarballen
   * extraheras då i `createMs`). Additivt fält; adaptrar utan mätning
   * utelämnar det.
   */
  sourceMs?: number;
  createMs?: number;
  uploadMs?: number;
  installMs?: number;
  buildMs?: number;
  readyMs?: number;
  totalMs?: number;
  /**
   * True när previewn serverades genom att återanvända en redan varm sandbox
   * (Tier 2, ADR 0041) i stället för att skapa en ny. Additivt fält: adaptrar
   * utan återanvändning utelämnar det (eller sätter `false`). På återanvändning
   * är `createMs` typiskt utelämnad — vinsten syns som `reused: true` + liten
   * `installMs` i preview-svaret.
   */
  reused?: boolean;
}

/**
 * Resultat från PreviewRuntime efter en Engine Run.
 * Canonical: `Preview Result` (naming-dictionary v17:`previewResult`).
 */
export interface PreviewResult {
  status: "ready" | "starting" | "failed" | "unsupported";
  previewSession?: PreviewSession;
  previewUrl?: string;
  /** Filpayload för adaptrar som lämnar över filer till ett UI-lager. */
  files?: PreviewFile[];
  /** Strukturerade startup-loggar för debugging. */
  logs?: string[];
  /** Mänsklig felförklaring vid `failed`/`unsupported`. */
  error?: string;
  /** Fas-timing (ms) när adaptern mäter sin cold-start (additivt fält). */
  timings?: PreviewTimings;
}

/**
 * Adapter-kontrakt som varje konkret Preview Runtime-implementation måste
 * uppfylla. Konkreta integrationer injiceras via `configurePreviewRuntimeHandlers`
 * så `packages/preview-runtime` inte behöver importera app-lagret.
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
