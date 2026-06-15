import {
  Callout,
  Card,
  CardBody,
  CardHeader,
  Code,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  Pill,
  Row,
  Stack,
  Stat,
  Swatch,
  Table,
  Text,
  useCanvasState,
  useHostTheme,
} from "cursor/canvas";

// ---------------------------------------------------------------------------
// Delad canvas - kanonisk kopia i repot: docs/canvases/
// Spegla till Cursors canvas-mapp med: python scripts/sync_canvases.py
//
// Steward-revision (read-only scout): LLM-floden + OpenClaw-floden, hur de
// speglas i chatten, vad som ar implementerat/kvar/i synk, och en grundad
// stadnings-rekommendation for tester/docs/governance mot ett 9/10 LLM-flode.
//
// Kallor (repo, kartlagt 2026-06-15): packages/generation/** (orchestration,
// planning, brief, codegen, quality_gate, repair), governance/policies/
// llm-models.v1.json (v13), docs/testing.md, docs/current-focus.md + handoff,
// docs/canvases/ (systerkartor). Siffror raknade ur repot.
// ---------------------------------------------------------------------------

type Status = "finns" | "delvis" | "planerat" | "input";

type StepDef = {
  canonical: string;
  status: Status;
  statusNote: string;
  what: string;
  files: string;
  model: string;
};

