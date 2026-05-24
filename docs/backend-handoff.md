> **SUPERSEDED** — detta dokument täcker wizardens 5-stegsomstrukturering
> från 2026-05-19. För aktuell status inklusive builder-shell, floating-chat,
> local-preview och Sprint A/B, se `docs/backend-handoff-2026-05-22.md`.

# Backend handoff — Discovery Wizard 5-stegs-omstrukturering

Skapad: 2026-05-19 (Pass 6 av wizardens omdesign på `christopher-ui`).
Mottagare: backend-teamet (resolver, prompt-pipeline och upload-API).

UI:t på `christopher-ui` har refactorats till 5 steg som mappar 1:1 mot
pipelinens valpunkter:

| Steg | UI-titel | Driver pipeline-del |
| --- | --- | --- |
| 1 | Företaget & sajttypen | Scaffold + Starter |
| 2 | Visuell identitet | Variant |
| 3 | Funktioner & sidor | Dossier + Routes |
| 4 | Innehåll & ton | Copy |
| 5 | Bilder & media | Copy (assets) |

Nya fält som skickas till `/api/prompt` (via `buildDiscoveryPayload` +
`composeMasterPrompt`) ligger redan i payloaden — men för flera av dem
saknas backend-stöd. Detta dokument listar exakt vad som krävs per gap.

> Inga av gappen är blocking för att starta en build. Wizarden faller
> tillbaka till nuvarande beteende om backend ignorerar nya fält.

---

## Gap 1 — `vibe.useCustomColors` ska skriva över variantens defaultfärger

**Frontend skickar:**

```json
{
  "answers": {
    "vibe": {
      "vibeId": "warm-craft",
      "useCustomColors": true
    },
    "brand": {
      "primaryColorHex": "#2D5F3F",
      "accentColorHex": "#D4A574"
    }
  }
}
```

**Backend behöver:**

- Om `vibe.useCustomColors === true`, läs `brand.primaryColorHex` och
  `brand.accentColorHex` och skriv över variantens `--primary` och
  `--accent` i `app/globals.css` (eller på rätt plats i variant-token-
  pipelinen).
- Om `false` eller saknas: använd variantens defaults (nuvarande
  beteende).

**Relaterade filer:**
- `packages/generation/orchestration/scaffolds/<id>/variants/<id>/tokens.json`
- `scripts/build_site.py` (variant-tillämpning)

**Acceptanskriterium:**
- En sajt med `useCustomColors=true` ska visa operatorns färger i CSS,
  inte vibens defaults.

---

## Gap 2 — `vibe.vibeId` ska användas som primärt variant-val

**Frontend skickar:** `vibe.vibeId = "warm-craft"` (en av 10 vibes i
`apps/viewser/components/discovery-wizard/wizard-constants.ts`).

**Backend behöver:**

- I Discovery Resolver / Site Brief-extraktorn, om `answers.vibe.vibeId`
  finns och matchar ett känt variant-id, sätt det som vald variant
  innan planner-modellen.
- Om vibe inte hittas eller är tom, fall tillbaka till nuvarande
  variant-selektion.

**Acceptanskriterium:**
- Demo-profilen `genberg-painter` (`vibeId="warm-craft"`) ska resultera
  i `selected_variant.id === "warm-craft"` i `site-brief.json`.

---

## Gap 3 — `businessFamily` ska användas som scaffold-hint

**Frontend skickar:** `businessFamily: "ecommerce" | "restaurant" | ...`
(8 BusinessFamilyId-värden).

**Backend behöver:**

- I Discovery Resolver, prioritera `answers.businessFamily` över
  `siteType[]` när scaffold ska väljas.
- Mappning: `service|health|creative|construction|consulting|landing|restaurant`
  → `local-service-business`, `ecommerce` → `ecommerce-lite`.

`buildDiscoveryPayload` redan sätter `payload.scaffoldHint` korrekt
baserat på family — backend behöver bara läsa det istället för att
räkna ut det från siteType.

**Acceptanskriterium:**
- En sajt med `businessFamily="ecommerce"` men `siteType=[]` ska få
  scaffold `ecommerce-lite`.

---

## Gap 4 — `selectedFunctions[]` ska driva Dossier-val

**Frontend skickar:**

```json
{
  "answers": {
    "selectedFunctions": ["fn-team", "fn-pricing", "fn-quote"]
  }
}
```

Varje funktion har en `capability`-slug i
`FUNCTION_GROUPS[*].choices[*].capability`. `composeMasterPrompt`
skriver redan "Önskade funktioner: ..." till prompten.

**Backend behöver:**

- I `requested_capabilities[]` (SiteBrief), inkludera alla unika
  `capability`-slugs som matchar valda funktioner.
- Detta gör att Dossier-resolvern kan välja rätt komponenter utan att
  förlita sig på LLM-extraktion av samma info.

**Mappning ligger i:**
- `apps/viewser/components/discovery-wizard/wizard-constants.ts`
  → `FUNCTION_GROUPS`.

