/**
 * prod-answer-only-probe — live prod-verifiering av answer-only-gaten.
 *
 * Diagnostik (importeras INGENSTANS i runtime). Bevisar mot riktiga prod att
 * en REN FRÅGA i follow-up-läget besvaras UTAN att ett bygge startas:
 *
 *   1. Init-bygge (mode: "init") -> ger ett grundat prod-siteId med hostad
 *      KV+blob-kontext (krävs av G1-grinden maybeAnswerHostedFollowupWithoutSandbox).
 *      Vi öppnar NDJSON-strömmen bara för att fånga runId+siteId tidigt och
 *      pollar sedan status-routen (sanningskällan) tills phase=done/failed.
 *   2. Fråge-prompt (mode: "followup", siteId) -> ska kortslutas av G1 till
 *      answer-only och returnera kontraktet i hosted-answer-only.ts /
 *      hostedPreclassifiedAnswerResponse:
 *        runId === null, answerText (icke-tom),
 *        conversation.conversationKind === "question", bridge === null,
 *        version === null, buildResult === {}, hosted === true.
 *
 * Rate-limit-medvetet: /api/prompt är publik på prod men IP-strypt till
 * 3 requests / 300 s. Proben gör exakt 2 anrop (init + fråga).
 *
 * Körning:
 *   node apps/viewser/scripts/prod-answer-only-probe.mjs
 *   PROD_BASE=https://... node apps/viewser/scripts/prod-answer-only-probe.mjs
 *
 * Konventioner: kodidentifierare/kommentarer på engelska enligt
 * governance/rules/code-in-english.md — men den här filen är ett
 * operatörs-diagnostikskript och håller svenska loggrader för läsbarhet.
 */

const BASE = (process.env.PROD_BASE ?? "https://sajtbyggaren-viewser.vercel.app").replace(/\/$/, "");
const PROMPT_URL = `${BASE}/api/prompt`;

const INIT_PROMPT =
  "Bygg en enkel företagshemsida för en lokal cykelreparatör i Göteborg " +
  "som heter Hjuldoktorn. Vänlig, jordnära ton.";
const QUESTION_PROMPT = "Vilka sidor finns på sajten och vad används de till?";

const STREAM_CAPTURE_MS = 90_000; // hur länge vi läser init-strömmen för runId
const BUILD_POLL_TIMEOUT_MS = 8 * 60_000; // tak för hela init-bygget
const POLL_INTERVAL_MS = 6_000;

