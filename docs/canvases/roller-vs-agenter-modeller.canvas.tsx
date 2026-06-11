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
  Stat,
  Swatch,
  Table,
  Text,
  useHostTheme,
} from "cursor/canvas";

// ---------------------------------------------------------------------------
// Delad canvas - kanonisk kopia i repot: docs/canvases/
// Spegla till Cursors canvas-mapp med: python scripts/sync_canvases.py
//
// Roller vs agenter vs personas vs modeller i Sajtbyggaren
// Faktakällor (repo): governance/policies/llm-models.v1.json (v10),
//   packages/generation/orchestration/openclaw/roles.py (ROLE_CONTRACTS),
//   apps/viewser/lib/openai.ts, apps/viewser/lib/asset-store/vision.ts,
//   scripts/scrape_site.py, docs/openclaw-workspace/SOUL.md.
// Live-modellfakta: OpenAI docs-MCP (developers.openai.com/mcp), hämtat 2026-06-11.
// ---------------------------------------------------------------------------

type LayerId = "modelRoles" | "conductor" | "persona" | "sideCalls" | "agents";

type Layer = {
  id: LayerId;
  title: string;
  question: string;
  oneLiner: string;
  source: string;
  count: string;
  model: string;
  tone: "info" | "success" | "warning" | "neutral";
};

const LAYERS: Layer[] = [
  {
    id: "modelRoles",
    title: "Model Roles",
    question: "VAR anropas en LLM?",
    oneLiner:
      "Namngivna anropspunkter i motorn (briefModel, planningModel, codegenModel …). Varje roll mappas mot en modellsträng. Ingen kod får anropa en LLM utan att gå via en registrerad roll.",
    source: "governance/policies/llm-models.v1.json (v10)",
    count: "12 roller",
    model: "gpt-5.4 (alla generation-roller)",
    tone: "info",
  },
  {
    id: "conductor",
    title: "Konduktör-roller (agent-roller)",
    question: "VEM förstår & föreslår en ändring?",
    oneLiner:
      "Frysta kontrakt (data, inte processer): router, section_builder, stylist, copy. En roll FÖRSTÅR och väljer skill; den deterministiska apply-kedjan VALIDERAR och applicerar.",
    source: "packages/generation/orchestration/openclaw/roles.py",
    count: "4 roller",
    model: "ärver Model Role (t.ex. stylist → styleDirectiveModel)",
    tone: "success",
  },
  {
    id: "persona",
    title: "Persona (SOUL)",
    question: "HUR låter chatten?",
    oneLiner:
      "Dirigentens konstitution — ton och personlighet för chatt-svar i ALLA sajter. Påverkar aldrig byggbeteendet (det bor i kod + governance, inte i prosa).",
    source: "docs/openclaw-workspace/SOUL.md",
    count: "1 fil",
    model: "läses in i chat-systemprompten",
    tone: "neutral",
  },
  {
    id: "sideCalls",
    title: "Chatt- & sidoanrop",
    question: "Vad ligger UTANFÖR motorns roller?",
    oneLiner:
      "Viewser-chattens server-side helper, bild/vision-tolkning och webb-scrape vid discovery. Dessa går inte via Model Roles utan via egna env-variabler.",
    source: "apps/viewser/lib/openai.ts · lib/asset-store/vision.ts · scripts/scrape_site.py",
    count: "3 anropspunkter",
    model: "gpt-4o (fallback)",
    tone: "warning",
  },
  {
    id: "agents",
    title: '"Agenter" (extern OpenClaw-mening)',
    question: "Finns fristående agent-processer?",
    oneLiner:
      "Nej. Sajtbyggaren har INGEN daemon, gateway eller fristående agent-process. Allt är in-process och deterministiskt orkestrerat. Extern OpenClaw är referens — inte arkitektur.",
    source: "AGENTS.md · docs/openclaw-workspace/README.md",
    count: "0 st",
    model: "—",
    tone: "neutral",
  },
];

