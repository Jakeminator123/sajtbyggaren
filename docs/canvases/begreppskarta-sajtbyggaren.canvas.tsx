import {
  Callout,
  Card,
  CardBody,
  CardHeader,
  CollapsibleSection,
  Grid,
  H1,
  H2,
  Pill,
  Row,
  Stack,
  Stat,
  Swatch,
  Table,
  Text,
  UsageBar,
  useCanvasState,
  useHostTheme,
} from "cursor/canvas";

// ---------------------------------------------------------------------------
// Delad canvas - kanonisk kopia i repot: docs/canvases/
// Spegla till Cursors canvas-mapp med: python scripts/sync_canvases.py
// Steward ansvarar for att fakta-blocket nedan matchar main
// (python scripts/update_canvas_facts.py).
//
// Killor: governance/policies/naming-dictionary.v1.json (v29), docs/glossary.md,
// governance/policies/engine-run.v1.json, page-quality-traits.v1.json,
// ADR 0005 / 0012 / 0015 / 0027 / 0036 / 0039, docs/current-focus.md.
// ---------------------------------------------------------------------------

// AUTOGEN_REPO_FACTS_START -- skrivs av scripts/update_canvas_facts.py, redigera inte for hand
const REPO_FACTS = {
  generatedAt: "2026-06-10",
  scaffoldsOnDisk: 6,
  scaffoldsInRegistry: 14,
  softDossiers: 13,
  hardDossiers: 0,
  qualityTargetScore: 9.0,
  qualityGateScore: 8.6,
  qualityBlockBelow: 7.5,
} as const;
// AUTOGEN_REPO_FACTS_END

// Steward uppdaterar dessa manuellt vid varje pass (kommer fran docs/current-focus.md
// och arkiverade audits - de kan inte raknas fram automatiskt fran filsystemet).
const QUALITY_TELEMETRY = {
  asOf: "2026-06-10",
  goldenPathRealLlm: 8.2,
  goldenPathDeterministic: 7.75,
  perceivedLow: 4,
  perceivedHigh: 5,
} as const;

// ---------------------------------------------------------------------------
// Data: begrepp, noder och kopplingar
// ---------------------------------------------------------------------------

type ConceptStatus = "finns" | "delvis" | "planerat";

type Concept = {
  id: string;
  canonical: string;
  status: ConceptStatus;
  statusNote: string;
  what: string;
  mnemonic: string;
  files: string;
  producer: string;
  consumer: string;
  aliases?: string;
  pitfall?: string;
};