const STEPS: Record<string, StepDef> = {
  // --- INIT (Golden Path) ---
  prompt: {
    canonical: "Prompt (init)",
    status: "input",
    statusNote: "Ingangspunkt.",
    what: "Fri text fran kunden. mode=init gar Golden Path direkt - forbi konduktoren - och bygger alltid en forsta version.",
    files: "apps/viewser/app/api/prompt/route.ts",
    model: "-",
  },
  brief: {
    canonical: "Fas 1 Understand -> Site Brief",
    status: "finns",
    statusNote: "Real-modell med mock-fallback utan nyckel.",
    what: "Extraherar bransch, malgrupp, ton, erbjudande och kontakt ur prompten till en strukturerad Site Brief.",
    files: "packages/generation/brief/extract.py",
    model: "briefModel - gpt-5.4 (medium)",
  },
  plan: {
    canonical: "Fas 2 Plan -> Site Plan / Blueprint",
    status: "finns",
    statusNote: "Delad produce_site_plan; real + mock-fallback.",
    what: "Valjer scaffold, route-hints, sektioner och dossier-rationale. Lyft till tyngre reasoning i v13.",
    files: "packages/generation/planning/{plan,blueprint}.py",
    model: "planningModel - gpt-5.5 (high)",
  },
  codegen: {
    canonical: "Fas 3 Build -> Codegen",
    status: "finns",
    statusNote: "Smalt kontrakt (ADR 0017): rationale + riskNotes.",
    what: "Deterministisk renderare bygger Next.js-filerna ur Generation Package. Modellen genererar inte filinnehall an.",
    files: "packages/generation/codegen/codegen.py",
    model: "codegenModel - gpt-5.4 (medium)",
  },
  quality: {
    canonical: "Quality Gate (+ verifier)",
    status: "finns",
    statusNote: "Deterministisk critic + read-only smak-critic.",
    what: "Kor typecheck/route-scan/build-status/policy + grundnings-grindar (t.ex. directive_leak). verifierModel mergar smak-findings, blockerar aldrig.",
    files: "packages/generation/quality_gate/{gate,critic,verifier}.py",
    model: "verifierModel - gpt-5.5 (high)",
  },
  repair: {
    canonical: "Repair Pipeline",
    status: "finns",
    statusNote: "Mekaniska fixes + LLM-fix nar mekanik inte racker.",
    what: "Forsoker laga det Quality Gate hittade via registrerade fixes; faller tillbaka pa LLM-fix sist.",
    files: "packages/generation/repair/{orchestration,repair}.py",
    model: "repairModel - gpt-5.4 (medium)",
  },
  previewInit: {
    canonical: "Preview (init)",
    status: "finns",
    statusNote: "vercel-sandbox primar, local-next fallback.",
    what: "Den byggda sajten renderas i preview-iframen. Forsta versionen ar nu synlig for kunden.",
    files: "packages/preview-runtime/** - ADR 0033",
    model: "-",
  },

  // --- FOLLOWUP (OpenClaw conductor) ---
  chat: {
    canonical: "Foljdprompt (chat)",
    status: "input",
    statusNote: "Samma ruta som init.",
    what: "Kunden skriver smaprat, en fraga, en asikt eller en riktig andringsbegaran. mode=followup gar till konduktoren.",
    files: "apps/viewser/components/builder/floating-chat.tsx",
    model: "-",
  },
  gate: {
    canonical: "Samtalsgrind (classify)",
    status: "finns",
    statusNote: "Forsta grinden - splittrar bygg vs chat-svar.",
    what: "Avgor om meddelandet ar en edit eller inte. Bara edits gar vidare till KOR-kedjan; allt annat besvaras i chatten utan ny version.",
    files: "packages/generation/orchestration/openclaw/roles.py",
    model: "klassning (router)",
  },
  router: {
    canonical: "Router 6a (+ routerModel 6b)",
    status: "finns",
    statusNote: "Deterministisk bas + valfri LLM-fallback.",
    what: "Klassar editKind (visual_style / copy_change / section_add ...) och valjer konduktor-roll. routerModel anropas bara nar heuristiken ar osaker/multi-intent.",
    files: "packages/generation/orchestration/router/{classify,llm_fallback}.py",
    model: "routerModel - gpt-5.5 (high)",
  },
  context: {
    canonical: "Context 7a",
    status: "finns",
    statusNote: "Las-bar.",
    what: "Samlar exakt det underlag patchen behover (Project Input, sektioner, artefakter) styrt av contextLevel.",
    files: "packages/generation/orchestration/context/",
    model: "-",
  },
  patch: {
    canonical: "Patch 7b",
    status: "finns",
    statusNote: "Validerad plan, transient.",
    what: "Foreslar en strukturerad, validerad patch-plan mot Project Input-lagret. Aldrig fri patch i genererade filer.",
    files: "packages/generation/orchestration/patch/",
    model: "copy/style-direktiv",
  },
  apply: {
    canonical: "Apply 7c -> Input vN+1",
    status: "finns",
    statusNote: "Skriver nasta oforanderliga version.",
    what: "Applicerar patch-planen och skriver Project Input vN+1. Bara per-sajt-lagret - aldrig delade scaffolds/dossiers.",
    files: "packages/generation/orchestration/apply/",
    model: "-",
  },
  build: {
    canonical: "Targeted build 7d -> ny run",
    status: "finns",
    statusNote: "Kors via run_followup_chain (CLI-bryggan).",
    what: "Bygger om det som behovs, skapar ny runId och pointer-swappar current.json sa preview pekar pa nya versionen.",
    files: "scripts/build_site.py -> run_followup_chain",
    model: "-",
  },
  previewFollow: {
    canonical: "Preview-refresh + svar",
    status: "finns",
    statusNote: "Iframe laddas om; arlighetssignaler applied/visibleEffect.",
    what: "Preview pekar pa nya versionen och kunden far bade strukturerat resultat och ett konversationssvar.",
    files: "apps/viewser/ preview-flode",
    model: "-",
  },
  chatReply: {
    canonical: "Chat-svar (ingen ny version)",
    status: "finns",
    statusNote: "3 av 4 konduktor-utfall landar har.",
    what: "answer_only / clarification / plan_only besvaras direkt i chatten med SOUL-personan - ingen build, ingen version skrivs. Detta ar fixen for 'chatten bygger i onodan'.",
    files: "apps/viewser/lib/openai.ts (chatWithOpenAi) + SOUL.md",
    model: "chat-helper - gpt-5.5 (env)",
  },
};

type NodeGeom = {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  role?: string;
};

const NODE_H = 44;
const INIT_Y = 92;
const FOLLOW_Y = 224;

