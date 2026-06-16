import {
  Callout,
  Card,
  CardBody,
  CardHeader,
  Grid,
  H1,
  H2,
  Pill,
  Row,
  Stack,
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
// Killor: governance/rules/09-openclaw-and-site-mutations.md,
// docs/heavy-llm-flow/openclaw-2.0-conductor.md, kor-o1-openclaw-core-contract.md,
// docs/openclaw-workspace/ (SOUL, TOOLS, action-registry.json),
// packages/generation/orchestration/openclaw/, docs/current-focus.md (2026-06-10).
// ---------------------------------------------------------------------------

type StepStatus = "finns" | "delvis" | "planerat";

type Step = {
  id: string;
  canonical: string;
  status: StepStatus;
  statusNote: string;
  what: string;
  files: string;
  notes?: string;
};

const STEPS: Record<string, Step> = {
  floatingChat: {
    id: "floatingChat",
    canonical: "FloatingChat (Viewser)",
    status: "finns",
    statusNote: "Live i operatörsprototypen.",
    what: "Chattytan där operatören/kunden skriver init-prompter och följdprompter. Samma ruta oavsett om meddelandet är småprat, en fråga eller en riktig ändringsbegäran.",
    files: "`apps/viewser/components/builder/`",
  },
  apiPrompt: {
    id: "apiPrompt",
    canonical: "POST /api/prompt",
    status: "finns",
    statusNote: "Live; hanterar både init och followup.",
    what: "Viewsers API-ingång. `mode=init` går Golden Path direkt (utan OpenClaw). `mode=followup` skickas till konduktören. Svaret innehåller runId, beslut och byggstatus.",
    files: "`apps/viewser/app/api/prompt/route.ts`",
    notes: "Chatt-svar för icke-byggande turer genereras här via `chatWithOpenAi` (OpenClaw-personan).",
  },
  runner: {
    id: "runner",
    canonical: "openclaw-runner.ts → CLI-bryggan",
    status: "finns",
    statusNote: "Live; shellar till Python.",
    what: "TypeScript-sidan som kör `scripts/run_openclaw_followup.py --apply` och tolkar resultatet. Detta är sömmen mellan Viewser (Node) och motorn (Python).",
    files: "`apps/viewser/lib/openclaw-runner.ts` · `scripts/run_openclaw_followup.py`",
  },
  docker: {
    id: "docker",
    canonical: "Extern Docker-konduktör (Fas 2)",
    status: "planerat",
    statusNote: "Medvetet INTE byggd ännu — förbjuden i nuvarande fas enligt regel 09.",
    what: "Framtida fristående OpenClaw-gateway (FastAPI-spiken finns lokalt som gitignorerad `openclaw-mvp/`). Ska delegera klassificering till samma router — aldrig bli en andra motor.",
    files: "`docs/heavy-llm-flow/openclaw-2.0-conductor.md` (Fas 0–3) · `openclaw-mvp/` (gitignorerad spik)",
    notes: "Referensmaterial: operatörens fristående OpenClaw-installation + sajtmaskins infra/openclaw (båda read-only).",
  },
  gate: {
    id: "gate",
    canonical: "classify_conversation (samtalsgrinden)",
    status: "finns",
    statusNote: "F1 slice 1–2 landade; slice 3 pågår.",
    what: "Första grinden: är meddelandet småprat, en åsikt om sajten, en fråga — eller en riktig ändring? Bara `edit` släpps vidare. Allt annat besvaras i chatten utan att en ny version byggs.",
    files: "`packages/generation/orchestration/openclaw/roles.py`",
    notes: "Detta är fixen för ”chatten bygger i onödan”-problemet — ingen version skrivs för icke-edit-turer.",
  },
  core: {
    id: "core",
    canonical: "OpenClaw Core V0 (decide/orchestrate)",
    status: "finns",
    statusNote: "Ren, läs-bara kärna; ärlighet hårdkodad.",
    what: "Konduktörens kärna: kombinerar routerns klassning med kontext och fattar ett transient beslut. Kör aldrig bygget självt och får aldrig fejka effekt (`appliedVisibleEffect` är alltid ärlig).",
    files: "`packages/generation/orchestration/openclaw/{core,models}.py`",
    notes: "Beslutstyperna är medvetet INTE kanoniska artefakter — de persisteras inte (kor-o1).",
  },
  decision: {
    id: "decision",
    canonical: "OpenClawDecision (4 utfall)",
    status: "finns",
    statusNote: "Transient — skrivs aldrig till disk.",
    what: "Ett av fyra utfall: answer_only (bara svar), clarification (motfråga), plan_only (förslag utan bygge) eller patch_plan_request (riktig ändring → KÖR-kedjan).",
    files: "`packages/generation/orchestration/openclaw/models.py`",
  },
  router: {
    id: "router",
    canonical: "Router (KÖR-6a, + LLM-fallback 6b)",
    status: "finns",
    statusNote: "Deterministisk bas + valfri routerModel-fallback.",
    what: "Klassificerar ändringen till editKind: visual_style, copy_change, section_add, component_add, route_remove, nav_hide m.fl. Rollerna mappas härifrån: stylist, copy, section_builder, component_builder, route_editor.",
    files: "`packages/generation/orchestration/router/` (`llm_fallback.py` för 6b)",
  },
  context: {
    id: "context",
    canonical: "Context (KÖR-7a)",
    status: "finns",
    statusNote: "Läs-bara.",
    what: "Samlar ihop precis det underlag patchen behöver: aktuell Project Input, sektioner, artefakter — styrt av contextLevel.",
    files: "`packages/generation/orchestration/context/`",
  },
  patch: {
    id: "patch",
    canonical: "Patch (KÖR-7b)",
    status: "finns",
    statusNote: "Validerad plan, transient.",
    what: "Föreslår en strukturerad, validerad patch-plan mot Project Input-lagret. Aldrig fri patch i genererade filer.",
    files: "`packages/generation/orchestration/patch/`",
  },
  apply: {
    id: "apply",
    canonical: "Apply (KÖR-7c)",
    status: "finns",
    statusNote: "Skriver nästa oföränderliga version.",
    what: "Applicerar patch-planen och skriver Project Input vN+1 (ny version, aldrig in-place). Bara per-sajt-lagret — aldrig delade scaffolds/varianter/dossiers.",
    files: "`packages/generation/orchestration/apply/`",
  },
  build: {
    id: "build",
    canonical: "Riktad build (KÖR-7d)",
    status: "finns",
    statusNote: "Del av run_followup_chain.",
    what: "Bygger om det som behövs från den nya Project Input-versionen och producerar en ny körning med nytt runId. Vid ok/degraded uppdateras pekarfilen current.json.",
    files: "`scripts/build_site.py` → `run_followup_chain`",
  },
  newInput: {
    id: "newInput",
    canonical: "Project Input vN+1",
    status: "finns",
    statusNote: "Versionerad, oföränderlig.",
    what: "Den nya versionen av kundens fakta + val. Mutationsytan för restyle (themeTokens/brand/tone), copy (copyDirective) och sektioner (mountedSections). Scaffold-byte kräver redesign/projekt-fork.",
    files: "`data/prompt-inputs/<siteId>.vN.project-input.json` + `.meta.json` (projectDna)",
  },
  newRun: {
    id: "newRun",
    canonical: "Ny körning (runId + current.json)",
    status: "finns",
    statusNote: "Atomär pointer-swap.",
    what: "Resultatet: ny mapp under data/runs/ och en pointer-swap av current.json så preview pekar på den nya versionen. Ärlighetssignalerna applied/appliedVisibleEffect kommer härifrån.",
    files: "`data/runs/<runId>/` · `build-result.json`",
  },
  preview: {
    id: "preview",
    canonical: "Preview-refresh",
    status: "finns",
    statusNote: "local-next eller vercel-sandbox.",
    what: "Viewser stoppar ev. lokal preview-server och laddar om iframen mot den nya körningen.",
    files: "`apps/viewser/` preview-flöde · ADR 0033",
  },
  reply: {
    id: "reply",
    canonical: "Svar i chatten",
    status: "finns",
    statusNote: "Strukturerat + konversationellt.",
    what: "Användaren får både det strukturerade resultatet (byggstatus, beslut) och ett konversationssvar. Icke-byggande turer (småprat, frågor, plan_only) landar här direkt — utan ny version.",
    files: "`apps/viewser/app/api/prompt/route.ts` (chatWithOpenAi)",
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
  dashed?: boolean;
};

const NODES: NodeGeom[] = [
  { id: "floatingChat", x: 28, y: 64, w: 140, h: 44, lines: ["FloatingChat"] },
  { id: "apiPrompt", x: 210, y: 64, w: 160, h: 44, lines: ["POST /api/prompt"], fontSize: 11 },
  { id: "runner", x: 412, y: 64, w: 170, h: 44, lines: ["openclaw-runner.ts"], fontSize: 11 },
  { id: "docker", x: 800, y: 64, w: 210, h: 44, lines: ["Extern Docker-", "konduktör (Fas 2)"], fontSize: 11, dashed: true },
  { id: "gate", x: 28, y: 186, w: 190, h: 44, lines: ["classify_conversation"], fontSize: 11 },
  { id: "core", x: 260, y: 186, w: 170, h: 44, lines: ["OpenClaw Core V0"], fontSize: 11 },
  { id: "decision", x: 472, y: 186, w: 190, h: 44, lines: ["OpenClawDecision", "(4 utfall)"], fontSize: 11 },
  { id: "router", x: 28, y: 308, w: 150, h: 44, lines: ["Router", "KÖR-6a"], fontSize: 11 },
  { id: "context", x: 212, y: 308, w: 150, h: 44, lines: ["Context", "KÖR-7a"], fontSize: 11 },
  { id: "patch", x: 396, y: 308, w: 150, h: 44, lines: ["Patch", "KÖR-7b"], fontSize: 11 },
  { id: "apply", x: 580, y: 308, w: 150, h: 44, lines: ["Apply", "KÖR-7c"], fontSize: 11 },
  { id: "build", x: 764, y: 308, w: 150, h: 44, lines: ["Riktad build", "KÖR-7d"], fontSize: 11 },
  { id: "newInput", x: 100, y: 430, w: 200, h: 44, lines: ["Project Input vN+1"], fontSize: 11 },
  { id: "newRun", x: 350, y: 430, w: 200, h: 44, lines: ["Ny runId + current.json"], fontSize: 11 },
  { id: "preview", x: 600, y: 430, w: 160, h: 44, lines: ["Preview-refresh"], fontSize: 11 },
  { id: "reply", x: 810, y: 430, w: 150, h: 44, lines: ["Svar i chatten"], fontSize: 11 },
];

type EdgeDef = {
  from: string;
  to: string;
  label: string;
  path: string;
  labelX: number;
  labelY: number;
  anchor?: "start" | "middle" | "end";
  dashed?: boolean;
};

const EDGES: EdgeDef[] = [
  { from: "floatingChat", to: "apiPrompt", label: "meddelande", path: "M 168,86 L 208,86", labelX: 188, labelY: 56 },
  { from: "apiPrompt", to: "runner", label: "mode=followup", path: "M 370,86 L 410,86", labelX: 390, labelY: 56 },
  { from: "runner", to: "docker", label: "HTTP-adapter (Fas 2)", path: "M 582,86 L 798,86", labelX: 690, labelY: 76, dashed: true },
  { from: "runner", to: "gate", label: "run_openclaw_followup.py --apply", path: "M 497,108 C 497,152 123,142 123,184", labelX: 310, labelY: 140 },
  { from: "gate", to: "core", label: "edit → vidare", path: "M 218,208 L 258,208", labelX: 238, labelY: 178 },
  { from: "gate", to: "reply", label: "småprat / fråga → svar utan bygge", path: "M 123,230 C 123,330 885,310 885,428", labelX: 470, labelY: 282 },
  { from: "core", to: "decision", label: "decide()", path: "M 430,208 L 470,208", labelX: 450, labelY: 178 },
  { from: "decision", to: "router", label: "patch_plan_request", path: "M 567,230 C 567,272 103,264 103,306", labelX: 330, labelY: 262, anchor: "middle" },
  { from: "decision", to: "reply", label: "answer / clarify / plan → inget bygge", path: "M 662,208 C 800,214 885,320 885,428", labelX: 845, labelY: 256, anchor: "end" },
  { from: "router", to: "context", label: "editKind + roll", path: "M 178,330 L 210,330", labelX: 194, labelY: 300 },
  { from: "context", to: "patch", label: "underlag", path: "M 362,330 L 394,330", labelX: 378, labelY: 300 },
  { from: "patch", to: "apply", label: "patch-plan", path: "M 546,330 L 578,330", labelX: 562, labelY: 300 },
  { from: "apply", to: "build", label: "ny version", path: "M 730,330 L 762,330", labelX: 746, labelY: 300 },
  { from: "apply", to: "newInput", label: "skriver vN+1", path: "M 655,352 C 655,394 200,386 200,428", labelX: 420, labelY: 388 },
  { from: "build", to: "newRun", label: "data/runs/<runId>", path: "M 839,352 C 839,394 450,386 450,428", labelX: 660, labelY: 380 },
  { from: "newRun", to: "preview", label: "pointer-swap", path: "M 550,452 L 598,452", labelX: 574, labelY: 480 },
  { from: "preview", to: "reply", label: "iframe laddas om", path: "M 760,452 L 808,452", labelX: 784, labelY: 480 },
];

const STATUS_LABEL: Record<StepStatus, string> = {
  finns: "Finns",
  delvis: "Delvis",
  planerat: "Planerat",
};

// ---------------------------------------------------------------------------
// Flodeskartan (SVG)
// ---------------------------------------------------------------------------

function FlowMap({
  selected,
  onSelect,
}: {
  selected: string;
  onSelect: (id: string) => void;
}) {
  const t = useHostTheme();

  const statusColor = (s: StepStatus) =>
    s === "finns" ? t.category.green : s === "delvis" ? t.category.yellow : t.category.gray;

  const hotEdges = EDGES.filter((e) => e.from === selected || e.to === selected);
  const dimEdges = EDGES.filter((e) => e.from !== selected && e.to !== selected);
  const neighborIds = new Set<string>(hotEdges.map((e) => (e.from === selected ? e.to : e.from)));

  const bandLabel = { fontSize: 10, letterSpacing: 1.2 } as const;

  const renderEdge = (e: EdgeDef, hot: boolean) => (
    <path
      key={`${e.from}-${e.to}`}
      d={e.path}
      fill="none"
      stroke={hot ? t.accent.primary : t.stroke.primary}
      strokeWidth={hot ? 1.8 : 1.1}
      strokeDasharray={e.dashed ? "5 4" : undefined}
      markerEnd={hot ? "url(#oc-arrow-hot)" : "url(#oc-arrow-dim)"}
    />
  );

  return (
    <div style={{ overflowX: "auto" }}>
      <svg
        viewBox="0 0 1040 508"
        style={{ width: "100%", minWidth: 880, display: "block", fontFamily: "inherit" }}
        role="img"
        aria-label="OpenClaw-flödet från chattmeddelande till ny version och preview"
      >
        <defs>
          <marker id="oc-arrow-dim" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
            <path d="M0,0 L8,4 L0,8 z" fill={t.stroke.primary} />
          </marker>
          <marker id="oc-arrow-hot" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
            <path d="M0,0 L8,4 L0,8 z" fill={t.accent.primary} />
          </marker>
        </defs>

        {/* Lagerband */}
        <rect x={16} y={30} width={1008} height={92} rx={10} fill={t.fill.quaternary} />
        <text x={28} y={48} fill={t.text.tertiary} style={bandLabel}>
          VIEWSER · TYPESCRIPT
        </text>

        <rect x={16} y={152} width={1008} height={92} rx={10} fill={t.fill.quaternary} />
        <text x={28} y={170} fill={t.text.tertiary} style={bandLabel}>
          KONDUKTÖREN · PYTHON, IN-PROCESS (INGEN EGEN MOTOR)
        </text>

        <rect x={16} y={274} width={1008} height={92} rx={10} fill={t.fill.quaternary} />
        <text x={28} y={292} fill={t.text.tertiary} style={bandLabel}>
          KÖR-KEDJAN · FOLLOW-UP-MUTATION (6A → 7A → 7B → 7C → 7D)
        </text>

        <rect x={16} y={396} width={1008} height={92} rx={10} fill={t.fill.quaternary} />
        <text x={28} y={414} fill={t.text.tertiary} style={bandLabel}>
          RESULTAT · NY VERSION, ALDRIG IN-PLACE
        </text>

        {/* Kanter: dimmade forst, markerade overst */}
        {dimEdges.map((e) => renderEdge(e, false))}
        {hotEdges.map((e) => renderEdge(e, true))}

        {/* Noder */}
        {NODES.map((n) => {
          const s = STEPS[n.id];
          const isSel = selected === n.id;
          const isNeighbor = neighborIds.has(n.id);
          const cx = n.x + n.w / 2;
          return (
            <g key={n.id} onClick={() => onSelect(n.id)} style={{ cursor: "pointer" }}>
              <title>{`${s.canonical} · ${STATUS_LABEL[s.status]}`}</title>
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
                strokeDasharray={n.dashed ? "6 4" : undefined}
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
              <circle cx={n.x + n.w - 10} cy={n.y + 10} r={4} fill={statusColor(s.status)} />
            </g>
          );
        })}

        {/* Etiketter for markerade kanter */}
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

function StepDetail({ selected }: { selected: string }) {
  const s = STEPS[selected] ?? STEPS.gate;
  const connections = EDGES.filter((e) => e.from === s.id || e.to === s.id).map((e) => {
    const outgoing = e.from === s.id;
    const other = STEPS[outgoing ? e.to : e.from];
    return `${outgoing ? "→" : "←"} ${other.canonical} · ${e.label}`;
  });

  return (
    <Card>
      <CardHeader trailing={<Pill size="sm" active>{STATUS_LABEL[s.status]}</Pill>}>
        {s.canonical}
      </CardHeader>
      <CardBody>
        <Stack gap={14}>
          <Text>{s.what}</Text>
          <Grid columns={2} gap={14}>
            <Field label="FIL & PLATS" value={s.files} />
            <Field label="STATUS" value={s.statusNote} />
          </Grid>
          {connections.length > 0 ? (
            <Stack gap={4}>
              <Text size="small" tone="tertiary" weight="semibold">KOPPLINGAR I FLÖDET</Text>
              {connections.map((line) => (
                <div key={line}>
                  <Text size="small" tone="secondary">{line}</Text>
                </div>
              ))}
            </Stack>
          ) : null}
          {s.notes ? <Callout tone="info">{s.notes}</Callout> : null}
        </Stack>
      </CardBody>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Roller, action-register och hardregler
// ---------------------------------------------------------------------------

function RolesAndActions() {
  return (
    <Stack gap={16}>
      <H2>Konduktörens roller (F1)</H2>
      <Text tone="secondary">
        Rollerna är kontrakt, inte separata processer — de avgör vilket slags mutation kedjan får
        göra. Definieras i `packages/generation/orchestration/openclaw/roles.py`.
      </Text>
      <Table
        headers={["Roll", "Ansvar", "Triggas av editKind"]}
        rows={[
          ["router", "Klassificerar meddelandet och väljer väg", "— (alltid först)"],
          ["stylist", "Visuell stil: tokens, brand, ton — aldrig struktur", "visual_style"],
          ["copy", "Textändringar via copyDirective", "copy_change"],
          ["section_builder", "Lägger till/monterar sektioner via capability + dossier", "section_add"],
          ["component_builder", "Komponenter: mount-only som standard + generativt recept (image-placeholder-grid)", "component_add"],
          ["route_editor", "Tar bort sida (disabledRoutes) resp. döljer nav-länk (hiddenNavRoutes)", "route_remove + nav_hide"],
        ]}
      />

      <H2>Sanktionerade åtgärder (action-registry)</H2>
      <Text tone="secondary">
        Registret i `docs/openclaw-workspace/action-registry.json` är spec-lagret; motorn speglar det
        i `roles.py` (korsvaliderat av `tests/test_openclaw_registry_consistency.py`), den läser inte
        JSON-filen direkt i runtime.
      </Text>
      <Table
        headers={["Åtgärd", "Status", "Kommentar"]}
        striped
        rowTone={["success", "success", "success", "success", "success", "success", "warning", "neutral"]}
        rows={[
          ["restyle", "Stöds", "themeTokens / brand / tone i Project Input"],
          ["copy_change", "Stöds", "Strukturerad copyDirective (ADR 0034)"],
          ["section_add", "Stöds", "faq/team renderas på local-service-business; övriga mount-only (ADR 0038)"],
          ["component_add", "Stöds", "Mount-only som standard + generativt recept image-placeholder-grid (ADR 0061)"],
          ["route_remove", "Stöds", "Tar bort icke-obligatorisk sida + nav-länk via disabledRoutes (ADR 0060)"],
          ["nav_hide", "Stöds", "Döljer nav-länk men behåller sidan via hiddenNavRoutes (ADR 0060)"],
          ["site_review", "Delvis", "Läs-bara granskning"],
          ["layout_change", "Planerad", "Ej implementerad ännu"],
        ]}
      />

      <H2>Hårda regler — det här får OpenClaw aldrig göra</H2>
      <Grid columns={2} gap={12}>
        <Callout tone="danger" title="Aldrig röra koden fritt">
          Ingen fri patch i genererade filer, ingen parallell motor, ingen handredigering av
          `.generated/**` eller `data/runs/**/generated-files/**`. All förändring går genom
          patch → apply → riktad build.
        </Callout>
        <Callout tone="danger" title="Aldrig hitta på fakta">
          Inga påhittade recensioner, certifikat, telefonnummer eller påståenden. Och aldrig fejka
          framgång: `appliedVisibleEffect` får bara vara sann med bevis från byggkedjan.
        </Callout>
        <Callout tone="danger" title="Aldrig ändra delat för en kund">
          Delade scaffolds, varianter och dossiers ändras aldrig för en enskild kunds skull.
          Mutationer sker bara i kundens eget lager (Project Input / projektminne).
        </Callout>
        <Callout tone="danger" title="Aldrig extern daemon i nuvarande fas">
          Ingen extern gateway/Docker-konduktör förrän Fas 2 är beslutad (regel 09). Tills dess är
          OpenClaw in-process — en dirigent över befintlig motor, inte en egen tjänst.
        </Callout>
      </Grid>
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Huvudkomponent
// ---------------------------------------------------------------------------

export default function OpenClawFloden() {
  const [selected, setSelected] = useCanvasState<string>("openclawSelected", "gate");

  return (
    <Stack gap={28} style={{ maxWidth: 1120, margin: "0 auto", padding: "24px 16px 48px" }}>
      <Stack gap={6}>
        <H1>OpenClaw-flödet: konduktören över sajtmutationer</H1>
        <Text tone="secondary">
          OpenClaw är en <Text weight="semibold">dirigent</Text>, inte en motor: den lyssnar på
          följdprompter, avgör om något alls ska byggas, och skickar riktiga ändringar genom den
          befintliga KÖR-kedjan. Klicka på en ruta för detaljer — kopplingarna lyser upp.
        </Text>
      </Stack>

      <Callout tone="info" title="Init går förbi konduktören">
        Första bygget (init) tar Golden Path direkt: prompt → Project Input → fullt bygge. OpenClaw
        kommer in först vid följdprompter (followup) — det är där grinden och KÖR-kedjan gör nytta.
      </Callout>

      <Stack gap={10}>
        <FlowMap selected={selected} onSelect={setSelected} />
        <Row gap={16} align="center" wrap>
          <Row gap={6} align="center">
            <Swatch color="green" />
            <Text size="small" tone="secondary">Finns & används</Text>
          </Row>
          <Row gap={6} align="center">
            <Swatch color="yellow" />
            <Text size="small" tone="secondary">Delvis</Text>
          </Row>
          <Row gap={6} align="center">
            <Swatch color="gray" />
            <Text size="small" tone="secondary">Planerat</Text>
          </Row>
          <Text size="small" tone="tertiary">
            Streckad ruta/pil = planerad Fas 2. Två vägar slutar i chatten: med eller utan ny version.
          </Text>
        </Row>
      </Stack>

      <StepDetail selected={selected} />

      <RolesAndActions />

      <Stack gap={4}>
        <Text size="small" tone="tertiary">
          Delad canvas — kanonisk kopia i `docs/canvases/` (git). Spegla lokalt med
          `python scripts/sync_canvases.py`. Systerkarta: `begreppskarta-sajtbyggaren.canvas.tsx`.
        </Text>
        <Text size="small" tone="tertiary">
          Källor: `governance/rules/09-openclaw-and-site-mutations.md`,
          `docs/heavy-llm-flow/openclaw-2.0-conductor.md`, `kor-o1-openclaw-core-contract.md`,
          `docs/openclaw-workspace/action-registry.json`, `docs/current-focus.md` · kartlagt 2026-06-10.
        </Text>
      </Stack>
    </Stack>
  );
}