const CONCEPTS: Record<string, Concept> = {
  prompt: {
    id: "prompt",
    canonical: "Init Prompt",
    status: "finns",
    statusNote: "Ren text — ingen egen artefaktfil.",
    what: "Operatörens/kundens råa textbeskrivning. Startpunkten för allt — ingen struktur, bara text.",
    mnemonic: "Det kunden faktiskt skrev.",
    files: "Råtext; bevaras i `input.json` och som `rawPrompt` i `site-brief.json`.",
    producer: "Operatör/kund (t.ex. via Viewser `/api/prompt`).",
    consumer: "`scripts/prompt_to_project_input.py`, Discovery Resolver, `briefModel`.",
  },
  projectInput: {
    id: "projectInput",
    canonical: "Project Input",
    status: "finns",
    statusNote: "Fullt implementerad: schema, 8 exempel, versionerade runtime-filer.",
    what: "Strukturerad JSON med kundfakta och val: företag, tjänster, ton, kontakt — plus pinnad scaffoldId/variantId och valda dossiers. Byggarens primära indata.",
    mnemonic: "Kundfakta + val, på burk.",
    files: "`examples/<siteId>.project-input.json` · `data/prompt-inputs/<siteId>.vN.project-input.json` · schema: `governance/schemas/project-input.schema.json`",
    producer: "`scripts/prompt_to_project_input.py`, Discovery Resolver, follow-up-merge, manuell författning.",
    consumer: "`scripts/build_site.py` (via flaggan `--dossier`!), Viewser `/api/prompt`, evals.",
    aliases: "Tillåtet alias: Deep Brief. Förbjudet: det gamla sajtmaskin-namnet med 'Site' framför dossier.",
    pitfall: "Kallas \u201ddossier\u201d i CLI-flaggan och i kodvariabler — men är INTE en Dossier. Två olika saker delar ordet.",
  },
  siteBrief: {
    id: "siteBrief",
    canonical: "Site Brief",
    status: "finns",
    statusNote: "Fullt implementerad; `briefSource` anger real/mock-sanning.",
    what: "Fas 1 (Understand): LLM:ns strukturerade tolkning av prompten — språk, ton, målgrupp, kapabiliteter och eventuella blueprint-fältgrupper. Inte fritext.",
    mnemonic: "Maskinens tolkning av kundens ord.",
    files: "`data/runs/<runId>/site-brief.json` · schema: `governance/schemas/site-brief.schema.json`",
    producer: "`briefModel` via `packages/generation/brief/extract.py` (mock-fallback utan API-nyckel).",
    consumer: "`produce_site_plan` (Fas 2), `planning/blueprint.py`, Quality Critic.",
    aliases: "Förbjudet: bara \u201dbrief\u201d och gamla sajtmaskin-brief-namn. OBS: \u201dDeep Brief\u201d är alias för Project Input — inte för Site Brief!",
  },
  sitePlan: {
    id: "sitePlan",
    canonical: "Site Plan",
    status: "finns",
    statusNote: "Fullt implementerad; `planSource` anger real/mock/pinned.",
    what: "Fas 2 (Plan): beslutet. Vilken scaffold, variant och starter, vilka rutter och sektioner, vilka dossiers. Här blir biblioteket till en konkret sajtidé.",
    mnemonic: "Beslutet: vad som ska byggas.",
    files: "`data/runs/<runId>/site-plan.json` · schema: `governance/schemas/site-plan.schema.json`",
    producer: "`packages/generation/planning/plan.py` → `produce_site_plan()`.",
    consumer: "Generation Package, codegen, `build_site.py`.",
    aliases: "Förbjudet: bara \u201dplan\u201d, scaffoldPlan.",
  },
  generationPackage: {
    id: "generationPackage",
    canonical: "Generation Package",
    status: "finns",
    statusNote: "Fullt implementerad.",
    what: "Den enda payload som codegen-LLM:en får se (plus refererad brief/plan). Bär blueprint-grupperna contentBlocks, visualDirection och qualityRisks.",
    mnemonic: "Allt codegen får veta.",
    files: "`data/runs/<runId>/generation-package.json` · schema: `governance/schemas/generation-package.schema.json`",
    producer: "Paketeras deterministiskt från Site Brief + Site Plan.",
    consumer: "`codegenModel` (Fas 3).",
  },
  codegenResult: {
    id: "codegenResult",
    canonical: "CodegenResult",
    status: "finns",
    statusNote: "Deterministisk v1 implementerad; bredare riktiga codegen-anrop kommer senare.",
    what: "Fas 3:s manifest i minnet: listan över filer som skrivs (pages, dossier-mounts, starter-patchar) med källa och roll per fil. Persisteras inte som egen fil (ADR 0015).",
    mnemonic: "Kvittot på vilka filer som skrevs.",
    files: "Endast i minnet · kod: `packages/generation/codegen/{codegen,models}.py` · syns via `build-result.json`",
    producer: "`codegenModel` + deterministisk codegen v1.",
    consumer: "Quality Gate, Repair Pipeline, byggsteget.",
    aliases: "Säg inte \u201dcodegen manifest\u201d — `manifest.json` är dossier-metadata, en annan sak.",
  },
  builtSite: {
    id: "builtSite",
    canonical: "Byggd sajt (Generated Files + Build)",
    status: "finns",
    statusNote: "Fullt implementerad via `build_site.py` + npm.",
    what: "Det körbara Next.js-projektet: starter-bas + scaffold-grammatik + dossier-mounts + variant-tokens, byggt med npm install/build.",
    mnemonic: "Slutprodukten kunden ser i preview.",
    files: "`../sajtbyggaren-output/.generated/<siteId>/builds/<timestamp>/` · `data/runs/<runId>/generated-files/`",
    producer: "`scripts/build_site.py` Fas 3 + npm.",
    consumer: "Preview (Viewser: local-next eller vercel-sandbox), Quality Gate.",
  },
  scaffold: {
    id: "scaffold",
    canonical: "Scaffold",
    status: "delvis",
    statusNote: `${REPO_FACTS.scaffoldsOnDisk} av ${REPO_FACTS.scaffoldsInRegistry} registrerade har komplett paket på disk.`,
    what: "Sajtens grammatik: vilka rutter och sektioner som får finnas, kvalitetsregler och vilka dossiers som är kompatibla. Ingen körbar kod — det är Starterns jobb.",
    mnemonic: "Grammatiken — vad en sådan här sajt FÅR innehålla.",
    files: "`packages/generation/orchestration/scaffolds/<id>/` (scaffold.json, routes.json, sections.json, quality-contract.json, variants/) · registry: `scaffold-contract.v1.json`",
    producer: "Governance/författare · kandidater via `data/scaffold-candidates/`.",
    consumer: "Planering, dossier-kompatibilitetsfilter, renderers, codegen-ruttlista.",
    aliases: "Förbjudet: template, boilerplate, pack.",
    pitfall: "Registryt listar fler scaffolds än vad som finns fullt utbyggt på disk — resten är registrerade/planerade.",
  },
  variant: {
    id: "variant",
    canonical: "Scaffold Variant",
    status: "finns",
    statusNote: "Implementerad med schema + kandidatflöde via backoffice.",
    what: "Visuellt uttryck inom en scaffold: färg-, typografi-, radius-, spacing- och motion-tokens plus tonvibb. Definierar aldrig rutter, sektioner eller dossiers.",
    mnemonic: "Utseendet — aldrig strukturen.",
    files: "`scaffolds/<scaffoldId>/variants/<variantId>.json` · schema: `governance/schemas/variant.schema.json`",
    producer: "Governance · kandidater: `scripts/generate_variant_candidate.py` → `data/variant-candidates/`.",
    consumer: "`produce_site_plan`, `build/tokens.py` (CSS-variabler), Project Input-pin.",
    aliases: "Förbjudet: theme, skin, style.",
  },
  dossier: {
    id: "dossier",
    canonical: "Dossier",
    status: "delvis",
    statusNote: `${REPO_FACTS.softDossiers} soft-dossiers implementerade; hard-klassen är tom (planerad).`,
    what: "Återanvändbar kapabilitets-legobit (soft = statisk, hard = kräver backend). En mapp med manifest.json + instructions.md. Inte kundspecifik.",
    mnemonic: "Legobiten med en funktion.",
    files: "`packages/generation/orchestration/dossiers/soft/` · `hard/` (planerad) · schema: `governance/schemas/dossier.schema.json`",
    producer: "Governance · intag: `scripts/dossier_candidate_intake.py`.",
    consumer: "Site Plan (urval), `build_site.py` (montering), capability-map.",
    aliases: "Förbjudet: package, plugin, feature, samt alla gamla dossier-prefix från sajtmaskin (hybrid-klassen togs bort i ADR 0012).",
    pitfall: "Delar ordet med CLI:ts `--dossier`, som betyder Project Input. Står något \u201ddossier\u201d nära byggvägar — läs det som Project Input, om det inte ligger under `orchestration/dossiers/`.",
  },
  starter: {
    id: "starter",
    canonical: "Starter",
    status: "finns",
    statusNote: "Implementerad i `data/starters/`.",
    what: "Den körbara Next.js-basen som allt monteras i. Teknisk grund; scaffoldens grammatik patchas ovanpå. Väljs via SCAFFOLD_TO_STARTER-mappningen.",
    mnemonic: "Den körbara basen.",
    files: "`data/starters/<starterId>/` · pekas ut av `site-plan.json: starterId`",
    producer: "Underhålls som del av repot.",
    consumer: "Fas 3-bygget (starter-patched-filer i CodegenResult).",
    pitfall: "Förväxlas ofta med Scaffold. Scaffold = grammatik, Starter = kod. Fanns inte i ursprungslistan — förtjänar en plats i vokabulären.",
  },
  projectDna: {
    id: "projectDna",
    canonical: "Project DNA",
    status: "delvis",
    statusNote: "V1 partiell i meta-sidecar (ADR 0027); `dna.json` är V2-scope.",
    what: "Projektets beständiga minne mellan versioner: scaffold-lås, variant, dossiers, tema-tokens, språk och ruttbas. Styr vad en follow-up-prompt får ändra.",
    mnemonic: "Det projektet ÄR mellan versionerna.",
    files: "Idag: `projectDna` i `data/prompt-inputs/<siteId>.meta.json` · Mål (V2): `data/projects/<projectId>/dna.json` · policy: `project-dna.v1.json`",
    producer: "Init-körning skapar; follow-up läser och patchar semantiskt.",
    consumer: "Follow-up-routing, `followup/theme_directives.py`, OpenClaw-regler.",
    aliases: "Förbjudet: projectState, projectMeta. \u201dSite DNA\u201d är inte kanoniskt.",
    pitfall: "Policyn finns men implementationen är bara delvis på plats — lätt att tro att `dna.json` redan skrivs. Blanda inte ihop med blueprint: DNA = identitet mellan körningar, blueprint = plan/copy-intention inom en körning.",
  },
  blueprint: {
    id: "blueprint",
    canonical: "Blueprint (fältgrupper)",
    status: "delvis",
    statusNote: "Fältgrupperna definierade (ADR 0036); Blueprint Repair (kor-5) under utbyggnad.",
    what: "Inte en artefakt — ett samlingsnamn för 8 valfria fältgrupper som bor inuti tre befintliga artefakter. `site-blueprint.json` är medvetet avvisad (ADR 0036).",
    mnemonic: "Copy/plan-intentionen INUTI artefakterna — ingen egen fil.",
    files: "Ingen egen fil! Fälten bor i site-brief / site-plan / generation-package · kod: `packages/generation/planning/blueprint.py`",
    producer: "`briefModel` (brief-grupperna), deterministisk härledning (plan/paket-grupperna), Blueprint Repair via `repairModel`.",
    consumer: "Renderer, Quality Critic, patch-planner, Repair Pipeline.",
    pitfall: "Lätt att blanda ihop med Project DNA. DNA = vad projektet är (mellan körningar); blueprint = plan/copy-intention (inom en körning). Leta aldrig efter blueprint.json i produktionsvägar — bara testfixturer använder det formatet.",
  },
};