const NODES: NodeGeom[] = [
  // Init rail (w=126, step 148, start 22)
  { id: "prompt", x: 22, y: INIT_Y, w: 126, h: NODE_H, label: "Prompt" },
  { id: "brief", x: 170, y: INIT_Y, w: 126, h: NODE_H, label: "Site Brief", role: "briefModel" },
  { id: "plan", x: 318, y: INIT_Y, w: 126, h: NODE_H, label: "Site Plan", role: "planningModel" },
  { id: "codegen", x: 466, y: INIT_Y, w: 126, h: NODE_H, label: "Codegen", role: "codegenModel" },
  { id: "quality", x: 614, y: INIT_Y, w: 126, h: NODE_H, label: "Quality Gate", role: "+ verifierModel" },
  { id: "repair", x: 762, y: INIT_Y, w: 126, h: NODE_H, label: "Repair", role: "+ repairModel" },
  { id: "previewInit", x: 910, y: INIT_Y, w: 126, h: NODE_H, label: "Preview" },
  // Followup rail (w=112, step 132, start 14)
  { id: "chat", x: 14, y: FOLLOW_Y, w: 112, h: NODE_H, label: "Foljdprompt" },
  { id: "gate", x: 146, y: FOLLOW_Y, w: 112, h: NODE_H, label: "Samtalsgrind", role: "classify" },
  { id: "router", x: 278, y: FOLLOW_Y, w: 112, h: NODE_H, label: "Router 6a", role: "+ routerModel" },
  { id: "context", x: 410, y: FOLLOW_Y, w: 112, h: NODE_H, label: "Context 7a" },
  { id: "patch", x: 542, y: FOLLOW_Y, w: 112, h: NODE_H, label: "Patch 7b" },
  { id: "apply", x: 674, y: FOLLOW_Y, w: 112, h: NODE_H, label: "Apply 7c", role: "Input vN+1" },
  { id: "build", x: 806, y: FOLLOW_Y, w: 112, h: NODE_H, label: "Build 7d", role: "ny run" },
  { id: "previewFollow", x: 938, y: FOLLOW_Y, w: 112, h: NODE_H, label: "Preview" },
  // Chat-only branch
  { id: "chatReply", x: 300, y: 336, w: 320, h: 40, label: "Chat-svar (ingen ny version)", role: "SOUL-persona" },
];

type EdgeDef = { path: string; from: string; to: string; dashed?: boolean };

const EDGES: EdgeDef[] = [
  // Init rail (center y = 114)
  { from: "prompt", to: "brief", path: "M148,114 L170,114" },
  { from: "brief", to: "plan", path: "M296,114 L318,114" },
  { from: "plan", to: "codegen", path: "M444,114 L466,114" },
  { from: "codegen", to: "quality", path: "M592,114 L614,114" },
  { from: "quality", to: "repair", path: "M740,114 L762,114" },
  { from: "repair", to: "previewInit", path: "M888,114 L910,114" },
  // Followup rail (center y = 246)
  { from: "chat", to: "gate", path: "M126,246 L146,246" },
  { from: "gate", to: "router", path: "M258,246 L278,246" },
  { from: "router", to: "context", path: "M390,246 L410,246" },
  { from: "context", to: "patch", path: "M522,246 L542,246" },
  { from: "patch", to: "apply", path: "M654,246 L674,246" },
  { from: "apply", to: "build", path: "M786,246 L806,246" },
  { from: "build", to: "previewFollow", path: "M918,246 L938,246" },
  // Chat-only branch off the gate
  { from: "gate", to: "chatReply", path: "M202,268 C202,318 460,300 460,336", dashed: true },
];

const STATUS_LABEL: Record<Status, string> = {
  finns: "Finns & korr",
  delvis: "Delvis",
  planerat: "Planerat",
  input: "Ingang",
};