const log = (...a) => console.log(...a);
const fail = (msg) => {
  console.error(`\n❌ MISSLYCKADES: ${msg}`);
  process.exit(1);
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Plocka ut siteId/runId/done/error ur en NDJSON-rad. */
function readEvent(line) {
  try {
    return JSON.parse(line);
  } catch {
    return null;
  }
}

/**
 * Starta init-bygget och läs strömmen bara tills vi har runId+siteId (eller
 * en done/error-rad). Bygget är detached i sandboxen, så att sluta läsa
 * strömmen dödar inte bygget — vi fortsätter via status-routen.
 */
async function startInitBuild() {
  log(`\n=== STEG 1: Init-bygge mot ${PROMPT_URL} ===`);
  const t0 = Date.now();
  const res = await fetch(PROMPT_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/x-ndjson",
    },
    body: JSON.stringify({ prompt: INIT_PROMPT, mode: "init" }),
  });
  log(`   HTTP ${res.status} ${res.statusText} (headers efter ${Date.now() - t0} ms)`);
  if (res.status === 429) fail("rate-limitad (429) — vänta 5 min och kör igen.");
  if (!res.ok) {
    const body = await res.text().catch(() => "(kunde inte läsa body)");
    fail(`init-bygget gav HTTP ${res.status}: ${body.slice(0, 400)}`);
  }
  if (!res.body) fail("init-svaret saknar body-ström.");

  let siteId = null;
  let runId = null;
  let doneEvent = null;
  const deadline = Date.now() + STREAM_CAPTURE_MS;
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for await (const chunk of res.body) {
      buffer += decoder.decode(chunk, { stream: true });
      let nl;
      while ((nl = buffer.indexOf("\n")) !== -1) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (!line) continue;
        const ev = readEvent(line);
        if (!ev) continue;
        if (typeof ev.siteId === "string") siteId = ev.siteId;
        if (typeof ev.runId === "string") runId = ev.runId;
        log(
          `   ström: ${JSON.stringify({ stage: ev.stage, runId: ev.runId, siteId: ev.siteId, buildStatus: ev.buildStatus, error: ev.error })}`,
        );
        if (ev.stage === "done") doneEvent = ev;
        if (ev.stage === "error") log(`   (stream-error — fortsätter via status-routen)`);
      }
      if (doneEvent || (siteId && runId) || Date.now() > deadline) break;
    }
  } catch (err) {
    log(`   ström avbröts (${err?.message ?? err}) — fortsätter via status-routen om vi har runId`);
  }

  if (doneEvent && siteId) {
    log(`   ✓ done direkt från strömmen (buildStatus=${doneEvent.buildStatus})`);
    return { siteId, runId: runId ?? doneEvent.runId ?? null, doneEvent };
  }
  if (!siteId || !runId) fail("fångade aldrig siteId+runId ur init-strömmen.");
  log(`   ✓ fångade siteId=${siteId} runId=${runId} — pollar status-routen`);
  return { siteId, runId, doneEvent: null };
}

/** Polla GET /api/hosted-build/<runId>?siteId=<siteId> tills phase=done/failed. */
async function pollUntilBuilt(siteId, runId) {
  const url = `${BASE}/api/hosted-build/${encodeURIComponent(runId)}?siteId=${encodeURIComponent(siteId)}`;
  const deadline = Date.now() + BUILD_POLL_TIMEOUT_MS;
  let lastPhase = "";
  while (Date.now() < deadline) {
    await sleep(POLL_INTERVAL_MS);
    let res;
    try {
      res = await fetch(url, { headers: { Accept: "application/json" } });
    } catch (err) {
      log(`   poll-fel (${err?.message ?? err}) — försöker igen`);
      continue;
    }
    if (res.status === 404) {
      log(`   poll: 404 (status-nyckeln inte synlig än) — försöker igen`);
      continue;
    }
    if (!res.ok) {
      log(`   poll: HTTP ${res.status} — försöker igen`);
      continue;
    }
    const status = await res.json().catch(() => null);
    if (!status) continue;
    if (status.phase !== lastPhase) {
      lastPhase = status.phase;
      const elapsed = Math.round((BUILD_POLL_TIMEOUT_MS - (deadline - Date.now())) / 1000);
      log(`   phase=${status.phase} (${elapsed}s)`);
    }
    if (status.phase === "done") {
      log(`   ✓ bygget klart (buildId=${status.buildId ?? "?"})`);
      return status;
    }
    if (status.phase === "failed") {
      fail(`init-bygget failade i sandboxen: ${status.error ?? "okänt fel"}`);
    }
  }
  fail(`init-bygget blev inte klart inom ${Math.round(BUILD_POLL_TIMEOUT_MS / 60000)} min.`);
}