type NodeGeom = {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  lines: string[];
  fontSize?: number;
};

const NODE_W = 116;
const NODE_H = 44;

const NODES: NodeGeom[] = [
  { id: "scaffold", x: 200, y: 64, w: NODE_W, h: NODE_H, lines: ["Scaffold"] },
  { id: "variant", x: 350, y: 64, w: NODE_W, h: NODE_H, lines: ["Variant"] },
  { id: "dossier", x: 500, y: 64, w: NODE_W, h: NODE_H, lines: ["Dossier"] },
  { id: "starter", x: 650, y: 64, w: NODE_W, h: NODE_H, lines: ["Starter"] },
  { id: "prompt", x: 28, y: 210, w: NODE_W, h: NODE_H, lines: ["Init Prompt"] },
  { id: "projectInput", x: 170, y: 210, w: NODE_W, h: NODE_H, lines: ["Project Input"] },
  { id: "siteBrief", x: 312, y: 210, w: NODE_W, h: NODE_H, lines: ["Site Brief"] },
  { id: "sitePlan", x: 454, y: 210, w: NODE_W, h: NODE_H, lines: ["Site Plan"] },
  { id: "generationPackage", x: 596, y: 210, w: NODE_W, h: NODE_H, lines: ["Generation", "Package"] },
  { id: "codegenResult", x: 738, y: 210, w: NODE_W, h: NODE_H, lines: ["CodegenResult"], fontSize: 11 },
  { id: "builtSite", x: 880, y: 210, w: NODE_W, h: NODE_H, lines: ["Byggd sajt"] },
  { id: "projectDna", x: 170, y: 374, w: 170, h: NODE_H, lines: ["Project DNA"] },
];

type EdgeDef = {
  from: string;
  to: string;
  label: string;
  path: string;
  labelX: number;
  labelY: number;
  anchor?: "start" | "middle" | "end";
};