function FlowMap({
  selected,
  onSelect,
}: {
  selected: string;
  onSelect: (id: string) => void;
}) {
  const t = useHostTheme();
  const statusColor = (s: Status) =>
    s === "finns"
      ? t.category.green
      : s === "delvis"
        ? t.category.yellow
        : s === "input"
          ? t.category.blue
          : t.category.gray;

  const neighbors = new Set<string>();
  EDGES.forEach((e) => {
    if (e.from === selected) neighbors.add(e.to);
    if (e.to === selected) neighbors.add(e.from);
  });

  const bandLabel = { fontSize: 10, letterSpacing: 1.1 } as const;

  return (
    <div style={{ overflowX: "auto" }}>
      <svg
        viewBox="0 0 1064 400"
        style={{ width: "100%", minWidth: 900, display: "block", fontFamily: "inherit" }}
        role="img"
        aria-label="LLM-floden: init Golden Path och foljdprompt-konduktoren, med chat-svar utan bygge"
      >
        <defs>
          <marker id="rv-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
            <path d="M0,0 L8,4 L0,8 z" fill={t.stroke.primary} />
          </marker>
          <marker id="rv-arrow-hot" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
            <path d="M0,0 L8,4 L0,8 z" fill={t.accent.primary} />
          </marker>
        </defs>

        {/* Lagerband */}
        <rect x={8} y={58} width={1048} height={116} rx={10} fill={t.fill.quaternary} />
        <text x={22} y={76} fill={t.text.tertiary} style={bandLabel}>
          INIT - GOLDEN PATH - INGEN KONDUKTOR, BYGGER ALLTID FORSTA VERSIONEN
        </text>

        <rect x={8} y={190} width={1048} height={116} rx={10} fill={t.fill.quaternary} />
        <text x={22} y={208} fill={t.text.tertiary} style={bandLabel}>
          FOLJDPROMPT - OPENCLAW-KONDUKTOR - GRINDEN AVGOR BYGG vs CHAT-SVAR
        </text>

        {/* Kanter */}
        {EDGES.map((e) => {
          const hot = e.from === selected || e.to === selected;
          return (
            <path
              key={`${e.from}-${e.to}`}
              d={e.path}
              fill="none"
              stroke={hot ? t.accent.primary : t.stroke.primary}
              strokeWidth={hot ? 1.8 : 1.1}
              strokeDasharray={e.dashed ? "5 4" : undefined}
              markerEnd={hot ? "url(#rv-arrow-hot)" : "url(#rv-arrow)"}
            />
          );
        })}

        {/* Noder */}
        {NODES.map((n) => {
          const s = STEPS[n.id];
          const isSel = selected === n.id;
          const isNb = neighbors.has(n.id);
          const cx = n.x + n.w / 2;
          return (
            <g key={n.id} onClick={() => onSelect(n.id)} style={{ cursor: "pointer" }}>
              <title>{`${s.canonical} - ${STATUS_LABEL[s.status]}`}</title>
              <rect
                x={n.x}
                y={n.y}
                width={n.w}
                height={n.h}
                rx={8}
                fill={isSel ? t.fill.secondary : t.bg.elevated}
                stroke={isSel || isNb ? t.accent.primary : t.stroke.primary}
                strokeWidth={isSel ? 2 : 1.2}
                strokeOpacity={isNb && !isSel ? 0.55 : 1}
              />
              <text
                x={cx}
                y={n.y + n.h / 2 + 4}
                textAnchor="middle"
                fontSize={11}
                fontWeight={isSel ? 600 : 500}
                fill={t.text.primary}
              >
                {n.label}
              </text>
              <circle cx={n.x + n.w - 10} cy={n.y + 10} r={4} fill={statusColor(s.status)} />
              {n.role ? (
                <text x={cx} y={n.y + n.h + 13} textAnchor="middle" fontSize={9} fill={t.text.tertiary}>
                  {n.role}
                </text>
              ) : null}
            </g>
          );
        })}

        {/* Branch-etikett */}
        <text x={250} y={316} fontSize={10} textAnchor="middle" fill={t.text.tertiary} stroke={t.bg.editor} strokeWidth={3} paintOrder="stroke">
          answer / clarify / plan -&gt; svar utan bygge
        </text>
      </svg>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <Stack gap={2}>
      <Text size="small" tone="tertiary" weight="semibold">{label}</Text>
      <Text size="small" tone="secondary">{value}</Text>
    </Stack>
  );
}

function StepDetail({ selected }: { selected: string }) {
  const s = STEPS[selected] ?? STEPS.gate;
  return (
    <Card>
      <CardHeader trailing={<Pill size="sm" active>{STATUS_LABEL[s.status]}</Pill>}>
        {s.canonical}
      </CardHeader>
      <CardBody>
        <Stack gap={14}>
          <Text>{s.what}</Text>
          <Grid columns={3} gap={14}>
            <Field label="FIL & PLATS" value={s.files} />
            <Field label="MODELL / ROLL" value={s.model} />
            <Field label="STATUS" value={s.statusNote} />
          </Grid>
        </Stack>
      </CardBody>
    </Card>
  );
}

// Status: implementerat / kvar / i synk (capabilities)
type CapTone = "success" | "warning" | "danger" | "info" | "neutral";
const CAPABILITIES: Array<{ name: string; status: string; tone: CapTone }> = [
  { name: "Init Golden Path (brief -> plan -> codegen -> QG -> repair)", status: "Finns - prod-E2E bevisad", tone: "success" },
  { name: "Foljdprompt restyle (tema/brand/ton, stylist)", status: "Finns", tone: "success" },
  { name: "Foljdprompt copy (copyDirective + editPlan)", status: "Finns", tone: "success" },
  { name: "Foljdprompt section_add (faq/team synlig, pricing -> /priser)", status: "Delvis - reviews/trust an stub", tone: "warning" },
  { name: "Route/Nav Mutation V1 (ta bort sida + nav + lankar)", status: "Saknas - hogsta prio (current-focus)", tone: "danger" },
  { name: "OpenClaw Core decide() -> apply-brygga", status: "Saknas - action_bridge_missing", tone: "danger" },
  { name: "routerModel 6b LLM-fallback / verifierModel critic", status: "Finns", tone: "success" },
  { name: "Preview: vercel-sandbox primar + local-next fallback", status: "Finns (ADR 0033)", tone: "success" },
  { name: "StackBlitz embedded preview", status: "Pausad - Chromium-only", tone: "warning" },
  { name: "Extern Docker-konduktor (Fas 2)", status: "Planerad - medvetet ej byggd (regel 09)", tone: "neutral" },
  { name: "Model routing v13 (gpt-5.5 / gpt-5.4-mini)", status: "Finns - real-key-smoke OK", tone: "success" },
];

