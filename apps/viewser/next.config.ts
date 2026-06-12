import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

// Monorepo-rot (två nivåer upp från apps/viewser). Beräknas från configens
// egen filsökväg (oberoende av process.cwd(), som inte är pålitlig under
// Turbopacks worker-processer). Används som ``turbopack.root`` så Turbopack
// inkluderar ``../../packages`` i modulgrafen — annars kan VARKEN ``next dev``
// ELLER ``next build`` resolva ``@preview-runtime`` (TS-källa utanför
// app-roten). Se kommentaren vid ``turbopack`` nedan.
const REPO_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
);

// Preview-runtime-läge (ADR 0028 — Runtime Ladder).
// ------------------------------------------------------------------
// Viewser har två sätt att rendera den genererade sajten i preview-
// iframen, och de behöver MOTSATTA header-konfigurationer:
//
//   1. `local-next`  — LocalRuntime, första rungen i runtime-stegen.
//                      `lib/local-preview-server.ts` spawnar
//                      `npx next start -p <4100-4199>` mot
//                      `../sajtbyggaren-output/.generated/<siteId>/`
//                      och ViewerPanel embeddar det via en plain
//                      cross-origin (annan port) <iframe>. Då FÅR vi
//                      INTE sätta Cross-Origin-Embedder-Policy /
//                      Cross-Origin-Opener-Policy — credentialless +
//                      same-origin blockerar cross-origin iframes som
//                      inte själva bär `credentialless`-attributet.
//
//   2. `stackblitz`  — Bakåtkompatibel WebContainer-väg. StackBlitz-
//                      embeddet kräver SharedArrayBuffer, vilket bara
//                      är tillgängligt på cross-origin-isolerade
//                      dokument. Då MÅSTE vi sätta
//                      `Cross-Origin-Embedder-Policy: credentialless`
//                      och `Cross-Origin-Opener-Policy: same-origin`,
//                      annars visar StackBlitz "Unable to run Embedded
//                      Project — Looks like this project is being
//                      embedded without proper isolation headers".
//
//   3. `auto`        — Reserverat för framtida heuristik (välj
//                      LocalRuntime när bygget finns, annars
//                      StackBlitz). Idag mappar `auto` på StackBlitz-
//                      headers för säker bakåtkompatibilitet.
//
//   4. `vercel-sandbox` — VercelSandboxRuntime (ADR 0033, primärt
//                      förstahandsval). Previewn serveras från en publik
//                      `…vercel.run`-https-URL (isolerad Vercel Sandbox) och
//                      bäddas som en plain cross-origin <iframe>. Precis som
//                      `local-next` FÅR vi INTE sätta COEP/COOP — en publik
//                      https-iframe behöver ingen cross-origin-isolation
//                      (det krävs bara av StackBlitz/WebContainers). Samma
//                      transport som local-next (http, COEP off).
//
// `credentialless` används i StackBlitz-grenen istället för
// `require-corp` eftersom vi embeddar tredjepartsiframe (stackblitz.com)
// vars resurser vi inte kan styra `Cross-Origin-Resource-Policy` på.
// `credentialless` är den nyare cross-origin-isolation-modellen som
// tillåter just det här fallet och dokumenteras av StackBlitz som det
// rätta värdet för "embedding arbitrary resources" — se
// https://developer.stackblitz.com/platform/webcontainers/browser-support#embedding.
//
// Krav speglas också i:
//   - docs/adr/0028-runtime-ladder.md (LocalRuntime som första rung)
//   - docs/integrations/webcontainers-notes.md (host-miljö-krav)
//   - docs/architecture/preview-runtime.md (StackBlitz-implementationen)
//   - docs/integrations/stackblitz-research.md (browser-baseline + headers)
//
// Embedded WebContainers fungerar officiellt bara i Chromium-baserade
// browsers (Chrome, Edge, Brave, Vivaldi). Firefox/Safari rendrar
// samma fel även med headers korrekt satta — StackBlitz egen browser-
// support-tabell säger detta uttryckligen.
//
// Default-värdet är `vercel-sandbox` sedan default-flippen (operatörsbeslut
// 2026-06-12, ADR 0033): den primära användarpreview-runtimen är nu också
// faktisk default, i synk med packages/preview-runtime:currentKind och
// preview-runtime-policy.v1.json:default. vercel-sandbox kör COEP off
// (publik https-iframe behöver ingen cross-origin isolation), så en osatt
// env i en hosted deploy ger rätt headers direkt. Lokal dev väljer
// `local-next` EXPLICIT via .env.local (mallen .env.example sätter raden) —
// production-gaten nedan skyddar fortfarande det fallet.
const PREVIEW_MODE = (
  process.env.VIEWSER_PREVIEW_MODE ?? "vercel-sandbox"
).toLowerCase();