const EDGES: EdgeDef[] = [
  // Pipelinen (vanster -> hoger)
  { from: "prompt", to: "projectInput", label: "prompt_to_project_input", path: "M 144,232 L 168,232", labelX: 157, labelY: 190 },
  { from: "projectInput", to: "siteBrief", label: "Fas 1 · briefModel", path: "M 286,232 L 310,232", labelX: 299, labelY: 190 },
  { from: "siteBrief", to: "sitePlan", label: "Fas 2 · produce_site_plan", path: "M 428,232 L 452,232", labelX: 441, labelY: 190 },
  { from: "sitePlan", to: "generationPackage", label: "paketering", path: "M 570,232 L 594,232", labelX: 583, labelY: 190 },
  { from: "generationPackage", to: "codegenResult", label: "Fas 3 · codegen", path: "M 712,232 L 736,232", labelX: 725, labelY: 190 },
  { from: "codegenResult", to: "builtSite", label: "filer + npm build", path: "M 854,232 L 878,232", labelX: 867, labelY: 190 },
  // Biblioteket internt
  { from: "scaffold", to: "variant", label: "har varianter", path: "M 316,86 L 348,86", labelX: 333, labelY: 56 },
  // Bibliotek -> korning
  { from: "scaffold", to: "projectInput", label: "scaffoldId pinnas", path: "M 258,108 C 258,150 210,168 210,208", labelX: 222, labelY: 152, anchor: "end" },
  { from: "scaffold", to: "sitePlan", label: "rutter & sektioner", path: "M 258,108 C 258,164 484,154 484,208", labelX: 368, labelY: 148 },
  { from: "variant", to: "projectInput", label: "variantId pinnas", path: "M 408,108 C 408,150 228,170 228,208", labelX: 318, labelY: 168 },
  { from: "variant", to: "sitePlan", label: "tokens → CSS-variabler", path: "M 408,108 C 408,150 502,168 502,208", labelX: 452, labelY: 162 },
  { from: "dossier", to: "projectInput", label: "selectedDossiers", path: "M 558,108 C 558,158 246,178 246,208", labelX: 402, labelY: 178 },
  { from: "dossier", to: "sitePlan", label: "dossierval i planen", path: "M 558,108 C 558,150 520,168 520,208", labelX: 548, labelY: 152, anchor: "start" },
  { from: "dossier", to: "codegenResult", label: "dossier-mount", path: "M 558,108 C 558,162 796,154 796,208", labelX: 676, labelY: 146 },
  { from: "starter", to: "sitePlan", label: "starterId mappas", path: "M 708,108 C 708,152 538,172 538,208", labelX: 622, labelY: 166 },
  { from: "starter", to: "builtSite", label: "körbar bas patchas", path: "M 708,108 C 708,162 938,154 938,208", labelX: 822, labelY: 144 },
  // Korning <-> projektminne
  { from: "projectInput", to: "projectDna", label: "init: skapar / uppdaterar", path: "M 238,254 C 238,304 268,322 268,372", labelX: 278, labelY: 316, anchor: "start" },
  { from: "projectDna", to: "projectInput", label: "follow-up: läser lås", path: "M 242,374 C 242,324 214,306 214,256", labelX: 204, labelY: 320, anchor: "end" },
];

const BLUEPRINT_MEMBERS = ["siteBrief", "sitePlan", "generationPackage"];

const STATUS_LABEL: Record<ConceptStatus, string> = {
  finns: "Finns",
  delvis: "Delvis",
  planerat: "Planerat",
};

// ---------------------------------------------------------------------------
// Kartan (SVG)
// ---------------------------------------------------------------------------