// Model Roles ur llm-models.v1.json (v10). Alla generation-roller = gpt-5.4.
const MODEL_ROLES: Array<[string, string, string]> = [
  ["briefModel", "Fas 1 Understand — extrahera Site Brief ur prompten", "gpt-5.4"],
  ["planningModel", "Fas 2 Plan — route-hints, dossier-rationale", "gpt-5.4"],
  ["routerModel", "Följdprompt-router (LLM-fallback ovanpå heuristiken)", "gpt-5.4"],
  ["copyDirectiveModel", "Tolkar följdprompt → validerade copy-direktiv", "gpt-5.4"],
  ["styleDirectiveModel", "Stylist — fri stil/färg-prompt → tema-mutation", "gpt-5.4"],
  ["rerankModel", "Rerank av scaffold-/dossier-kandidater", "gpt-5.4"],
  ["codegenModel", "Fas 3 Build — generera filerna", "gpt-5.4"],
  ["variantModel", "Design-tooling — Scaffold Variant-kandidater", "gpt-5.4"],
  ["dossierModel", "Design-tooling — Soft Dossier-kandidater", "gpt-5.4"],
  ["repairModel", "Repair Pipeline — LLM-fix när mekanik inte räcker", "gpt-5.4"],
  ["verifierModel", "Read-only smak-critic ovanpå Quality Critic", "gpt-5.4"],
  ["embeddingModel", "Semantisk sökning (index)", "text-embedding-3-small"],
];

// Var gpt-4o faktiskt körs idag (svaret på "vilka kör jag 4o på?").
const GPT4O_USAGE: Array<[string, string, string, string]> = [
  [
    "Viewser chatt-helper",
    "apps/viewser/lib/openai.ts",
    "OPENAI_MODEL",
    "Svar i FloatingChat (chat.completions, temperature 0.3)",
  ],
  [
    "Bild/vision-tolkning",
    "apps/viewser/lib/asset-store/vision.ts",
    "OPENAI_VISION_MODEL",
    "Tolkar uppladdade bilder/assets",
  ],
  [
    "Discovery-scrape",
    "scripts/scrape_site.py",
    "SAJTBYGGAREN_DISCOVERY_MODEL",
    "Läser referenssajt vid discovery",
  ],
];

// Aktuell OpenAI-lineup enligt docs-MCP (live, 2026-06-11).
const OPENAI_LINEUP: Array<[string, string, string]> = [
  ["gpt-5.5", "Flagship", "Nuvarande topp; reasoning.effort default medium"],
  ["gpt-5.5-pro", "Tyngsta reasoning", "För de svåraste agentiska uppgifterna"],
  ["gpt-5.4", "Föregående generation", "Det motorns Model Roles kör idag"],
  ["gpt-5.2", "Äldre GPT-5", "Nämns som tidigare generation"],
  ["gpt-4o", "Äldre (icke-reasoning)", "Det chatt-/sidoanropen faller tillbaka på"],
];

function toneSwatch(tone: Layer["tone"]): "blue" | "green" | "yellow" | "gray" {
  if (tone === "info") return "blue";
  if (tone === "success") return "green";
  if (tone === "warning") return "yellow";
  return "gray";
}

function LayerCard({ layer }: { layer: Layer }) {
  return (
    <Card>
      <CardHeader trailing={<Pill size="sm">{layer.count}</Pill>}>
        <Row gap={8} align="center">
          <Swatch color={toneSwatch(layer.tone)} />
          <Text weight="semibold">{layer.title}</Text>
        </Row>
      </CardHeader>
      <CardBody>
        <Stack gap={10}>
          <Text size="small" tone="tertiary" weight="semibold">
            {layer.question}
          </Text>
          <Text size="small">{layer.oneLiner}</Text>
          <Stack gap={2}>
            <Text size="small" tone="tertiary" weight="semibold">
              MODELL / KOPPLING
            </Text>
            <Text size="small" tone="secondary">
              {layer.model}
            </Text>
          </Stack>
          <Stack gap={2}>
            <Text size="small" tone="tertiary" weight="semibold">
              KÄLLA
            </Text>
            <Text size="small" tone="secondary">
              {layer.source}
            </Text>
          </Stack>
        </Stack>
      </CardBody>
    </Card>
  );
}