// Production safety gate.
// ------------------------------------------------------------------
// `local-next` är medvetet "isolation off" — det är det enda sättet
// att låta en cross-origin (annan port) localhost-iframe rendras
// utan att blockas av `Cross-Origin-Embedder-Policy: credentialless`.
// Det är RÄTT i dev-miljö (lokal preview-server på 4100-4199), men
// FARLIGT i produktion av två orsaker:
//
//   a) Den hostade StackBlitz-vägen (fallback när LocalRuntime inte
//      finns) tappar tyst SharedArrayBuffer och rendrar "Unable to
//      run Embedded Project" istället för en tydlig 4xx — d.v.s.
//      misslyckandet maskeras som en pseudo-renderad preview.
//   b) Alla framtida features som beror på cross-origin isolation
//      (OPFS, högupplösta perf-counters, vissa wasm-paths) regressar
//      tyst i exakt samma miljö där vi minst märker det.
//
// Därför "befordrar" vi `local-next` → `stackblitz` (för header-
// utvärderingens skull) när `NODE_ENV === "production"`. Operatören
// kan opta ur via `VIEWSER_ALLOW_NO_ISOLATION=1` — namnet är
// avsiktligt brusigt eftersom variabeln säger vad den kostar. Det
// ska kräva ett medvetet beslut att stänga av cross-origin
// isolation i produktion, inte ett slip av tangentbordet i en CI-
// config. Spegla värdet i NEXT_PUBLIC-spegeln nedan så ViewerPanel
// får samma vy som server-render och inte spawnar en LocalRuntime-
// klient som ändå skulle blockas av headers.
const IS_PRODUCTION = process.env.NODE_ENV === "production";
const ALLOW_NO_ISOLATION = process.env.VIEWSER_ALLOW_NO_ISOLATION === "1";
const effectiveMode =
  IS_PRODUCTION && PREVIEW_MODE === "local-next" && !ALLOW_NO_ISOLATION
    ? "stackblitz"
    : PREVIEW_MODE;