function ConceptMap({
  selected,
  onSelect,
}: {
  selected: string;
  onSelect: (id: string) => void;
}) {
  const t = useHostTheme();

  const statusColor = (s: ConceptStatus) =>
    s === "finns" ? t.category.green : s === "delvis" ? t.category.yellow : t.category.gray;

  const hotEdges = EDGES.filter((e) => e.from === selected || e.to === selected);
  const dimEdges = EDGES.filter((e) => e.from !== selected && e.to !== selected);
  const neighborIds = new Set<string>(
    selected === "blueprint"
      ? BLUEPRINT_MEMBERS
      : hotEdges.map((e) => (e.from === selected ? e.to : e.from)),
  );

  const bandLabel = { fontSize: 10, letterSpacing: 1.2 } as const;

  const renderEdge = (e: EdgeDef, hot: boolean) => (
    <path
      key={`${e.from}-${e.to}`}
      d={e.path}
      fill="none"
      stroke={hot ? t.accent.primary : t.stroke.primary}
      strokeWidth={hot ? 1.8 : 1.1}
      markerEnd={hot ? "url(#bk-arrow-hot)" : "url(#bk-arrow-dim)"}
    />
  );

  return (
    <div style={{ overflowX: "auto" }}>
      <svg
        viewBox="0 0 1040 446"
        style={{ width: "100%", minWidth: 880, display: "block", fontFamily: "inherit" }}
        role="img"
        aria-label="Begreppskarta över Sajtbyggarens artefakter och bibliotek"
      >
        <defs>
          <marker id="bk-arrow-dim" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
            <path d="M0,0 L8,4 L0,8 z" fill={t.stroke.primary} />
          </marker>
          <marker id="bk-arrow-hot" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
            <path d="M0,0 L8,4 L0,8 z" fill={t.accent.primary} />
          </marker>
        </defs>

        {/* Lagerband */}
        <rect x={16} y={30} width={1008} height={92} rx={10} fill={t.fill.quaternary} />
        <text x={28} y={48} fill={t.text.tertiary} style={bandLabel}>
          BIBLIOTEK · ÅTERANVÄNDBARA DEFINITIONER (VERSIONERAS I REPO)
        </text>

        <rect x={16} y={156} width={1008} height={146} rx={10} fill={t.fill.quaternary} />
        <text x={28} y={174} fill={t.text.tertiary} style={bandLabel}>
          {"EN KÖRNING · ENGINE RUN → data/runs/<runId>/"}
        </text>

        <rect x={16} y={340} width={1008} height={92} rx={10} fill={t.fill.quaternary} />
        <text x={28} y={358} fill={t.text.tertiary} style={bandLabel}>
          PROJEKTMINNE · BESTÄNDIGT MELLAN VERSIONER
        </text>

        {/* Kanter: dimmade forst, markerade overst */}
        {dimEdges.map((e) => renderEdge(e, false))}
        {hotEdges.map((e) => renderEdge(e, true))}

        {/* Blueprint-overlay runt de tre artefakter som bar faltgrupperna */}
        <g onClick={() => onSelect("blueprint")} style={{ cursor: "pointer" }}>
          <title>Blueprint — 8 fältgrupper utan egen fil</title>
          <rect
            x={304}
            y={200}
            width={416}
            height={64}
            rx={10}
            fill="none"
            stroke={selected === "blueprint" ? t.accent.primary : t.stroke.primary}
            strokeWidth={selected === "blueprint" ? 2 : 1.2}
            strokeDasharray="6 4"
          />
          <circle cx={400} cy={280} r={4} fill={statusColor("delvis")} />
          <text
            x={410}
            y={284}
            fontSize={11}
            fill={selected === "blueprint" ? t.accent.primary : t.text.secondary}
          >
            Blueprint — 8 fältgrupper, ingen egen fil
          </text>
        </g>

        {/* Noder */}
        {NODES.map((n) => {
          const c = CONCEPTS[n.id];
          const isSel = selected === n.id;
          const isNeighbor = neighborIds.has(n.id);
          const cx = n.x + n.w / 2;
          return (
            <g key={n.id} onClick={() => onSelect(n.id)} style={{ cursor: "pointer" }}>
              <title>{`${c.canonical} · ${STATUS_LABEL[c.status]}`}</title>
              <rect
                x={n.x}
                y={n.y}
                width={n.w}
                height={n.h}
                rx={8}
                fill={isSel ? t.fill.secondary : t.bg.elevated}
                stroke={isSel || isNeighbor ? t.accent.primary : t.stroke.primary}
                strokeWidth={isSel ? 2 : 1.2}
                strokeOpacity={isNeighbor && !isSel ? 0.55 : 1}
              />
              {n.lines.length === 1 ? (
                <text
                  x={cx}
                  y={n.y + n.h / 2 + 4}
                  textAnchor="middle"
                  fontSize={n.fontSize ?? 12}
                  fontWeight={isSel ? 600 : 500}
                  fill={t.text.primary}
                >
                  {n.lines[0]}
                </text>
              ) : (
                <text
                  x={cx}
                  textAnchor="middle"
                  fontSize={n.fontSize ?? 12}
                  fontWeight={isSel ? 600 : 500}
                  fill={t.text.primary}
                >
                  <tspan x={cx} y={n.y + n.h / 2 - 3}>{n.lines[0]}</tspan>
                  <tspan x={cx} y={n.y + n.h / 2 + 11}>{n.lines[1]}</tspan>
                </text>
              )}
              <circle cx={n.x + n.w - 10} cy={n.y + 10} r={4} fill={statusColor(c.status)} />
            </g>
          );
        })}

        {/* Etiketter for markerade kanter (med halo sa de syns ovanpa allt) */}
        {hotEdges.map((e) => (
          <text
            key={`label-${e.from}-${e.to}`}
            x={e.labelX}
            y={e.labelY}
            fontSize={10}
            textAnchor={e.anchor ?? "middle"}
            fill={t.accent.primary}
            stroke={t.bg.editor}
            strokeWidth={3}
            paintOrder="stroke"
          >
            {e.label}
          </text>
        ))}
      </svg>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detaljpanel
// ---------------------------------------------------------------------------

function Field({ label, value }: { label: string; value: string }) {
  return (
    <Stack gap={2}>
      <Text size="small" tone="tertiary" weight="semibold">{label}</Text>
      <Text size="small" tone="secondary">{value}</Text>
    </Stack>
  );
}

function ConceptDetail({ selected }: { selected: string }) {
  const c = CONCEPTS[selected] ?? CONCEPTS.projectInput;

  const connections: string[] =
    c.id === "blueprint"
      ? [
          "→ Site Brief · businessFacts, positioning, contentStrategy, conversion",
          "→ Site Plan · sectionPlan",
          "→ Generation Package · contentBlocks, visualDirection, qualityRisks",
        ]
      : EDGES.filter((e) => e.from === c.id || e.to === c.id).map((e) => {
          const outgoing = e.from === c.id;
          const other = CONCEPTS[outgoing ? e.to : e.from];
          return `${outgoing ? "→" : "←"} ${other.canonical} · ${e.label}`;
        });

  return (
    <Card>
      <CardHeader trailing={<Pill size="sm" active>{STATUS_LABEL[c.status]}</Pill>}>
        {c.canonical}
      </CardHeader>
      <CardBody>
        <Stack gap={14}>
          <Stack gap={4}>
            <Text>{c.what}</Text>
            <Text italic tone="secondary" size="small">Minnesregel: {c.mnemonic}</Text>
          </Stack>
          <Grid columns={2} gap={14}>
            <Field label="FIL & PLATS" value={c.files} />
            <Field label="STATUS" value={c.statusNote} />
            <Field label="SKAPAS AV" value={c.producer} />
            <Field label="ANVÄNDS AV" value={c.consumer} />
          </Grid>
          {c.aliases ? <Field label="NAMNREGLER (NAMING-DICTIONARY)" value={c.aliases} /> : null}
          {connections.length > 0 ? (
            <Stack gap={4}>
              <Text size="small" tone="tertiary" weight="semibold">KOPPLINGAR I KARTAN</Text>
              {connections.map((line) => (
                <div key={line}>
                  <Text size="small" tone="secondary">{line}</Text>
                </div>
              ))}
            </Stack>
          ) : null}
          {c.pitfall ? (
            <Callout tone="warning" title="Fallgrop">{c.pitfall}</Callout>
          ) : null}
        </Stack>
      </CardBody>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Faser mot 9/10
// ---------------------------------------------------------------------------

type PhaseStatus = "done" | "inProgress" | "partial" | "planned";

type Phase = {
  id: string;
  title: string;
  status: PhaseStatus;
  doneMeans: string;
  evidence: string;
  note?: string;
};

const PHASES: Phase[] = [
  {
    id: "p1",
    title: "P1 · Motorgrund (Sprint 1–3B)",
    status: "done",
    doneMeans:
      "Brief → plan → bygge → quality gate (4 checkar) → mekanisk repair → första riktiga codegen-anropet.",
    evidence: "ADR 0014–0017 · packages/generation/{codegen,quality_gate,repair}/",
  },
  {
    id: "p2",
    title: "P2 · Blueprint + tung LLM-orkestrering (kor-0…7d)",
    status: "done",
    doneMeans:
      "Blueprint-fältgrupper, deterministisk critic + verifier, blueprint repair, router och hela follow-up-kedjan finns i kod.",
    evidence: "docs/heavy-llm-flow/README.md (status 2026-06-04) · packages/generation/orchestration/",
    note: "Klart i kod — återstoden är wiring och eval, inte nya kor-kort.",
  },
  {
    id: "p3",
    title: "P3 · Produktloop-wiring (Viewser + OpenClaw-konduktör)",
    status: "inProgress",
    doneMeans:
      "Chatten bygger inte i onödan; follow-up → apply → preview fungerar sömlöst; F1 slice 3 (section_builder-dispatch, stylist-scope) landad.",
    evidence: "docs/current-focus.md · PR #259–#262 · docs/heavy-llm-flow/openclaw-2.0-conductor.md",
  },
  {
    id: "p4",
    title: "P4 · Preview- och drifthärdning",
    status: "inProgress",
    doneMeans:
      "vercel-sandbox som primär preview, pre-built upload, prune/recovery-buggar stängda (B163–B175).",
    evidence: "ADR 0033 · PR #257, #263",
  },
  {
    id: "p5",
    title: "P5 · Trovärdighet & copy (upplevd kvalitet)",
    status: "partial",
    doneMeans:
      "Ingen fejkad kontakt, trust-signaler renderas, branschnära copy i stället för generiska mallar.",
    evidence: "Trovärdighets-slice steg 1 klart · B166 · docs/archive/current-focus-2026-06-08-pre-slim.md",
    note: "Största dokumenterade hävstången för att stänga gapet mellan mätt 8.2 och upplevd ~4–5.",
  },
  {
    id: "p6",
    title: "P6 · Sprint 3C-full — automatisk 9.0-poängsättning",
    status: "planned",
    doneMeans:
      "Femte quality-gate-checken poängsätter 10 viktade traits; promotion kräver viktat snitt ≥ gate och ingen trait under blockBelow.",
    evidence: "governance/policies/page-quality-traits.v1.json · docs/architecture/builder-mvp.md",
  },
  {
    id: "p7",
    title: "P7 · Bevisad 9/10 på fyra baslinjeföretag",
    status: "planned",
    doneMeans:
      "Elektriker, frisör, naprapat och keramik-e-handel: fri prompt + följdprompter + manuellt scorecard ≥ 9, i linje med golden path och traits.",
    evidence: "docs/product-operating-context.md (första kvalitetsbaseline) · docs/evals.md",
  },
];

const PHASE_STATUS_LABEL: Record<PhaseStatus, string> = {
  done: "KLART",
  inProgress: "PÅGÅR",
  partial: "DELVIS",
  planned: "PLANERAT",
};

function phaseSwatchColor(status: PhaseStatus): "green" | "blue" | "yellow" | "gray" {
  if (status === "done") return "green";
  if (status === "inProgress") return "blue";
  if (status === "partial") return "yellow";
  return "gray";
}

function QualityScale() {
  const t = useHostTheme();
  const x = (v: number) => 40 + v * 92;
  const f = REPO_FACTS;
  const q = QUALITY_TELEMETRY;

  return (
    <div style={{ overflowX: "auto" }}>
      <svg
        viewBox="0 0 1000 104"
        style={{ width: "100%", minWidth: 760, display: "block", fontFamily: "inherit" }}
        role="img"
        aria-label="Kvalitetsskala 0 till 10 med dagens mätvärden och målet 9.0"
      >
        {/* Skallinje med andpunktsmarkeringar */}
        <line x1={x(0)} y1={52} x2={x(10)} y2={52} stroke={t.stroke.primary} strokeWidth={2} />
        {[0, 2, 4, 6, 8, 10].map((v) => (
          <g key={v}>
            <line x1={x(v)} y1={46} x2={x(v)} y2={58} stroke={t.stroke.primary} strokeWidth={1} />
            <text x={x(v)} y={74} fontSize={10} textAnchor="middle" fill={t.text.quaternary}>
              {v}
            </text>
          </g>
        ))}

        {/* Upplevd kvalitet (coach) som band */}
        <rect
          x={x(q.perceivedLow)}
          y={45}
          width={x(q.perceivedHigh) - x(q.perceivedLow)}
          height={14}
          fill={t.category.yellow}
          fillOpacity={0.35}
        />
        <text x={x((q.perceivedLow + q.perceivedHigh) / 2)} y={92} fontSize={10} textAnchor="middle" fill={t.text.secondary}>
          upplevd kvalitet ~{q.perceivedLow}–{q.perceivedHigh} (coach)
        </text>

        {/* Deterministisk golden path */}
        <line x1={x(q.goldenPathDeterministic)} y1={42} x2={x(q.goldenPathDeterministic)} y2={62} stroke={t.text.tertiary} strokeWidth={2} />
        <text x={x(q.goldenPathDeterministic)} y={92} fontSize={10} textAnchor="end" fill={t.text.secondary}>
          deterministisk {q.goldenPathDeterministic}
        </text>

        {/* Golden path med riktig LLM */}
        <line x1={x(q.goldenPathRealLlm)} y1={42} x2={x(q.goldenPathRealLlm)} y2={62} stroke={t.category.green} strokeWidth={2.5} />
        <text x={x(q.goldenPathRealLlm)} y={32} fontSize={10} textAnchor="end" fill={t.text.secondary}>
          golden path (riktig LLM) {q.goldenPathRealLlm}
        </text>

        {/* Gate och mal fran page-quality-traits */}
        <line x1={x(f.qualityGateScore)} y1={40} x2={x(f.qualityGateScore)} y2={64} stroke={t.text.secondary} strokeWidth={1.5} strokeDasharray="3 3" />
        <text x={x(f.qualityGateScore)} y={92} fontSize={10} textAnchor="middle" fill={t.text.secondary}>
          gate {f.qualityGateScore}
        </text>

        <line x1={x(f.qualityTargetScore)} y1={38} x2={x(f.qualityTargetScore)} y2={66} stroke={t.accent.primary} strokeWidth={3} />
        <text x={x(f.qualityTargetScore)} y={32} fontSize={11} fontWeight={600} textAnchor="start" fill={t.accent.primary}>
          mål {f.qualityTargetScore.toFixed(1)}
        </text>
      </svg>
    </div>
  );
}

function PhasesSection() {
  const doneCount = PHASES.filter((p) => p.status === "done").length;
  const activeCount = PHASES.filter((p) => p.status === "inProgress" || p.status === "partial").length;
  const plannedCount = PHASES.filter((p) => p.status === "planned").length;

  return (
    <Stack gap={16}>
      <H2>Faser mot 9/10</H2>
      <Text tone="secondary">
        Målet är formellt definierat i `page-quality-traits.v1.json`: viktat snitt{" "}
        <Text weight="semibold">{REPO_FACTS.qualityTargetScore.toFixed(1)} av 10</Text> (worldclass-lite),
        promotion-gate {REPO_FACTS.qualityGateScore}, ingen trait under {REPO_FACTS.qualityBlockBelow}.
        Skalan nedan visar var bygget står i dag — och faserna visar vägen dit.
      </Text>
      <QualityScale />
      <Text size="small" tone="tertiary">
        Källa: golden path-eval (`data/evals/summaries/golden-path/`) + coach-audit · siffror per{" "}
        {QUALITY_TELEMETRY.asOf}. Gapet mellan mätt 8.2 och upplevd ~4–5 är dokumenterat — evalen
        mäter struktur, inte känsla. P5 är bron.
      </Text>
      <Grid columns={3} gap={16}>
        <Stat value={`${doneCount}/${PHASES.length}`} label="Faser klara" tone="success" />
        <Stat value={activeCount} label="Pågår eller delvis" tone="info" />
        <Stat value={plannedCount} label="Planerade" />
      </Grid>
      <Stack gap={2}>
        {PHASES.map((p) => (
          <div key={p.id}>
            <CollapsibleSection
              title={p.title}
              leading={<Swatch color={phaseSwatchColor(p.status)} />}
              trailing={
                <Text size="small" tone="tertiary" weight="semibold">
                  {PHASE_STATUS_LABEL[p.status]}
                </Text>
              }
            >
              <Stack gap={6}>
                <Text size="small" tone="secondary">
                  <Text size="small" weight="semibold">Klart betyder:</Text> {p.doneMeans}
                </Text>
                <Text size="small" tone="tertiary">Evidens: {p.evidence}</Text>
                {p.note ? <Text size="small" italic tone="secondary">{p.note}</Text> : null}
              </Stack>
            </CollapsibleSection>
          </div>
        ))}
      </Stack>
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Vad finns / vad fattas
// ---------------------------------------------------------------------------

function GapSection() {
  const f = REPO_FACTS;
  return (
    <Stack gap={16}>
      <H2>Vad finns — och vad fattas?</H2>
      <Grid columns={4} gap={16}>
        <Stat value={`${f.scaffoldsOnDisk} / ${f.scaffoldsInRegistry}`} label="Scaffolds fullt på disk" tone="warning" />
        <Stat value={f.softDossiers} label="Soft-dossiers implementerade" tone="success" />
        <Stat value={f.hardDossiers} label="Hard-dossiers (planerade)" tone="warning" />
        <Stat value="8" label="Blueprint-fältgrupper på 3 artefakter" tone="info" />
      </Grid>
      <UsageBar
        total={f.scaffoldsInRegistry}
        topLeftLabel="Scaffold-registry: byggt vs. endast registrerat"
        topRightLabel={`${f.scaffoldsOnDisk} av ${f.scaffoldsInRegistry} har komplett paket`}
        segments={[{ id: "built", value: f.scaffoldsOnDisk, color: "green" }]}
      />
      <Table
        headers={["Begrepp", "Status", "Finns idag", "Fattas / nästa steg"]}
        striped
        rowTone={[
          "success",
          "success",
          "success",
          "success",
          "warning",
          "success",
          "warning",
          "success",
          "warning",
          "warning",
        ]}
        rows={[
          ["Site Brief", "Finns", "Schema, Fas 1, briefSource-sanning", "Blueprint-grupper fylls bara med riktig LLM-nyckel"],
          ["Site Plan", "Finns", "Schema, produce_site_plan, pinned-stöd", "—"],
          ["Generation Package", "Finns", "Schema + deterministisk paketering", "—"],
          ["CodegenResult", "Finns", "Deterministisk codegen v1 + Quality Gate", "Bredare riktiga codegen-anrop"],
          ["Scaffold", "Delvis", `${f.scaffoldsOnDisk} kompletta paket på disk`, `${f.scaffoldsInRegistry - f.scaffoldsOnDisk} registrerade utan mapp på disk`],
          ["Scaffold Variant", "Finns", "Schema, varianter per scaffold, kandidatflöde", "Fler varianter per scaffold"],
          ["Dossier", "Delvis", `${f.softDossiers} soft under orchestration/dossiers/soft/`, `Hard-klassen är tom (${f.hardDossiers} st)`],
          ["Starter", "Finns", "Körbar Next.js-bas i data/starters/", "—"],
          ["Blueprint", "Delvis", "8 fältgrupper definierade (ADR 0036)", "Blueprint repair (kor-5) mognar fortfarande"],
          ["Project DNA", "Delvis", "V1 i meta-sidecar (ADR 0027)", "data/projects/<id>/dna.json är V2-scope"],
        ]}
      />
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Kommentar: overflodigt, forvirrande, saknat
// ---------------------------------------------------------------------------

function CommentSection() {
  return (
    <Stack gap={16}>
      <H2>Kommentar: överflödigt, förvirrande och saknat</H2>
      <Callout tone="warning" title="”dossier” är överlastat — den enda riktiga städuppgiften">
        CLI-flaggan `--dossier` i `scripts/build_site.py` pekar på en Project Input-fil, inte på en
        Dossier (kapabilitetsmodulen). Två helt olika saker delar alltså ordet i vardagen.
        Rekommendation: inför `--project-input` som alias och fasa ut `--dossier` ur CLI och
        kodvariabler.
      </Callout>
      <Callout tone="info" title="”blueprint” är inget substantiv i filsystemet">
        ADR 0036 avvisade `site-blueprint.json` medvetet — ordet är bara ett samlingsnamn för
        8 fältgrupper som bor i tre befintliga artefakter. Begreppet behövs, men säg hellre
        ”blueprint-fälten” än ”blueprinten”, så ingen letar efter en fil som inte finns.
      </Callout>
      <Callout tone="neutral" title="Inget av de sex begreppen är överflödigt — de täcker olika lager">
        Scaffold, Variant och Dossier är bibliotek (återanvändbara definitioner). Site Brief är en
        körningsartefakt. Project DNA är projektminne. Blueprint är språkligt svagast (osynligt i
        filsystemet) men konceptet fyller en lucka ingen annan term täcker.
      </Callout>
      <Callout tone="info" title="Begrepp som saknades i ursprungslistan men bär lika mycket vikt">
        Project Input (det CLI:t kallar ”dossier”!), Starter (den körbara basen — förväxlas ständigt
        med Scaffold), Generation Package (codegens enda payload), Engine Run (hela körningen) och
        CodegenResult (fil-kvittot). Med dessa fem på plats hänger hela kedjan ihop.
      </Callout>
      <Stack gap={8}>
        <H2>Säg inte — säg i stället</H2>
        <Table
          headers={["Säg inte", "Säg i stället", "Varför"]}
          striped
          rows={[
            ["theme / skin / style", "Scaffold Variant", "Förbjudna alias i naming-dictionary; tokens är inte ett tema"],
            ["template / boilerplate / pack", "Scaffold eller Starter", "Grammatik (Scaffold) och körbar bas (Starter) är olika saker"],
            ["brief (ensamt)", "Site Brief", "”Deep Brief” är alias för Project Input — inte Site Brief!"],
            ["dossier med Site-/Feature-prefix", "Project Input resp. Dossier", "Gammal sajtmaskin-förvirring, uttryckligen förbjuden"],
            ["gamla delta-brief-namnet", "(utgått)", "Globalt förbjudet sajtmaskin-arv"],
            ["package / plugin / feature", "Dossier", "Kapabilitetsmodulen har ett kanoniskt namn"],
            ["projectState / projectMeta / Site DNA", "Project DNA", "Ett kanoniskt namn för projektminnet"],
            ["codegen manifest", "CodegenResult", "manifest.json är dossier-metadata — en annan sak"],
          ]}
        />
      </Stack>
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Huvudkomponent
// ---------------------------------------------------------------------------

export default function BegreppskartaSajtbyggaren() {
  const [selected, setSelected] = useCanvasState<string>("selectedConcept", "projectInput");

  return (
    <Stack gap={28} style={{ maxWidth: 1120, margin: "0 auto", padding: "24px 16px 48px" }}>
      <Stack gap={6}>
        <H1>Begreppskarta: Sajtbyggarens artefakter</H1>
        <Text tone="secondary">
          Tre lager håller isär allt: <Text weight="semibold">biblioteket</Text> (återanvändbara
          definitioner), <Text weight="semibold">en körning</Text> (artefakter per Engine Run) och{" "}
          <Text weight="semibold">projektminnet</Text> (det som överlever mellan versioner). Klicka
          på en ruta i kartan så lyser dess kopplingar upp och detaljerna visas under.
        </Text>
      </Stack>

      <Stack gap={10}>
        <ConceptMap selected={selected} onSelect={setSelected} />
        <Row gap={16} align="center" wrap>
          <Row gap={6} align="center">
            <Swatch color="green" />
            <Text size="small" tone="secondary">Finns & används</Text>
          </Row>
          <Row gap={6} align="center">
            <Swatch color="yellow" />
            <Text size="small" tone="secondary">Delvis — luckor finns</Text>
          </Row>
          <Row gap={6} align="center">
            <Swatch color="gray" />
            <Text size="small" tone="secondary">Planerat / endast registrerat</Text>
          </Row>
          <Text size="small" tone="tertiary">
            Pilarna visar dataflöde och urval; streckad ram = blueprint-fältens hem.
          </Text>
        </Row>
      </Stack>

      <ConceptDetail selected={selected} />

      <PhasesSection />

      <GapSection />

      <CommentSection />

      <Stack gap={4}>
        <Text size="small" tone="tertiary">
          Delad canvas — kanonisk kopia i `docs/canvases/` (git). Steward håller fakta-blocket i synk
          med main via `python scripts/update_canvas_facts.py`; spegla lokalt med
          `python scripts/sync_canvases.py`. Systerkarta: `openclaw-floden.canvas.tsx`.
        </Text>
        <Text size="small" tone="tertiary">
          Källor: `governance/policies/naming-dictionary.v1.json` (v29), `docs/glossary.md`,
          `governance/policies/engine-run.v1.json`, `page-quality-traits.v1.json`,
          ADR 0005 / 0012 / 0015 / 0027 / 0036 / 0039 · fakta per {REPO_FACTS.generatedAt}.
        </Text>
      </Stack>
    </Stack>
  );
}
