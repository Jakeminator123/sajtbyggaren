---
status: historical
owner: backend
truth_level: historical-reference
last_verified_commit: f56ac30
---

> **Arkivnot (lane A, 2026-06):** Historiskt beslutsstöd (B125). Aktuell
> runtime-status: [`docs/architecture/preview-runtime.md`](../architecture/preview-runtime.md)
> + ADR 0033. Se `docs/archive/README.md`.

# Preview-runtime matrix — beslutsstöd för B125

Beslutsstöd för operatör + Christopher. Sex alternativ för
preview-runtime (L2-lagret enligt halvtidsrapport
`docs/health-checks/2026-05-25-halvtid.md`). B125 är blockaren —
embedded StackBlitz fungerar bara i Chromium-browsers, ~25–35% av
svenska SMB-slutkunder är på Safari/iPhone eller Firefox.

Rapporten kompletterar inte ersätter `docs/reports/b125-preview-fallback-decision-2026-05-22.md`.

## Sex alternativ

| Kod | Namn | Status idag |
|---|---|---|
| A | StackBlitz embedded WebContainer | ~80% implementerat (`apps/viewser/lib/stackblitz-files.ts`) |
| B | Server-byggd HTML-snapshot till CDN (t.ex. Cloudflare R2 + Workers) | Ej implementerat |
| C | Lokal `next dev`-process per kund (Sajtmaskin-VM-modellen) | Ej implementerat |
| D | Vercel Preview Deployments | Ej implementerat. ADR 0030 säger "adapter, inte beroende". |
| E | "Öppna i StackBlitz"-knapp (top-level navigation, ej embed) | Ej implementerat |
| F | Vercel Sandbox (V0-stil, Firecracker microVMs) | Ej implementerat |

## Matris

| Dimension | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| Kostnad MVP (10-50 kunder, max 5 samtidiga) | $0 | $5-10/mån | $50-100/mån | $20/mån + $60 builds | $0 | $200-400/mån |
| Kostnad scale (200+ kunder) | $0 | $20-50/mån | $500-1000/mån | $1200/mån | $0 | $3600/mån |
| Browser-stöd | Chrome/Edge/Brave only | Alla | Alla | Alla | Safari/FF får ny flik | Alla |
| UX första laddning | 60-90 s | 30-60 s per Preview | under 5 s | 30-60 s per deploy | Beror på SB | 5-10 s sandbox-boot |
| UX efter första laddning | Hot reload via WC | Ingen hot reload | Hot reload | Iframe-cache snabb | Beror på SB | Hot reload |
| API/form-submission funkar i preview | Ja | Nej (statisk) | Ja | Ja | Ja | Ja |
| Effort | 5 dagar kvar | 1 vecka | 2-3 veckor | 3 dagar | 1 dag | 1 vecka |
| Vendor lock-in | StackBlitz (medel) | Låg (R2 S3-kompatibel) | Låg (vilken VPS som helst) | Hög (Vercel-API) | StackBlitz (medel) | Hög (Vercel Sandbox) |
| B125 löst? | Nej, det ÄR B125 | Ja | Ja | Ja | Delvis (UX-kompromiss) | Ja |
| Underhållsbörda | Hög (SB-API + WC + ADR 0021) | Låg (få rörliga delar) | Medel (process-mgmt + security) | Låg (Vercel) | Mycket låg | Låg (Vercel) |
| Skalfri kostnad | Ja | Ja | Nej (linjär) | Nej (linjär) | Ja | Nej (linjär) |

## Rekommendation: hybrid A + E + B

1. Browser-detection client-side (delvis implementerat:
   `getBrowserKind` + `supportsStackBlitzEmbed` i
   `apps/viewser/components/viewer-panel.tsx`).
2. Chromium-användare till Alternativ A (StackBlitz embedded). Den
   befintliga implementationen, slutförd när B125-fallback finns.
3. Safari/Firefox-användare till Alternativ B (server-byggd HTML-
   snapshot via Cloudflare R2 + Workers). Bygg-server triggas på
   Preview-knapp, snapshotar HTML, uploadar, iframe pekar dit.
   Cirka 5-10 dollar/mån, skalar inte med kunder.
4. Soft fallback för båda till Alternativ E ("Öppna projektet i
   StackBlitz" som länk, top-level navigation). Säkerhetsventil om
   både A och B misslyckas.

## Varför inte C, D eller F som default

- C (VM next dev): bästa UX, men linjär kostnad. Sajtmaskin-erfarenhet
  visade att server-side preview tappar pengar vid scale.
- D (Vercel Preview): ADR 0030 låser Vercel som adapter, inte beroende.
  Vid 200 kunder ungefär 1200 dollar/mån — vi betalar Vercel för att
  vara mellanhand.
- F (Vercel Sandbox): snyggt tekniskt, dyrast. V0:s modell kräver
  premium-pricing som inte matchar svenska SMB-segmentet.

## Vad detta INTE löser

- L1 (publicerade kund-sajter): separat hosting-beslut, kan komma med
  egen ADR senare.
- L3 (sajtbyggaren-appen hostas där): separat fråga, troligen Vercel
  oavsett B125-beslut.
- L4 (bygg-runtime för server-snapshot i B): ny krav — behöver en
  burk som kan köra Next.js-build. Hetzner/DO/Cloudflare Workers.

## Nästa steg

1. Operatör + Christopher diskuterar matrisen.
2. Beslut låses i ny ADR 0033 (Preview-Runtime Hybrid Default).
   (Spekulerat 0031 är upptaget av Steward auto-bump; spekulerat 0032
   av section-treatments efter B146-port — nästa lediga är 0033.)
3. Implementations-PR mot jakob-be (sannolikt cloud-grind-agent
   eftersom ren mekanisk implementation).

## Referenser

- `docs/health-checks/2026-05-25-halvtid.md` §9 punkt 1 (B125-fråga)
- `docs/known-issues.md` B125 (full bugg-beskrivning)
- `governance/decisions/0003-preview-runtime-stackblitz-first.md`
  (original ADR som rekommenderade StackBlitz first)
- `governance/decisions/0025-browser-fallback-preview.md`
  (browser-fallback ADR)
- `governance/decisions/0028-runtime-ladder.md`
  (runtime ladder för PreviewRuntime)
- `governance/decisions/0030-preview-provider-portability.md`
  (Vercel som adapter, inte beroende)
- `docs/reports/b125-preview-fallback-decision-2026-05-22.md`
  (tidigare beslut-stöd, kompletteras av denna)