/** Skicka fråge-prompten och verifiera answer-only-kontraktet. */
async function probeQuestion(siteId) {
  log(`\n=== STEG 2: Fråge-prompt (answer-only-grind) för siteId=${siteId} ===`);
  log(`   prompt: "${QUESTION_PROMPT}"`);
  const t0 = Date.now();
  const res = await fetch(PROMPT_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt: QUESTION_PROMPT, mode: "followup", siteId }),
  });
  const ms = Date.now() - t0;
  log(`   HTTP ${res.status} ${res.statusText} efter ${ms} ms`);
  if (res.status === 429) fail("rate-limitad (429) på fråge-anropet — vänta 5 min.");
  const payload = await res.json().catch(() => null);
  if (!res.ok) fail(`fråge-anropet gav HTTP ${res.status}: ${JSON.stringify(payload)?.slice(0, 400)}`);
  if (!payload) fail("fråge-svaret gick inte att parsa som JSON.");

  log(`   svar: ${JSON.stringify({
    runId: payload.runId,
    version: payload.version,
    buildStatus: payload.buildStatus,
    bridge: payload.bridge,
    hosted: payload.hosted,
    conversation: payload.conversation,
    answerText: typeof payload.answerText === "string" ? `${payload.answerText.slice(0, 160)}…` : payload.answerText,
  }, null, 2)}`);

  // Assertions: answer-only utan bygge, OCH ett RIKTIGT svar (inte felfallback).
  // Answer-only kan landa via två likvärdiga vägar — G1:s snabba kortslutning
  // (bridge: null) ELLER konduktorns sandbox-gate (bridge: {applied:false}) —
  // så vägen i sig assertas inte; det som räknas är "inget bygge + ärligt svar".
  const answerText = typeof payload.answerText === "string" ? payload.answerText : "";
  const isErrorFallback = /chat-anropet misslyckades/i.test(answerText);
  const isNoKeyFallback = /OPENAI_API_KEY saknas|utan API-nyckel/i.test(answerText);
  const bridgeApplied = payload.bridge?.applied === true;
  const validKinds = ["question", "site_opinion", "small_talk"];

  const checks = [];
  const check = (name, ok) => {
    checks.push({ name, ok });
    log(`   ${ok ? "✓" : "✗"} ${name}`);
  };
  check("HTTP 200", res.ok);
  check("runId === null (inget bygge)", payload.runId === null || payload.runId === undefined);
  check("version === null (ingen ny version)", payload.version === null || payload.version === undefined);
  check("inget bygge applicerades (bridge.applied !== true)", !bridgeApplied);
  check("answerText är en icke-tom sträng", answerText.trim().length > 0);
  check("answerText är INTE chat-fel-fallbacken", !isErrorFallback);
  check("answerText är INTE no-key-fallbacken", !isNoKeyFallback);
  check(
    `conversationKind är en konversation (${validKinds.join("/")})`,
    validKinds.includes(payload.conversation?.conversationKind),
  );
  check("conversation.expectsAnswer === true", payload.conversation?.expectsAnswer === true);
  // Informativt (inte hård assertion): G1 snabb-väg ger sekunder, sandbox-gaten
  // ger ~40 s. Båda är korrekta answer-only-utfall.
  log(`   • svarstid: ${ms} ms (${ms < 15_000 ? "G1 snabb-väg" : "sandbox-gate"})`);

  const failed = checks.filter((c) => !c.ok);
  if (failed.length > 0) {
    if (isErrorFallback) {
      log(`\n   ⚠️  answerText = chat-fel-fallbacken → TS-chathelpern (lib/openai.ts) kastar på prod.`);
    }
    fail(`${failed.length} assertion(er) föll: ${failed.map((c) => c.name).join("; ")}`);
  }
  log(`\n✅ ANSWER-ONLY VERIFIERAD PÅ PROD — frågan besvarades med ett riktigt svar utan bygge (${ms} ms).`);
  log(`\n   Fullt svar från dirigenten:\n   "${answerText}"`);
}

async function main() {
  log(`Prod answer-only-probe mot ${BASE}`);
  const { siteId, runId, doneEvent } = await startInitBuild();
  if (!doneEvent) {
    await pollUntilBuilt(siteId, runId);
  }
  // Liten paus så KV-pekaren + blob garanterat är synliga för G1-kontexten.
  await sleep(3_000);
  await probeQuestion(siteId);
  log(`\nKlart.`);
}

main().catch((err) => fail(err?.stack ?? String(err)));