**Acceptanskriterium:**
- En sajt med `selectedFunctions=["fn-booking"]` ska få
  `capabilities.includes("online-booking") === true`.

---

## Gap 5 — `specialRequests` ska bli `notes_for_planner`

**Frontend skickar:** Fritext från Steg 3-fältet "Specialönskemål".

**Backend behöver:**

- I SiteBrief, lägg `answers.specialRequests` (eller relevant del) i
  `notes_for_planner`-fältet så planner-modellen ser dessa krav.

**Acceptanskriterium:**
- En sajt med `specialRequests="Instagram-feed på startsidan"` ska
  producera en `site-plan.json` där planner explicit nämner Instagram-
  feed-kapabiliteten.

---

## Gap 6 — Favicon-stöd i `/api/upload-asset` och build-pipeline

**Frontend skickar:** `media.favicon` (en `AssetRef` med någon
PNG/SVG-fil).

**Backend behöver:**

1. **Upload-API**: acceptera filer som inte automatiskt klassas som
   "logo"/"hero"/"gallery" — eller utöka `AssetRole` med `"favicon"`.
2. **Build-pipeline**: när `media.favicon` finns, konvertera till
   `public/favicon.ico` (multi-size 16/32/48/64 px) via `sharp` eller
   `imagemagick`.
3. **Project Input mapping**: peka `metadata.favicon` på den
   genererade ICO-filen så Next.js plockar upp den.

**Acceptanskriterium:**
- En sajt med favicon-upload ska ha `public/favicon.ico` med 4
  storlekar.

---

## Gap 7 — OG-image-stöd (1200×630 crop)

**Frontend skickar:** `media.ogImage` (en `AssetRef` med en
JPG/PNG/WebP-fil).

**Backend behöver:**

1. **Build-pipeline**: när `media.ogImage` finns, croppa till
   1200×630 px (center-crop) via `sharp` och skriv till
   `public/og-image.png`.
2. **Metadata**: sätt `<meta property="og:image">` och
   `<meta name="twitter:image">` på rätt root-route så social
   delning hämtar den.

**Acceptanskriterium:**
- Facebooks Sharing Debugger ska visa rätt 1200×630-preview.

---

## Gap 8 — Video-mimetype stöd i `/api/upload-asset`

**Frontend skickar:** `media.backgroundVideo` (en `AssetRef` med
`mimeType: "video/mp4"` eller `"video/webm"`).

**Backend behöver:**

1. **Upload-API** (`apps/viewser/app/api/upload-asset/route.ts`):
   tillåt mime-types `video/mp4` och `video/webm`. Hoppa över
   `sharp`-pipelinen för videon (sharp stödjer inte video).
2. **GPT Vision**: hoppa över för video — Vision-API:t stödjer inte
   video. Sätt `visionConfidence = null` istället för att fela.
3. **Build-pipeline**: kopiera videon till `public/hero-video.mp4`
   och rendera `<video autoplay loop muted playsInline>`-tag i hero-
   sektionen som tillval över hero-bilden.
4. **Fallback**: om video-fil saknas eller inte stöds av browsern,
   fall tillbaka till `assets.heroImage` automatiskt.

**Acceptanskriterium:**
- En sajt med upload av en 5 MB MP4 ska visa videon som hero-bakgrund
  i Chrome/Safari/Firefox.

---

## Gap 9 — `moodImages[]` skickas till Vision men inte sajten

**Frontend skickar:** `moodImages: AssetRef[]` (1-5 referensbilder
för stämning/färg).

**Backend behöver:**

- Mood-bilder ska INTE kopieras till `public/uploads/` (de är inte
  sajt-assets — bara inspiration).
- I `composeMasterPrompt` skickas redan en text-sammanfattning per
  mood-bild. Om backend kör Vision separat på dem för att extrahera
  färgpalett/stil — inkludera det i `site-brief.notes_for_planner`.

**Acceptanskriterium:**
- Mood-bilder ska finnas i `data/uploads/<runId>/__mood/` men inte i
  `public/uploads/` på den färdiga sajten.

---

## Gap 10 — `products[].productImage` ska bli sajtens produktbild

**Frontend skickar:** Per produkt, en valfri `productImage: AssetRef`.

**Backend behöver:**

- I `copy_operator_uploads` (build_site.py), kopiera varje produkts
  `productImage` till `public/products/<productId>.<ext>` och peka
  `products[].imageUrl` på den genererade URL:en.
- Om `productImage` saknas, fall tillbaka till befintlig
  `imageUrl`-text-input eller en generisk placeholder.

**Acceptanskriterium:**
- En e-handelssajt med 4 uppladdade produktbilder ska visa dem på
  produkt-grid-sidan utan extra konfiguration.

---

## Gap #11 — Vercel Blob för asset-uppladdningar (`AssetRef.sourceUrl`)