// Glapp + obsoleta kedjor
const GAPS: Array<{ title: string; tone: "danger" | "warning" | "info"; body: string }> = [
  {
    title: "Konduktor-brygga saknas (glapp)",
    tone: "danger",
    body: "OpenClaw Core decide() returnerar action_bridge_missing for edits. Faktiska andringar appliceras idag via CLI:n run_openclaw_followup.py -> run_followup_chain, INTE via konduktorsbeslutet. Tva nastan-parallella foljdvagar tills bryggan byggs.",
  },
  {
    title: "Route/Nav Mutation V1 saknas",
    tone: "danger",
    body: "Det gar inte att ta bort en sida/nav/lank. 'ta bort Kontakt' faller till component_remove eller action_bridge_missing. Basal redigeringsformaga - hogre produktvarde an mer katalog-mount.",
  },
  {
    title: "StackBlitz: pausad men kvar (obsolet kedja)",
    tone: "warning",
    body: "7 filer lever kvar (adapter, UI, test, ADR 0003/0021) trots att ADR 0033 gjorde vercel-sandbox primar och produktkompassen markerar StackBlitz pausad. Avskriv formellt eller markera som legacy - annars underhalls/kors dod kod.",
  },
  {
    title: "Canvas-/doc-drift mot koden",
    tone: "warning",
    body: "roller-vs-agenter-canvasen listar 12 Model Roles, men policyn (v13) har 13 (scaffoldModel saknas) och modellerna ar inte uppdaterade (planning/router/verifier = gpt-5.5, rerank = gpt-5.4-mini). docs/testing.md sager '~160 testfiler' men det ar 213.",
  },
  {
    title: "gpt-4o pensionerad som fallback",
    tone: "info",
    body: "Sidoanropens kod-fallback lyftes till gpt-5.5 (2026-06-11). Ingen atgard - men verifiera att inga env-variabler eller dossier-instruktioner fortfarande pekar pa gpt-4o.",
  },
  {
    title: "Fritext -> pahittade service-kort",
    tone: "info",
    body: "Fri prompttext blir ibland stray tjanste-kort kunden aldrig bett om. Avgransa till grundade tjanster (samma arlighets-tema som directive_leak-fixen). Current-focus prio 2.",
  },
];

// Test-portfolj audit (213 filer / 3232 testfall raknade 2026-06-15)
type AuditRow = { family: string; files: string; tier: string; rec: string; tone: CapTone };
const AUDIT: AuditRow[] = [
  {
    family: "Karnkedjan (brief/plan/codegen/quality/repair/router/patch/apply)",
    files: "~40",
    tier: "core (~28 filer i lanen)",
    rec: "BEHALL som kärnskydd. Parametrisera de storsta filerna (route_emission 85, planning 41, patch_apply 35).",
    tone: "success",
  },
  {
    family: "followup_* (tema/copy/sektion/versionering/chain)",
    files: "12",
    tier: "core + sekundär",
    rec: "BEHALL - skyddar foljdprompt-loopen. Slå ihop paritetsfall: copy_directives har 100 testfall -> parametrisera.",
    tone: "success",
  },
  {
    family: "viewser_hosted_* (answer/build_status/run_history/openclaw_apply...)",
    files: "9",
    tier: "saknar tier (-> integration)",
    rec: "Markera 'integration'. Slå ihop till parametriserade hostad-yt-tester; tunga, kor inte i smoke/core.",
    tone: "info",
  },
  {
    family: "viewser_* ovriga (UI-las, security, soul, marketing, stackblitz)",
    files: "23",
    tier: "saknar tier (-> tooling)",
    rec: "Markera 'tooling'. Flera ar source-locks. stackblitz-testet kopplas till obsolet kedja (se glapp).",
    tone: "warning",
  },
  {
    family: "backoffice_* (operatörs-UI/diagnostik - EJ karnloop)",
    files: "22",
    tier: "tooling (delvis omarkerat)",
    rec: "Storsta ihopslagnings-/parametriseringsvinsten. Markera 'tooling'; konsolidera diagnostik-/views-familjen.",
    tone: "warning",
  },
  {
    family: "discovery / sni / industry (goldens)",
    files: "8",
    tier: "sekundär",
    rec: "BEHALL. Parametrisera bransch-goldens (discovery_resolver har 80 testfall).",
    tone: "neutral",
  },
  {
    family: "Historiska bugg-/sprint-las (b163_b171, b154, b157, audit_post_3b, 3c_lite)",
    files: "5",
    tier: "source_lock (foreslaget)",
    rec: "Markera 'source_lock'. Borttag ar operatörsbeslut per fil (egen chore-commit) - redan listade i docs/testing.md.",
    tone: "danger",
  },
  {
    family: "Governance/docs-meta (docs_*, no_legacy, naming, term, cross_policy, repo_boundaries)",
    files: "~12",
    tier: "governance / tooling",
    rec: "BEHALL - snabba och skyddar drift. Ingen radering; dessa ar billiga grindar.",
    tone: "success",
  },
];