export default function RollerVsAgenterModeller() {
  const t = useHostTheme();

  return (
    <Stack gap={28} style={{ maxWidth: 1120, margin: "0 auto", padding: "24px 16px 48px" }}>
      <Stack gap={6}>
        <H1>Roller, agenter, personas & modeller</H1>
        <Text tone="secondary">
          Fyra olika saker bär ord som låter lika. Den här kartan håller isär dem: en{" "}
          <Text weight="semibold">Model Role</Text> är VAR en LLM anropas, en{" "}
          <Text weight="semibold">konduktör-roll</Text> är VEM som förstår en ändring,{" "}
          <Text weight="semibold">SOUL</Text> är HUR chatten låter, och{" "}
          <Text weight="semibold">"agenter"</Text> (fristående processer) finns inte alls här.
        </Text>
      </Stack>

      <Grid columns={4} gap={16}>
        <Stat value="12" label="Model Roles (motorn)" tone="info" />
        <Stat value="4" label="Konduktör-roller" tone="success" />
        <Stat value="3" label="Sidoanrop på gpt-4o" tone="warning" />
        <Stat value="0" label="Fristående agenter/daemon" />
      </Grid>

      <Stack gap={12}>
        <H2>De fyra lagren (plus icke-lagret)</H2>
        <Grid columns={2} gap={16}>
          {LAYERS.map((layer) => (
            <div key={layer.id}>
              <LayerCard layer={layer} />
            </div>
          ))}
        </Grid>
      </Stack>

      <Stack gap={12}>
        <H2>Vilka modeller kör du gpt-4o på?</H2>
        <Text tone="secondary">
          Motorns Model Roles ligger på <Text weight="semibold">gpt-5.4</Text>. Det är bara tre
          sidoanrop som faller tillbaka på <Text weight="semibold">gpt-4o</Text> — och bara när
          respektive env-variabel inte är satt.
        </Text>
        <Table
          headers={["Anropspunkt", "Fil", "Env-override", "Vad den gör"]}
          striped
          rowTone={["warning", "warning", "warning"]}
          rows={GPT4O_USAGE}
        />
        <Callout tone="info" title="Viktig nyans om env">
          På Vercel-deploy sätts <Text weight="semibold">OPENAI_MODEL=gpt-5.5</Text> i miljön — då
          kör chatt-helpern 5.5, inte 4o. <Text weight="semibold">gpt-4o</Text> är bara
          kod-fallbacken i `lib/openai.ts` / `vision.ts` när variabeln saknas. Viewser läser inte
          repo-rotens `.env`, så `OPENAI_MODEL` måste finnas i Viewsers egen miljö för att vinna.
        </Callout>
      </Stack>

      <Stack gap={12}>
        <H2>Motorns 12 Model Roles</H2>
        <Table
          headers={["Roll-id", "Syfte", "Modell"]}
          striped
          rows={MODEL_ROLES}
        />
        <Text size="small" tone="tertiary">
          Källa: `governance/policies/llm-models.v1.json` (v10). Att byta modell för en roll är en
          policy-bump (version-höjning) — inte en kodändring. Redigerbart i backoffice → "Model
          Roles".
        </Text>
      </Stack>

      <Stack gap={12}>
        <H2>Gränser idag</H2>
        <Grid columns={3} gap={16}>
          <Card>
            <CardHeader>Chatt (Viewser)</CardHeader>
            <CardBody>
              <Stack gap={6}>
                <Text size="small">Svarstokens: <Text weight="semibold">1500</Text> (env `VIEWSER_MAX_CHAT_TOKENS`)</Text>
                <Text size="small">Input: <Text weight="semibold">8000 tecken</Text>/meddelande</Text>
                <Text size="small">Max <Text weight="semibold">40</Text> meddelanden/request</Text>
                <Text size="small">temperature <Text weight="semibold">0.3</Text></Text>
              </Stack>
            </CardBody>
          </Card>
          <Card>
            <CardHeader>Motor-roller</CardHeader>
            <CardBody>
              <Stack gap={6}>
                <Text size="small">Inga per-roll token-gränser i policyn</Text>
                <Text size="small">Anropas via `responses.parse` (structured output)</Text>
                <Text size="small">Ingen `reasoning`/`temperature` satt → modellens defaults</Text>
              </Stack>
            </CardBody>
          </Card>
          <Card>
            <CardHeader>SOUL-persona</CardHeader>
            <CardBody>
              <Stack gap={6}>
                <Text size="small">Backoffice-editor: max <Text weight="semibold">8000</Text> tecken</Text>
                <Text size="small">Runtime trunkerar till <Text weight="semibold">3500</Text> tecken</Text>
                <Text size="small">Styr ton — aldrig byggregler</Text>
              </Stack>
            </CardBody>
          </Card>
        </Grid>
      </Stack>

      <Stack gap={12}>
        <H2>Aktuell OpenAI-lineup (live via docs-MCP)</H2>
        <Table
          headers={["Modell", "Klass", "Kommentar"]}
          striped
          rowTone={["success", "success", "info", "neutral", "warning"]}
          rows={OPENAI_LINEUP}
        />
        <Row gap={16} align="center" wrap>
          <Row gap={6} align="center">
            <Swatch color="green" />
            <Text size="small" tone="secondary">Nuvarande flagship-familj</Text>
          </Row>
          <Row gap={6} align="center">
            <Swatch color="yellow" />
            <Text size="small" tone="secondary">Äldre — sidoanropens fallback</Text>
          </Row>
          <Text size="small" tone="tertiary">
            Den nya "thinking"-ratten heter `reasoning.effort` (none/low/medium/high/xhigh) plus
            `text.verbosity` — finns på GPT-5-serien, inte på gpt-4o.
          </Text>
        </Row>
      </Stack>

      <Stack gap={12}>
        <H2>Mitt förslag</H2>
        <Callout tone="warning" title="gpt-4o ligger två generationer efter">
          Sidoanropen (chatt-helper, vision, discovery) faller tillbaka på gpt-4o, medan motorn kör
          gpt-5.4 och OpenAI:s flagship nu är gpt-5.5. Sätt `OPENAI_MODEL` och `OPENAI_VISION_MODEL`
          explicit i Viewsers miljö så chatt och vision inte tyst hamnar på en äldre modell.
        </Callout>
        <Callout tone="info" title="Bestäm modell på ETT ställe per lager">
          Motorns roller byts i `llm-models.v1.json` (policy-bump, ej kod). Chatt/vision/discovery
          styrs av env. Persona (ton) i `SOUL.md`. Blanda aldrig ihop dem — en SOUL-ändring gör
          inte chatten smartare, bara artigare.
        </Callout>
        <Callout tone="info" title="Outnyttjad hävstång: reasoning.effort + verbosity">
          Motoranropen kör `responses.parse` helt utan reasoning-/verbosity-parametrar idag. På
          GPT-5-serien är `reasoning.effort` (low för klassning/router, high för codegen/repair) och
          `text.verbosity` den största kvalitets-/kostnadsspaken — värt en medveten policy innan en
          ren modell-bump.
        </Callout>
        <Callout tone="neutral" title="Behåll 'inga fristående agenter'">
          Frestelsen att bygga en daemon/gateway som extern OpenClaw är reell, men hela poängen här
          är kontrollerad in-process-orkestrering. Roller som data + deterministisk apply-kedja är
          en styrka, inte en brist.
        </Callout>
      </Stack>

      <Stack gap={4}>
        <Text size="small" tone="tertiary">
          Källor (repo): `llm-models.v1.json` (v10), `roles.py` (ROLE_CONTRACTS), `lib/openai.ts`,
          `lib/asset-store/vision.ts`, `scripts/scrape_site.py`, `SOUL.md`.
        </Text>
        <Text size="small" tone="tertiary">
          Live-modellfakta hämtade via OpenAI docs-MCP (`developers.openai.com/mcp`) 2026-06-11.
          Exakta priser bör hämtas live via samma MCP (`get_openapi_spec` / pris-doc) eftersom de
          ändras.
        </Text>
      </Stack>
    </Stack>
  );
}