// Transport ↔ mode mismatch warning (soft, dev-only).
// ------------------------------------------------------------------
// `stackblitz` / `auto`-läget kräver att Viewser körs över HTTPS för
// att StackBlitz-embeddet ska få cross-origin isolation (COEP
// credentialless + COOP same-origin är meningslöst utan secure
// context — Chrome kräver båda för att SharedArrayBuffer ska
// exponeras inuti den embeddade WebContainer).
//
// `scripts/dev.mjs`-dispatchern hanterar det automatiskt genom att
// passa `--experimental-https` till `next dev` när mode != local-next.
// Men `npm run dev:http` och `npm run dev:https` finns kvar som
// "manuella escape hatchar" (se .env.example) och DE går runt
// dispatchern. Om operatören kör `dev:http` med
// `VIEWSER_PREVIEW_MODE=stackblitz` i .env.local får de "CORS"-fel
// i Chrome som ser ut precis som det LocalRuntime-misslyckande som
// fix-fallback-headers fixar — men rotorsaken är helt annan, och
// utan en explicit guard maskeras det och sänker debuggability.
//
// Soft warning (inte process.exit) eftersom next.config.ts läses även
// vid `next build` och `next start`. NODE_ENV=production-gaten skyddar
// teoretiskt, men en hard-fail som krasch-loopar build:en vid en
// felkonfigurerad shell-env är värre än en ignored warning. Operatören
// får istället en tydlig stderr-rad vid dev-startup som länkar till
// det riktiga fixet, och viewer-panel.tsx ger pedagogiskt felmeddelande
// in-browser om embeddet faktiskt blockas.
// `process.argv` är inte tillförlitlig under Turbopack: nästans config
// laddas i worker-processer vars argv inte ärver parent-processens
// flaggor, så `--experimental-https` syns inte ens när Next-CLI:n
// startades med den. Vi konsulterar därför primärt `VIEWSER_DISPATCHER_HTTPS`
// — env-variabeln som `scripts/dev.mjs` sätter när dispatchern valt
// https-grenen — och faller tillbaka till argv-checken för operatörer
// som kör `next dev --experimental-https` direkt (utan dispatchern).
const HAS_EXPERIMENTAL_HTTPS =
  process.env.VIEWSER_DISPATCHER_HTTPS === "1" ||
  process.argv.includes("--experimental-https");
const ALLOW_TRANSPORT_MISMATCH =
  process.env.VIEWSER_ALLOW_TRANSPORT_MISMATCH === "1";
const STACKBLITZ_MODE_REQUIRES_HTTPS =
  effectiveMode === "stackblitz" || effectiveMode === "auto";
if (
  !IS_PRODUCTION &&
  STACKBLITZ_MODE_REQUIRES_HTTPS &&
  !HAS_EXPERIMENTAL_HTTPS &&
  !ALLOW_TRANSPORT_MISMATCH
) {
  process.stderr.write(
    `\n[viewser/next.config] VARNING: VIEWSER_PREVIEW_MODE=${PREVIEW_MODE}` +
      ` förväntar HTTPS men --experimental-https saknas i process.argv.\n` +
      `StackBlitz-embeddet kräver cross-origin isolation och kommer\n` +
      `troligen blockas av Chrome med "Specify a Cross-Origin Embedder Policy".\n\n` +
      `Fix:\n` +
      `  1. Använd \`npm run dev\` (dispatchern i scripts/dev.mjs väljer\n` +
      `     rätt transport baserat på VIEWSER_PREVIEW_MODE), eller\n` +
      `  2. Kör \`npm run dev:https\` istället för \`dev:http\`, eller\n` +
      `  3. Sätt VIEWSER_PREVIEW_MODE=local-next i .env.local om du inte\n` +
      `     behöver StackBlitz-fallback (default-vägen för operator-bygda\n` +
      `     sajter).\n\n` +
      `Tysta varningen (medveten override): VIEWSER_ALLOW_TRANSPORT_MISMATCH=1.\n`,
  );
}