// Governance + docs overhead
type GovRow = { area: string; count: string; verdict: string; tone: CapTone };
const GOV: GovRow[] = [
  { area: "ADR / decisions (append-only historik)", count: "59", verdict: "BEHALL - historik, inte friktion. Ev. arkivindex.", tone: "success" },
  { area: "Policies (kontrakt)", count: "21", verdict: "BEHALL - kallan for sanning (ADR 0001).", tone: "success" },
  { area: "Schemas", count: "39", verdict: "BEHALL - laser artefaktkontrakt.", tone: "success" },
  { area: "Rules (aktiva)", count: "13", verdict: "BEHALL - speglas till .cursor/rules via rules_sync.", tone: "success" },
  { area: "Docs .md (totalt / top-level)", count: "160 / 22", verdict: "DRIFTRISK. testing.md inaktuell (160 vs 213). Hall current-focus/handoff korta (regel 07).", tone: "warning" },
  { area: "docs/heavy-llm-flow/ (designspec + historik)", count: "30", verdict: "Konsolidera/indexera - delvis historik blandad med aktiv spec.", tone: "info" },
];

export default function StewardRevision() {
  const [selected, setSelected] = useCanvasState<string>("rvSelected", "gate");

  return (
    <Stack gap={30} style={{ maxWidth: 1160, margin: "0 auto", padding: "24px 16px 56px" }}>
      <Stack gap={6}>
        <H1>Steward-revision: LLM-floden, OpenClaw & vag mot 9/10</H1>
        <Text tone="secondary">
          En read-only scout-karta over <Text weight="semibold">var en LLM faktiskt anropas</Text>,
          hur init- och foljdprompt-floden speglas i chatten, vad som ar byggt/kvar/i synk, och en
          grundad rekommendation for vad i tester/docs/governance som bromsar utan att skydda
          karnflodet <Text weight="semibold">prompt -&gt; hemsida -&gt; preview -&gt; foljdprompt -&gt; ny version</Text>.
        </Text>
      </Stack>

      <Grid columns={4} gap={16}>
        <Stat value="213" label="testfiler (3232 testfall)" tone="warning" />
        <Stat value="13" label="Model Roles (policy v13)" tone="info" />
        <Stat value="59 / 21 / 39 / 13" label="ADR / policies / schemas / rules" />
        <Stat value="2" label="hårda glapp: Route/Nav V1 + action-brygga" tone="danger" />
      </Grid>

      <Callout tone="info" title="Sammanfattning pa en rad">
        Sviten bor <Text weight="semibold">tieras och parametriseras, inte massraderas</Text> -
        och projektet har redan halva jobbet gjort (core-lane + docs/testing.md). De storsta
        verkliga vinsterna: parametrisera paritetstunga filer, markera backoffice/hosted som
        tooling/integration, och stadа obsoleta StackBlitz-spar. Gor det som en
        <Text weight="semibold"> separat slice</Text> - inte mitt i Route/Nav V1.
      </Callout>

      <Stack gap={10}>
        <H2>1. De tva kedjorna (klicka pa en ruta)</H2>
        <Text tone="secondary">
          Init gar Golden Path direkt och bygger alltid. Foljdprompten gar genom konduktoren, dar
          samtalsgrinden splittrar: bara en riktig edit gar hela KOR-kedjan; smaprat/fraga/asikt
          besvaras i chatten utan ny version. Det ar sa samma chattruta speglar tva helt olika utfall.
        </Text>
        <FlowMap selected={selected} onSelect={setSelected} />
        <Row gap={16} align="center" wrap>
          <Row gap={6} align="center"><Swatch color="green" /><Text size="small" tone="secondary">Finns & korr</Text></Row>
          <Row gap={6} align="center"><Swatch color="yellow" /><Text size="small" tone="secondary">Delvis</Text></Row>
          <Row gap={6} align="center"><Swatch color="blue" /><Text size="small" tone="secondary">Ingangspunkt</Text></Row>
          <Row gap={6} align="center"><Swatch color="gray" /><Text size="small" tone="secondary">Planerat</Text></Row>
          <Text size="small" tone="tertiary">Streckad pil = chat-svar utan bygge. Systerkartor: openclaw-floden + roller-vs-agenter-modeller.</Text>
        </Row>
        <StepDetail selected={selected} />
      </Stack>

      <Stack gap={12}>
        <H2>2. Hur det speglas i chatten</H2>
        <Grid columns={2} gap={16}>
          <Card>
            <CardHeader trailing={<Pill size="sm" active>bygger alltid</Pill>}>Init-tur (mode=init)</CardHeader>
            <CardBody>
              <Text size="small">
                Forsta meddelandet. Gar forbi konduktoren rakt in i Golden Path och producerar
                alltid en forsta version + preview. Ingen grind, inget val.
              </Text>
            </CardBody>
          </Card>
          <Card>
            <CardHeader trailing={<Pill size="sm">grind avgor</Pill>}>Foljd-tur (mode=followup)</CardHeader>
            <CardBody>
              <Stack gap={6}>
                <Text size="small">Konduktoren valjer ETT av fyra utfall:</Text>
                <Text size="small">- <Text weight="semibold">answer_only</Text> / <Text weight="semibold">clarification</Text> / <Text weight="semibold">plan_only</Text> -&gt; svar i chatten, ingen ny version.</Text>
                <Text size="small">- <Text weight="semibold">patch_plan_request</Text> -&gt; riktig edit gar KOR-kedjan -&gt; ny version + preview.</Text>
              </Stack>
            </CardBody>
          </Card>
        </Grid>
      </Stack>

      <Stack gap={12}>
        <H2>3. Implementerat / kvar / i synk</H2>
        <Table
          headers={["Förmåga", "Status"]}
          columnAlign={["left", "left"]}
          striped
          rowTone={CAPABILITIES.map((c) => c.tone)}
          rows={CAPABILITIES.map((c) => [c.name, c.status])}
        />
      </Stack>

      <Stack gap={12}>
        <H2>4. Glapp & obsoleta kedjor</H2>
        <Grid columns={2} gap={12}>
          {GAPS.map((g) => (
            <div key={g.title}>
              <Callout tone={g.tone} title={g.title}>
                {g.body}
              </Callout>
            </div>
          ))}
        </Grid>
      </Stack>

      <Stack gap={12}>
        <H2>5. Test-portfolj - audit & rekommendation</H2>
        <Text tone="secondary">
          213 testfiler / 3232 testfall (raknade 2026-06-15). Markorer som finns idag: <Code>core</Code>,
          {" "}<Code>governance</Code>, <Code>tooling</Code>, <Code>slow</Code>, <Code>e2e</Code>,
          {" "}<Code>requires_node</Code>. Saknas: <Code>smoke</Code>, <Code>integration</Code>,
          {" "}<Code>source_lock</Code>. Tre kluster (viewser 32, backoffice 22, followup 12) ar 31% av filerna.
        </Text>
        <Table
          headers={["Testfamilj", "Filer", "Nivå idag", "Rekommendation"]}
          columnAlign={["left", "right", "left", "left"]}
          striped
          rowTone={AUDIT.map((a) => a.tone)}
          rows={AUDIT.map((a) => [a.family, a.files, a.tier, a.rec])}
        />
        <Callout tone="neutral" title="Tier-modell (additiv - inga raderingar kravs for steg 1)">
          smoke (30-90s, saknas idag) · core (~28 filer, FINNS) · integration (hostad/preview, foreslagen)
          · slow/e2e/requires_node (FINNS) · source_lock (historiska las, foreslagen). Lagg markorerna
          forst; parametrisering och ev. radering ar senare, granskade steg.
        </Callout>
      </Stack>

      <Stack gap={12}>
        <H2>6. Governance & docs - overhead vs skydd</H2>
        <Text tone="secondary">
          Governance ska skydda riktningen, inte kvava bygget (produktkompassen). Slutsats: kontrakten
          (policies/schemas/rules/ADR) ar inte problemet - de ar billiga och styr ratt. Friktionen
          sitter i <Text weight="semibold">doc-drift</Text> och spridd designspec.
        </Text>
        <Table
          headers={["Område", "Antal", "Bedömning"]}
          columnAlign={["left", "right", "left"]}
          striped
          rowTone={GOV.map((g) => g.tone)}
          rows={GOV.map((g) => [g.area, g.count, g.verdict])}
        />
      </Stack>

      <Stack gap={12}>
        <H2>7. Rekommenderad ordning</H2>
        <Grid columns={2} gap={16}>
          <Card>
            <CardHeader trailing={<Pill size="sm" active>Builder - nu</Pill>}>Karnvardet forst</CardHeader>
            <CardBody>
              <Stack gap={6}>
                <Text size="small">1. Fortsatt <Text weight="semibold">Route/Nav Mutation V1</Text> (ta bort sida/nav/lank) - hogsta produktvardet. Ror INTE testsviten samtidigt.</Text>
                <Text size="small">2. Avgransa fritext -&gt; grundade tjanste-kort (arlighet).</Text>
              </Stack>
            </CardBody>
          </Card>
          <Card>
            <CardHeader trailing={<Pill size="sm">Scout/Steward - parallellt</Pill>}>Billiga, read-only-nara</CardHeader>
            <CardBody>
              <Stack gap={6}>
                <Text size="small">3. Uppdatera <Code>docs/testing.md</Code> (213/3232) + synka canvas-fakta (lagg scaffoldModel + v13-modeller i roller-canvasen).</Text>
                <Text size="small">4. Lagg additiva markorer i <Code>pyproject.toml</Code>: smoke / integration / source_lock. Inga raderingar.</Text>
              </Stack>
            </CardBody>
          </Card>
          <Card>
            <CardHeader trailing={<Pill size="sm">Separat slice</Pill>}>Test Tier Cleanup V1</CardHeader>
            <CardBody>
              <Stack gap={6}>
                <Text size="small">5. Parametrisera paritetstunga filer (copy_directives 100, route_emission 85, discovery_resolver 80).</Text>
                <Text size="small">6. Konsolidera backoffice-diagnostik; markera hosted_* som integration; markera de 5 historiska lasen source_lock.</Text>
              </Stack>
            </CardBody>
          </Card>
          <Card>
            <CardHeader trailing={<Pill size="sm">Operatör / senare</Pill>}>Arkitektur & beslut</CardHeader>
            <CardBody>
              <Stack gap={6}>
                <Text size="small">7. Avskriv/legacy-marka StackBlitz-klustret (7 filer) - operatörsbeslut per fil.</Text>
                <Text size="small">8. Bygg <Text weight="semibold">OpenClaw-action-bryggan</Text> (decide -&gt; KOR-kedjan) sa konduktoren blir en riktig dirigent, inte en parallell beslutsfattare.</Text>
              </Stack>
            </CardBody>
          </Card>
        </Grid>
        <Callout tone="danger" title="Skydda detta - aldrig stada bort">
          followup-versionering, route/nav, preview, secrets, Quality Gate och schema-las. Gor inga
          raderingar mitt i Route/Nav V1. Markorer/parametrisering ar additivt; radering ar
          operatörsbeslut per fil i egen chore-commit (docs/testing.md, regel 04).
        </Callout>
      </Stack>

      <Divider />
      <Stack gap={4}>
        <Text size="small" tone="tertiary">
          Read-only scout-karta - inga filer andrade i koden. Siffror raknade ur repot 2026-06-15.
          Kallor: packages/generation/**, governance/policies/llm-models.v1.json (v13),
          docs/testing.md, docs/current-focus.md + handoff, docs/canvases/.
        </Text>
        <Text size="small" tone="tertiary">
          Delad canvas - kanonisk kopia i docs/canvases/ (git). Spegla lokalt med
          python scripts/sync_canvases.py. Systerkartor: begreppskarta-sajtbyggaren,
          openclaw-floden, roller-vs-agenter-modeller.
        </Text>
      </Stack>
    </Stack>
  );
}
