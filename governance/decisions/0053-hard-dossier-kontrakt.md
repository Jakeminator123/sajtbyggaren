# ADR 0053 — Hard-dossier-kontrakt: env-, code- och integration-kontrakt + mockMode-regler

**Status:** Proposed
**Datum:** 2026-06-11
**Beroenden:** ADR 0012 (dossier-klasserna soft/hard, hybrid borttagen),
ADR 0048 (hostad byggväg: env-injektion i sandbox), policyn
[`dossier-contract.v1.json`](../policies/dossier-contract.v1.json) (v3) och
agentguiden
[`packages/generation/orchestration/dossiers/AGENT-GUIDE.md`](../../packages/generation/orchestration/dossiers/AGENT-GUIDE.md).
Utlöst av audit 2026-06-11: hard-dossier-kontrakten är den uttalade
blockeraren för `resend-contact-form` som första hard-dossier.

## Kontext

Tretton soft-dossiers är implementerade; hard-klassen är tom. Mappstrukturen
i `dossiers/README.md` listar tre kontraktsfiler för hard-dossiers —
`code-contract.json`, `env-contract.json`, `integration-contract.json` — men
alla tre är markerade "planerad Sprint 3+" och saknar definition. Policyn
`dossier-contract.v1.json` bär redan embryot: `envContractRequiredFields`
(`requires`, `designModeBehavior`, `integrationModeBehavior`) och
`codeContractRequiredFields` (`must`, `avoid`) finns deklarerade, men ingen
fil, inget schema och inget flöde konsumerar dem.

Konsekvensen är att ingen agent säkert kan montera en hard-dossier: det som
saknas är inte en manifest-fil utan hela kedjan server-route i genererad
sajt, env-injektion i bygget (lokalt och hostat per ADR 0048) och ett ärligt
designläge när env saknas. Agentguiden säger detta uttryckligen: den första
hard-dossiern är ett infraprojekt.

## Beslut

De tre kontraktsfilerna definieras enligt nedan. Den här ADR:n låser
*formatet och reglerna*; implementeringen (scheman, validering, monterings-
flödet, första dossiern) är en egen slice och ingår inte i detta beslut.

### 1. `env-contract.json` — vad integrationen kräver av miljön

Bygger på policyns befintliga `envContractRequiredFields`:

```json
{
  "requires": [
    {
      "name": "RESEND_API_KEY",
      "purpose": "Serverside-anrop till e-postleverantören.",
      "scope": "runtime",
      "valueFormat": "re_..."
    }
  ],
  "designModeBehavior": "Formuläret renderas komplett men submit visar ett ärligt designläge-besked; inga nätverksanrop görs.",
  "integrationModeBehavior": "Submit postar till sajtens egen server-route som anropar leverantören; svar/fel visas ärligt."
}
```

Regler:

- `requires[].name` är exakta env-namn; **aldrig** värden eller riktiga
  nycklar, inte ens exempel (`valueFormat` beskriver bara formen).
- `scope` är `build` eller `runtime` — styr var injektionen sker: lokalt via
  operatörens env, hostat via sandbox-env (ADR 0048-vägen).
- Manifestets `envVars` ska vara exakt unionen av `requires[].name`
  (korsvalideras i implementations-slicen).

### 2. `code-contract.json` — vad den genererade koden måste och inte får

Bygger på policyns `codeContractRequiredFields`:

- `must`: numrerade, testbara krav på koden som monteras i användarsajten —
  t.ex. att formulärsubmit går till en server-route i den egna sajten, att
  validering sker server-side, att fel renderas ärligt och att designläget
  aktiveras automatiskt när env saknas.
- `avoid`: anti-mönster som aldrig får skeppas — t.ex. hemligheter eller
  leverantörsanrop i klientkod, submit mot en route som inte genereras, eller
  copy som lovar fungerande integration i designläge.

### 3. `integration-contract.json` — hur förmågan aktiveras och verifieras

- `provider`: leverantörsslug (t.ex. `resend`).
- `activation`: speglar policyns `activationFieldRequirements.hard` —
  `explicit-or-strong-semantic`, `requiresUserMention: true`. En hard-dossier
  väljs aldrig in enbart via brief-semantik.
- `mockMode`: triggern är saknad env (någon av `requires[].name`); beteendet
  är `designModeBehavior`. Designläget måste vara visuellt komplett men
  ärligt — aldrig fejkad success, aldrig påhittad bekräftelse.
- `verification`: steg som avgör att integrationsläget faktiskt fungerar
  (t.ex. provanrop bakom operatörsflagga), så `appliedVisibleEffect`-klassens
  ärlighetssignaler kan grundas i verklighet även för hard-förmågor.

### Gemensamma regler

1. Kontraktsfilerna blir **obligatoriska för `class: "hard"`** via en
   policy-bump av `dossier-contract.v1.json` (v3 -> v4:
   `additionalRequiredFilesByClass.hard` fylls) plus JSON-scheman under
   `governance/schemas/` — i implementations-slicen, inte här.
2. Soft-dossiers påverkas inte: kraven gäller bara hard-klassen.
3. Ärlighetsprincipen ärvs oförändrad: montering utan synlig/fungerande
   effekt rapporteras som mount-only respektive designläge — UI får aldrig
   påstå att en hard-förmåga fungerar innan env finns och verifieringen
   passerat.

## Första konsument: `resend-contact-form`

`mailto-contact-form` förblir soft default för capabilityn `contact-form`.
`resend-contact-form` blir första hard-dossier och etablerar därmed flödet:
server-route i den genererade sajten, env-injektion lokalt + hostat,
mockMode-rendering och selektering med `requiresUserMention`. Det är ett
infraprojekt och planeras som egen slice med denna ADR som kontrakt.

## Konsekvenser

- Plus: en agent som ska bygga/montera en hard-dossier har för första gången
  komplett förhandsinfo (manifest + instructions + tre kontrakt); 80%-
  principen i agentguiden gäller även hard-klassen; ärligheten blir
  verifierbar i stället för lovad.
- Minus: mer författaryta per hard-dossier (tre filer till), och
  implementations-slicen måste bygga monterings-/injektionsflödet innan
  första dossiern ger kundvärde.
- Neutralt: policyfälten fanns redan i v3 — beslutet aktiverar dem snarare
  än uppfinner dem.