**Status frontend:** klar. `apps/viewser/lib/asset-store/vercel-blob.ts`
implementerar `AssetStore`-interface:t mot Vercel Blob. Aktiveras med
`ASSET_STORE_DRIVER=vercel-blob` + `BLOB_READ_WRITE_TOKEN` i env.
`AssetRef`-typen har fått ett nytt optional `sourceUrl`-fält
(`apps/viewser/lib/asset-store/types.ts`) som driver:n fyller i med
public blob-URL:n för `optimized.webp` (eller SVG-originalet).
`/api/asset-preview` 307-redirectar till blob-URL:n när driver:n inte
är `LocalAssetStore`.

**Varför:** persistens i molnet (uppladdningar tappas inte vid byte av
maskin / Cloud Agent VM), förberedelse för video senare (då blob-URL
kan embed:as direkt eftersom video är för tung att kopiera in i
StackBlitz-payloaden), ingen disk-IO som blockerar för stora filer.

**Backend behöver:**

1. **`scripts/build_site.py copy_operator_uploads`** — när
   `ref.sourceUrl` finns: HTTP-fetcha bytes från URL:en och skriv till
   `public/uploads/<ref.filename>`. När fältet saknas: behåll dagens
   disk-lookup oförändrad. Mock så att test:s utan nätverk fortsatt
   funkar — t.ex. via en `requests` mock eller env-flagga som hoppar
   över fetch.

   Skeleton (Python):
   ```python
   if ref.get("sourceUrl"):
       resp = urllib.request.urlopen(ref["sourceUrl"], timeout=15)
       dest = public_uploads / ref["filename"]
       dest.write_bytes(resp.read())
       copied += 1
       continue
   # ... existing disk-based logic ...
   ```

2. **`governance/schemas/project-input.schema.json`** — `$defs.assetRef`
   måste tillåta `sourceUrl` (optional, string, format=uri). Idag
   `additionalProperties: false`, så payload med fältet skulle avvisas
   av `validate_project_input`. Diff:

   ```json
   "visionConfidence": { "type": "string", "enum": ["low","medium","high"] },
   "sourceUrl": {
     "type": "string",
     "format": "uri",
     "description": "Public HTTPS-URL där optimerade bytes kan hämtas. Satt av VercelBlobAssetStore när ASSET_STORE_DRIVER=vercel-blob. När fältet finns ska copy_operator_uploads fetcha bytes härifrån istället för disk-lookup i data/uploads/."
   }
   ```

3. **Naming-dictionary** — `governance/policies/naming-dictionary.v1.json`
   bör få en entry för `assetSourceUrl` och uppdatera
   `operatorUpload`-definitionen att nämna både disk- och blob-paths.

4. **Tester** — `tests/test_operator_uploads.py` behöver ett nytt fall:
   asset med `sourceUrl` ska fetchas (mocka `urllib.request.urlopen`)
   istället för diskat.

**Acceptanskriterium:**

- Operatör laddar upp logo via wizard med `ASSET_STORE_DRIVER=vercel-blob`.
- Wizard-preview rendererar via `/api/asset-preview` (307 → blob-URL).
- Build körs och `public/uploads/<filename>` innehåller samma bytes
  som blob:en — sajten är fortfarande fristående efter build.
- Att växla tillbaka till `ASSET_STORE_DRIVER=local` är non-breaking
  (bara nya uppladdningar går till disk; gamla blob-refs fortsätter
  funka via sourceUrl).

**Storlek:** S (Python: ~30 rader + 1 test, schema: 1 fält, naming:
2 entries).

---

## Sammanfattning — vad gör vi nu?

UI:t fungerar end-to-end på dagens backend-beteende (alla nya fält
ignoreras gracefully). Gap 1-3 är **högst prio** för att new wizard
ska kännas meningsfull. Gap 6-8 kan vänta tills vi vill ha "rik"
sajtprofil. Gap 11 (Blob) är behovsdriven — växla bara på
`ASSET_STORE_DRIVER=vercel-blob` när backend har stöd för
`sourceUrl`-fältet i `copy_operator_uploads`.

| Gap | Prio | Storlek |
| --- | --- | --- |
| 1. useCustomColors | Hög | S (variant-token-skrivning) |
| 2. vibeId variant-val | Hög | S (resolver-prioritering) |
| 3. businessFamily scaffold | Hög | XS (läs istället för räkna) |
| 4. selectedFunctions capabilities | Hög | S (mappning + injektion) |
| 5. specialRequests notes_for_planner | Medel | XS (passa igenom) |
| 6. Favicon-konvertering | Låg | M (sharp .ico + metadata) |
| 7. OG-image crop | Låg | S (sharp center-crop) |
| 8. Video-mimetype + render | Låg | M (upload + build + fallback) |
| 9. Mood-bilder isolering | Låg | XS (path-route) |
| 10. ProductImage per produkt | Medel | S (copy_operator_uploads) |
| 11. Vercel Blob `sourceUrl` | Medel | S (fetch i copy_operator_uploads + schema) |

Frontend-payload är dokumenterad i
`apps/viewser/components/discovery-wizard/wizard-payload.ts`. Schema-
version `1` bevaras — om ni gör större ändringar i fältnamn, bumpa
till `2` och håll båda parallellt en period.