const nextConfig: NextConfig = {
  // ``@preview-runtime`` är ett tsconfig-path-alias som pekar på delad TS-källa
  // utanför app-roten (``../../packages/preview-runtime/src``). tsc resolvar det
  // via ``paths``, men Turbopack (BÅDE ``next dev`` och ``next build``)
  // inkluderar aldrig moduler vars riktiga sökväg ligger utanför den inferrade
  // projektroten — så utan detta 500:ar preview-routen i dev och bygget failar.
  // Bite C är första konsumenten som faktiskt RUNTIME-importerar paketet
  // (``app/api/preview/[siteId]`` → ``lib/preview-runtime-server.ts``). Därför:
  //   - ``turbopack.root`` breddar bygg-/dev-roten till repo-roten (``REPO_ROOT``,
  //     beräknad från configens egen filsökväg — pålitligare än ``process.cwd()``
  //     under Turbopacks worker-processer) så ``../../packages`` ingår i modulgrafen.
  //   - ``resolveAlias`` pekar specifieraren på TS-källans index.
  // De repo-rot-baserade runtime-sökvägarna i ``lib/*-runner.ts`` (python-spawn
  // mot ``.venv`` m.m.) görs opaka för Turbopacks statiska analys (se
  // ``repoRoot()`` där) så den bredare roten inte får output-tracern att
  // försöka inkludera t.ex. ``.venv``-symlänkar som pekar ut ur repo-roten.
  turbopack: {
    root: REPO_ROOT,
    resolveAlias: {
      "@preview-runtime": "../../packages/preview-runtime/src/index.ts",
    },
  },
  // Hostad deploybarhet (FAS 2A): ``/api/discovery-options`` läser
  // governance-policyfiler och scaffold-variant-JSON via ``fs`` vid runtime.
  // På Vercel inkluderar output-tracern bara filer som faktiskt importeras —
  // runtime-``fs``-läsningar utanför app-roten bundlas inte automatiskt och
  // skulle saknas i funktionen (routern degraderar då ärligt, men wizarden
  // tappar sina alternativ). ``outputFileTracingRoot`` breddar spårnings-roten
  // till repo-roten så monorepo-filer utanför app-katalogen får följa med, och
  // ``outputFileTracingIncludes`` pekar ut exakt de policy-/variantfiler routern
  // behöver så de hamnar i serverless-bundlen.
  outputFileTracingRoot: REPO_ROOT,
  outputFileTracingIncludes: {
    "/api/discovery-options": [
      "../../governance/policies/discovery-taxonomy.v1.json",
      "../../governance/policies/scaffold-contract.v1.json",
      "../../packages/generation/orchestration/scaffolds/**/variants/*.json",
    ],
  },
  // Spegla läget till klienten så ViewerPanel kan ta beslut baserat
  // på det (t.ex. skippa StackBlitz-fallbacken när vi vet att vi kör
  // LocalRuntime). NEXT_PUBLIC_-prefixet är vad Next.js kräver för att
  // exponera variabler i browserbundlen.
  //
  // Vi exponerar RAW `PREVIEW_MODE` (operatörens uttryckta intent),
  // INTE `effectiveMode` (server-headers-utfallet efter production-
  // gaten). Skälet: gaten är medvetet en server-side säkerhets-rail
  // för cross-origin isolation, inte en omtolkning av operatörens
  // runtime-val. Att smitta klient-runtime-besluten med gate-utfallet
  // skulle göra production-läget oförutsägbart för en operator som
  // explicit valt local-next (AI Bug Review-fynd 84% på PR #88). En
  // framtida ViewerPanel-konsument kan självständigt välja att
  // korsreferera mot fetch:ade headers om den behöver veta vad servern
  // ACT settle:ade på.
  env: {
    NEXT_PUBLIC_VIEWSER_PREVIEW_MODE: PREVIEW_MODE,
  },
  async headers() {
    // Tom header-lista för local-next OCH vercel-sandbox. COEP
    // credentialless + COOP same-origin skulle annars blockera en
    // cross-origin iframe:
    //   - local-next  → localhost:<4100-4199> (annan port, cross-origin).
    //   - vercel-sandbox → publik …vercel.run-https-URL (cross-origin).
    // Ingendera behöver cross-origin isolation (det krävs bara av
    // StackBlitz/WebContainers för SharedArrayBuffer). En publik https-iframe
    // bäddas utan isolation (ADR 0033). Notera: `effectiveMode`, inte
    // `PREVIEW_MODE` — production-gaten ovanför promotar bara local-next, så
    // vercel-sandbox passerar oförändrad hit även i NODE_ENV=production.
    if (effectiveMode === "local-next" || effectiveMode === "vercel-sandbox") {
      return [];
    }

    // StackBlitz-grenen (och `auto` / okänt värde): behåll de
    // cross-origin-isolation-headers som WebContainers kräver.
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Cross-Origin-Embedder-Policy", value: "credentialless" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
