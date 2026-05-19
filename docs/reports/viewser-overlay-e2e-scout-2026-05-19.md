# Viewser Overlay E2E Scout — 2026-05-19

**Roll:** Scout (read-only, interaktiv, guidar operatören steg-för-steg)
**Modell:** Claude Opus 4.7
**Datum:** 2026-05-19
**HEAD-SHA vid scout-start:** `99ec56d`. **HEAD-SHA vid scout-pickup (2026-05-19 morgon):** `9176f5e` (`docs(steward): bump for PR #38 merge (48a6a22) + register B129`) ovanpå merge-commit `48a6a22` för PR #38 (8 nya canonical Scaffold Variants under `packages/generation/orchestration/scaffolds/<scaffold>/variants/`). PR #38 mergades av en parallell agent ~01:38 UTC medan scout väntade. **Variants är dead code i prod-flödet via `_DEFAULT_VARIANT_BY_SCAFFOLD`-guard i `packages/generation/planning/plan.py:364-385`** som tvingar `local-service-business → nordic-trust` och `ecommerce-lite → clean-store`. Discovery taxonomy är oförändrad. Scout-mätningen är därför **fortsatt representativ för dagens prod-flöde** — Case 1-6 mäter exakt vad slutkunden ser idag. **B129 öppnad** (medvetet) på den hardcoded mappingen — flytt till governance + ny ADR ligger i variant-promotion-sprint (Queue #6), inte i Scout-scopet.
**Branch:** `main`. Working tree dirty bara med `post-frontend-merge.txt` (operatörsanteckning) + denna rapport-fil (untracked).
**Audit-confidence:** 7/10 — Case 1+2+3a verifierat live mot generated TSX + Project Input meta-sidecar; Case 4 (sköldpaddssoppa / conflict), Case 6 (follow-up byte-stabilitet) och Spår B (variant-experiment) ej körda så subjektiv kvalitetsbedömning utöver det som redan landat är osäker.
**Status:** **AVSLUTAD (delvis)** — Case 1-3a körda, Case 4/6/3b + Spår B kvar för senare körning.

## Mål

Verklig frontend-kvalitetsmätning via det faktiska Viewser-overlayflödet (DiscoveryWizard → POST `/api/prompt` → build_site.py → preview), **inte** ännu en torr CLI-discovery-smoke. Coach-direktiv 2026-05-19: "verklig frontend-kvalitetsmätning via det faktiska overlayflödet, inte mer CLI-discovery-plumbing".

Sex case planerade. Operatören väljer slutligt set och kör så många hen hinner; rapporten markerar resten som "ej testat".

## Sammanfattning

- **Totalsnitt: ~7.1/10** över tre mätbara case (Case 1 ~7.3, Case 2 ~7.4, Case 3a ~6.6) — jämfört med Scout 4-baseline 6.59/10 för CLI-cases. Snittet är **över beslutsregelns 7-tröskel** men marginalen är liten — Case 3a (6.6/10) är under det villkorade 6.5-golvet bara om man räknar strikt på "inget case under 6.5"; Case 3a landar på 6.6 vilket är ≥6.5 så regeln är formellt uppfylld.
- **Verdict mot beslutsregel:** ≥7/10 OCH inget case <6.5 → uppfyllt. Project DNA-sprint är öppen som möjligt nästa steg, men auto-merge-pipelinen 2026-05-19 stängde redan B130/B131/B132/B133/B134/B135 vilket adresserar de mest kritiska fynden i Case 1-3a. Scout-rekommendation: Spår B variant-experiment + Case 4/6/3b (~30 min totalt) innan Project DNA-spår låses, så vi har komplett baseline-data.
- **Direkt nästa rekommenderat steg:** något av (a) Spår B variant-experiment (B1 keramik+earth-wellness, B2 frisör+warm-craft) för visuell kvalitetsbedömning + B129-underlag, (b) Case 4 (sköldpaddssoppa / conflict) för att mäta Intent Guard-behov, (c) variant-promotion-sprint (B129) eller B125 browser-fallback-ADR (produktblockare innan kundyta), eller (d) Project DNA / semantic follow-up merge.
- **Modell-/insatsnivå nästa Builder-pass:** låg-medel. B130/B131/B132/B133/B134/B135 stängda parallellt under operatörens 1-h-paus med composer-2.5 + RO-review; samma orchestrator-mönster fungerar för B-IDs i låg-medel-spannet. Project DNA-sprint kräver dock djupare modell (Claude 4.6 / GPT 5.5) eftersom semantic merge i `merge_followup_project_input` är arkitektoniskt val, inte fix.

## Förkonfiguration verifierad

Innan operatören börjar: HTTPS-cert, `.env.local` med OPENAI_API_KEY, ledig port 3000, repo HEAD som ovan.

## Kartläggning per case (förväntat utfall)

För varje case: vad operatören klickar i wizarden, vilken DiscoveryPayload som genereras, vad Discovery Resolver ska producera, vilka routes som ska byggas, och vilka B-IDs som verifieras.

### Case 1 — KERAMIK E-HANDEL (verifierar B101/B102/B128 LIVE)

**Wizard-val (förslag):**
- Steg 1 Företag: namn (t.ex. "Atelje Vit Lera"), offer="Liten e-handel på svenska för försäljning av keramik med fokus på köpkonvertering", inga kontaktfält.
- Steg 2 Kategori: chip `Webshop / E-handel` (id `ecommerce`).
- Steg 3 Innehåll: minst 1-2 produkter (`name`, `price`) — t.ex. "Stengods-mugg" 280 kr, "Vas i seladon" 750 kr.
- Steg 4 Story: kort om-text på svenska (t.ex. "Liten studio i Hagsätra som drejar bruksföremål för vardagsbordet."). **Ingen** "Bygg ..."-fras här — det är planner-imperativen som ska blockas i Step 6 av build_site, inte här.
- Steg 5 Sidor: defaults för ecommerce: `Startsida / Hero`, `Webshop / Produkter`, `Om oss / Om mig`, `FAQ`, `Kontaktformulär`. Primär CTA: `Köp nu`.
- Steg 6 Bilder: skippa.
- Steg 7 Ton: skippa.

**Förväntad DiscoveryPayload:**
- `schemaVersion: 1`, `contentBranch: "ecommerce"`, `scaffoldHint: "ecommerce-lite"`, `answers.siteType: ["ecommerce"]`, `answers.primaryCta: "Köp nu"`.

**Förväntad DiscoveryDecision (resolver):**
- `selectedScaffoldId: ecommerce-lite`, `selectedVariantId: clean-store`, `expectedStarterId: commerce-base`, `selectionSource: taxonomy`, `operatorReviewRequired: true` (capability-unknown ecommerce från `Webshop / Produkter` + capability-gap payments/contact-form).
- `categoryIds: ["ecommerce"]`, `contentBranch: ecommerce`.
- `fallbackWarnings`: minst `capability-gap` på `payments` och `contact-form`, plus `capability-unknown` på `ecommerce` (intern alias från `Webshop / Produkter`-mustHave).
- `fieldSources`: `scaffoldId=taxonomy`, `variantId=taxonomy`, `company.name=wizard`, `company.tagline=wizard`, `company.story=wizard`, `requestedCapabilities=wizard|taxonomy`, `conversionGoals=wizard`.

**Förväntade routes:** `/`, `/produkter`, `/om-oss`, `/kontakt`. (Builder MVP packar 4 sidor från ecommerce-lite-scaffolden oavsett vad pageIntent säger — separat fynd om "2 sidor"-case visar mismatch.)

**B101/B102/B128-verifikation (kärnan):**
- **B101:** Hero-CTA-knappen på `/` ska ha texten **"Shoppa nu"** OCH `href="/produkter"` (inte `/kontakt`). Verifieras genom att inspektera knappen i preview eller läsa generated `app/page.tsx` under `data/runs/<runId>/...` eller `../sajtbyggaren-output/.generated/<siteId>/`.
- **B102:** Bottom-CTA på `/produkter` ska ha texten **"Hör av dig för att beställa"** (sv) eller "Get in touch to order" (en). Inte "Fråga om en beställning".
- **B128:** `/om-oss` ska INTE innehålla någon Bygg-/Skapa-/Make-/Build-imperativ. Den ska heller inte börja med markdown-prefix (`-Bygg`, `**Bygg`, `1. Bygg`). Texten ska vara antingen briefModels notesForPlanner (om customer-safe) eller en fallback-mening typ "Keramikstudio i Stockholm med tydligt erbjudande, enkel kontaktväg och ett fokuserat nästa steg för besökaren."

### Case 2 — TJÄNSTEFÖRETAG MED ADRESS (skuggar B119/B120)

**Wizard-val:** företag (t.ex. "Snickeri Älvsjö AB" eller en frisörsalong), kategori `Företag / Tjänster` (id `business`) eller `Bygg / Hantverk` (id `construction`) eller `Salong / Skönhet` (id `salon`). Adress: **explicit svenskt komma-format** "Götgatan 12, 11646 Stockholm" i steg 1-fältet `Adress`.

**Förväntad resolver:** `selectedScaffoldId: local-service-business`, `selectedVariantId: nordic-trust`, `expectedStarterId: marketing-base`, `selectionSource: taxonomy`, `operatorReviewRequired: false` (om ingen booking på mustHave) eller `true` om mustHave innehåller `Bokning online` (capability-unknown booking).

**Förväntad city-extraktion:**
- Resolverns `_apply_location_from_address` kör regex `\b\d{3}\s?\d{2}\s+([A-Za-zÅÄÖåäö\-]+)` mot `addressLines[0]`.
- "Götgatan 12, 11646 Stockholm" → match på "11646" + " Stockholm" → `location.city = "Stockholm"`, `country = "Sverige"`, `serviceAreas = ["Stockholm"]`.
- B120-skuggning: kontrollera att city BLIR "Stockholm" och inte "Sverige" eller country-only.

**B119-skuggning:** scrape körs inte i detta case (manuellt ifyllt), så B119 (alfabetisk email-sortering) skuggas i Case 3.

**Förväntade routes:** `/`, `/tjanster`, `/om-oss`, `/kontakt`. Hero-CTA "Begär offert" → `/kontakt`.

### Case 3 — SCRAPE-CASE

**Wizard-val:** operatören skriver in URL i steg 1 `Befintlig hemsida`-fältet och klickar `Hämta`. Tjänar både B113 (SSRF-redirect-validation) och B118 (scrape-runner SIGKILL-fallback) sanity-check, samt B119 (kontaktdata).

**Förslag URL:** verklig liten svensk småföretagssajt. Operatören väljer själv — exempelvis en lokal frisör/snickare/restaurang/butik vars sajt operatören känner till. Helst en sajt med:
- Synlig email + telefon i footer eller på `/kontakt`.
- Synlig adress.
- Inte en SPA (BeautifulSoup måste kunna parsa HTML i första requesten).

**Förväntat scrape-resultat:** `/api/scrape-site` returnerar `{ ok: true, data: { companyName, offer, contact: { phone, email, address }, ... } }`. Wizardens fält fylls i via `onChange(patch)`. Operatören granskar och justerar.

**B119-skuggning:** är email-valet vettigt? `scripts/scrape_site.py` plockar idag potentiellt första alfabetisk email (info@... vinner över verkligt kontakt). Om operatören ser en konstig email i wizardens kontakt-fält efter scrape: registrera detta som B119-bekräftelse.

**Förväntad resolver/build:** likt Case 2 efter att wizarden är ifylld. Test av att scrape-data flödar genom hela kedjan utan att tappas.

### Case 4 — SKÖLDPADDSSOPPA / CONFLICT-CASE (Intent Guard-fråga)

**Wizard-val:** medvetet **fel** kategori. Förslag:
- Kategori: `Gym / Tränare` (id `fitness`) eller `Bygg / Hantverk` (id `construction`).
- Företag: t.ex. "Sköldpaddssoppa Karlsson".
- Beskrivning: "Hemsida om sköldpaddssoppa, mat, 2 sidor, gröna färger".
- Inga andra kontextfält.

**Förväntat utfall (today):**
- Resolver väljer scaffold = `local-service-business`, variant = `nordic-trust`, starter = `marketing-base` (fitness/construction är båda active i taxonomi och pekar mot local-service-business).
- Build går grön. Sajten blir ett gym/byggföretag med "Sköldpaddssoppa Karlsson"-namn och soppa-text — produktmässigt fel, men ingen warning.
- **Ingen Intent Guard finns idag.** Inget i pipeline jämför "fri prompt säger mat/soppa" mot "wizard säger gym/bygg".

**Frågan att besvara:**
1. Visas någon warning i ConsoleDrawer eller PromptStatusStrip? (Förväntat: nej.)
2. Skulle en Intent Guard hjälpa, eller har keramik-fix:en (B128-blocklist) redan höjt baselinen tillräckligt? Mät hur "fel" output:en känns på en 1-10-skala.

### Case 5 — "2 SIDOR"-CASE (Page Intent-fråga)

**Wizard-val:** explicit fri prompt. Förslag:
- Företag: en standard-bransch (t.ex. en juridiksajt eller fotograf).
- Beskrivning: "Jag vill ha en liten hemsida med 2 sidor — bara start och kontakt, inget mer."
- Wizard-pages: avmarkera allt utom `Startsida / Hero` och `Kontaktformulär`.

**Förväntat utfall (today):**
- Wizard låter operatören välja antal mustHave-sidor, men **discovery resolver** mappar bara till capabilities, inte till antal routes.
- Builder genererar fortfarande scaffold-baserat (4 routes för local-service-business eller ecommerce-lite). Sidantal från wizard respekteras inte.
- **Ingen pageIntent-logik finns idag.** Antingen visas ingen mismatch-signal, eller så ger bygget 4 sidor utan kommentar.

**Frågan att besvara:**
1. Skapar systemet en mismatch-signal när wizard säger "2 sidor" och scaffold ger 4?
2. Visar Backoffice/Run Details något om sidantal?

### Case 6 — FOLLOW-UP (verifierar B71-status)

**Wizard-val:** kör Case 1 (keramik) eller Case 2 (tjänsteföretag) till färdig build, växla till `Följdprompt`-läget och skriv "byt huvudfärg till grön" eller "ändra ton till mer lekfull". Build v2.

**Förväntat utfall:**
- v2 bevarar `projectId`, bumpar version till 2.
- Visuellt: ny färg (om brand.primaryColorHex ändras) eller ny ton.
- B71-byte-stabilitet: story/tagline/tone ska INTE byta oavsiktligt om operatören bara bett om färgändring.

**Frågan att besvara:**
1. Syns v2 visuellt annorlunda?
2. Har story/tagline/tone bytts utan att operatören bett om det? (Det vore en B71-regression.)

## Per case: prompt + observation + screenshots + poäng + anteckningar

Varje case fyllls i av Scout efter att operatören kört det och rapporterat tillbaka. Tom mall för varje:

### Case 1 (keramik) — KÖRD 2026-05-19 11:50-12:00 UTC+2

**Wizard-input:** companyName=`Atelje Vit Lera`, offer=`Liten e-handel på svenska för försäljning av keramik med fokus på köpkonvertering`, kategori=`Webshop / E-handel` (id `ecommerce`), aboutText=`Liten studio i Hagsätra som drejar bruksföremål för vardagsbordet`. Inga produkter i Steg 3 (operatören byggde direkt). CTA=`Köp nu`. Inga assets, inga toner.

**siteId:** `operatorens-beskrivning-0d1392` (avvikande — borde varit `atelje-vit-lera-...`; se Obs 1 nedan).
**Generated path:** `..\sajtbyggaren-output\.generated\operatorens-beskrivning-0d1392\`.
**Build-status:** `ok` (build slutförd, sajt på disk).
**Preview:** "Unable to run Embedded Project" — operatörens dev-server kör på `http://` (gamla servern), `-Https`-flaggan misslyckades med EADDRINUSE. Sidospår, rört inte Scout-mätningen.

| Kriterium | Poäng /10 | Anteckning |
| --- | --- | --- |
| intentMatch | 8 | Sajten är e-handel, Hero "Shoppa nu" → /produkter, products-grid finns. Andemeningen "liten keramik-shop" är fångad. |
| branchMatch | 8 | scaffold=ecommerce-lite, variant=clean-store (default), starter=commerce-base. Korrekt taxonomy-mappning för ecommerce-kategorin. |
| routeStructure | 8 | 4 routes (`/`, `/produkter`, `/om-oss`, `/kontakt`). Standard ecommerce-lite. |
| copyConcrete | 5 | Hero-, om-oss- och kontakt-copy är konkret + på svenska. Men `/produkter` listar 3 auto-derivat ("Försäljning av keramik", "Säljer vit lera", "Drejar bruksföremål...") som fragment från offer/about — inte konkreta produktnamn med priser. Wizardens products-array fylldes inte i, så detta är inte en regression utan en konsekvens. |
| branchCredibility | 6 | Känns som "generisk shop med keramik-tagline" snarare än "specifikt keramikstudio". Saknar handcraft-känsla, generic icons (Sparkles på alla 3 kort). |
| ctaClarity | 9 | "Shoppa nu" → /produkter (B101 fix). "Hör av dig för att beställa" → /kontakt (B102 fix). "Se alla produkter" → /produkter (sekundär). "Kontakta oss" → /kontakt (bottom-band). Tydliga, konsekventa shop-flöde-CTAs. |
| mobileFirstImpression | n/a | Ingen screenshot av render — preview-iframen trasig pga `http://`-host. Bedöms ej. |
| followUpReadiness | n/a | Case 6. |
| visualPolish | n/a | Ingen rendering testad. clean-store-variantens tokens (#fafafa background, #0a0a0a primary) syns bara via CSS-variabler i koden. |
| conversionClarity | 7 | Hero-CTA tydlig + sekundär "Ring"-knapp + products-grid + bottom-CTA till kontakt. Klar konverteringsväg. Men dummy-telefonnummer "+46 8 000 00 00" syns publikt — kosmetiskt fult även om det inte är produktblocker. |
| **Snitt (n=7 mätbara)** | **~7.3** | |

**Observation:** Keramik-passet håller live. Alla tre B-IDs som passet adresserade är stängda i kod OCH live-output. Två icke-blocker-observationer: (Obs 1) siteId-derivation, (Obs 2) products auto-derivat från offer-text när wizardens products-array är tom.

**B101-verifikation:** ✅ stängd.
- `app/page.tsx:15` — `<a href={"/produkter"} ...>Shoppa nu<ArrowRight ... /></a>`. Hero-CTA-text + path matchar exakt vad `_hero_cta_label(dossier)` + `_hero_cta_target_path(dossier, listing_route, contact_path)` ska producera för shop-variant när scaffold deklarerar `id="products"`.

**B102-verifikation:** ✅ stängd.
- `app/produkter/page.tsx:30` — `<a href={"/kontakt"} ...><ShoppingBag .../>Hör av dig för att beställa<ArrowRight .../></a>`. Verbet är "beställa" (whitelist `_COMMERCE_BOTTOM_CTA_LABELS["sv"] = "Hör av dig för att beställa"`). Inte "Fråga om en beställning". Länk till /kontakt behålls medvetet (ingen checkout i MVP).

**B128-verifikation:** ✅ stängd.
- `app/om-oss/page.tsx:14` — `<p ...>{"Liten studio i Hagsätra som drejar bruksföremål för vardagsbordet"}</p>`. Texten är operatörens egen aboutText från wizarden. Ingen Bygg-/Skapa-/Make-/Build-imperativ. `_customer_safe_planner_note()` + `_starts_with_planner_imperative()`-guards håller — Composer-2.5-bypass-regression (`-Bygg`, `**Bygg`, `1. Bygg`) är inte närvarande.

**Obs 1 (icke-blocker, ej B-ID per operatörsdirektiv):** siteId blir `operatorens-beskrivning-0d1392`, vilket är slugified från `[Operatörens beskrivning]`-headern i `composeMasterPrompt`. companyName ÄR "Atelje Vit Lera" på /om-oss-sidan, så `_derive_company_name` fungerar; det är `slugify_site_id` eller motsvarande som tar fel källa. Förväntat hade varit `atelje-vit-lera-<tail>`. siteId-string hamnar i URL-paths för future hosting, så det är värt framtida granskning men inte produktblocker.

**Obs 2 (icke-blocker, ej B-ID per operatörsdirektiv):** `app/produkter/page.tsx` listar 3 auto-genererade product-kort:
- "Försäljning av keramik" / "Utvalt sortiment med tydlig produktväg och enkel beställning."
- "Säljer vit lera" / samma description.
- "Drejar bruksföremål för vardagsbordet" / samma description.

Operatören fyllde **inte** i wizardens products-array (Steg 3 hoppades effektivt över). Builder/briefModel har då fallit tillbaka till `_product_category_name` som plockar fragment från `offer`/`servicesMentioned`. Inte regression mot keramik-passet, men en kvalitetsbrist: alla 3 har samma generisk description, samma Sparkles-ikon, ingen prisuppgift. Resultat: products-sidan bygger men säger inget konkret. Behöver inte fix per se — om operatören faktiskt fyller in products i Steg 3 (testas i ev. Case 1b eller Case 6 follow-up) så bör de gå hela vägen genom till sidan.

**Källa:** Select-String-output från `app/page.tsx`, `app/produkter/page.tsx`, `Get-Content app/om-oss/page.tsx | Select -First 60`. Skickad av operatör 2026-05-19 12:01 UTC+2 i scout-chatten. Inga visuella screenshots (preview-iframen trasig).

### Case 2 (tjänsteföretag med adress) — KÖRD 2026-05-19 12:15-12:25 UTC+2

**Wizard-input:** companyName=`Frisörsalongen Tussilago`, offer/tagline=`Klipper hår`, kategori=`Salong / Skönhet` (id `salon`), telefon=`08-123 45 67`, email=`kontakt@tussilago.se`, **adress=`Götgatan 12, 11646 Stockholm`** (B120-test), öppettider=`Mån-Fre 09:00-17:00`, services=`Klippning Dam`/`Färgning` (utan description), aboutText skippad, mustHave=6 sidor (`Startsida / Hero`, `Om oss / Om mig`, `Priser och paket`, `Bokning online`, `Bildgalleri`, `Karta / Hitta hit`), CTA tom (testar fallback). Inga assets/toner.

**siteId:** `operatorens-beskrivning-092284` (samma Obs 1-bug som Case 1 — konsistent över caser).
**RunId:** `20260519T101956.601Z-a9f18c8b-operatorens-beskrivning-092284`.
**Build-status:** `ok` (briefSource=real, 104.0s totalt; npm install 40.2s + npm run build 49.0s).
**Project Input** (från `data/prompt-inputs/operatorens-beskrivning-092284.v1.project-input.json`):
- `company.businessType: "hair-salon"` ✅ briefModel-mapping korrekt
- `company.tagline: "Klipper hår"` (operatörens egen text, kort men OK)
- `company.story: "Frisör i Stockholm med tydligt erbjudande, enkel kontaktväg och ett fokuserat nästa steg för besökaren."` (fallback från `_planner_note_or_fallback` — operatören skippade Steg 4)
- `location.city: "Stockholm"`, `location.country: "Sverige"`, `location.serviceAreas: ["Stockholm"]` ✅ **B120-fix verifierad live**
- `services`: 2 från wizarden, descriptions generic-fallback ("Tydlig hjälp med klippning dam och enkel väg vidare.")
- `conversionGoals: ["booking"]` (briefModel auto-derived trots tomt CTA-val)
- `requestedCapabilities: ["booking", "gallery", "map", "contact-form", "online-booking"]` — `online-booking` är duplikat av `booking` (Obs 2)
- `scaffoldId: "local-service-business"`, `variantId: "nordic-trust"` ✅ taxonomy-mapping för salon

**Routes byggda:** `/`, `/tjanster`, `/om-oss`, `/kontakt` (4 st). **Routes som operatören önskat men INTE byggda:** `/priser`, `/galleri`, `/karta`, `/bokning` (Obs 3 — Page Intent-fynd, se nedan).

| Kriterium | Poäng /10 | Anteckning |
| --- | --- | --- |
| intentMatch | 8 | Frisör + Stockholm + boknings-CTA. Andemeningen fångad. Hero "Frisörsalongen Tussilago" + Stockholm-tag + Boka tid + Ring. |
| branchMatch | 8 | scaffold=local-service-business, variant=nordic-trust, starter=marketing-base. Salon-taxonomy-mapping korrekt. businessType="hair-salon" extraherat. |
| routeStructure | 6 | 4 routes byggda men 6 önskade. Mismatch på `/priser`, `/galleri`, `/karta`, `/bokning`. Builder bygger scaffoldens hardcoded routes — wizardens mustHave-array går bara till capabilities, inga extra routes. **Page Intent saknas helt.** |
| copyConcrete | 7 | companyName + city + telefon + email korrekt och från wizarden. Wizardens services-array kom igenom till `/tjanster` (stor förbättring mot Case 1). Service-descriptions generic-fallback eftersom operatör skippade description-fält. Story fallback eftersom Steg 4 skippades — men customer-safe (B128 håller även där). |
| branchCredibility | 6 | Generic Sparkles-icon på alla service-cards. nordic-trust-variantens neutralt-skandinaviska känsla är OK för frisör men inte super-typisk salong. Saknar foto/galleri trots att operatören valt "Bildgalleri" i Steg 5 (route byggdes inte). |
| ctaClarity | 9 | "Boka tid" → /kontakt (Hero + /tjanster bottom — konsekvent boknings-flöde). "Ring 08-123 45 67" → tel:08-1234567 (verklig telefon, inte dummy som Case 1 hade). "Kontakta oss" → /kontakt (generic bottom-band). |
| mobileFirstImpression | n/a | Ingen rendering testad — kvar fram tills slut-spurt. |
| followUpReadiness | n/a | Case 6. |
| visualPolish | n/a | Ingen rendering. |
| conversionClarity | 8 | Hero-CTA + sekundär ring + service-grid + bottom-CTA till kontakt. Tydligt boknings-flöde. Telefonnummer som klickbar tel:-länk är ett bra mobile-friendly val. |
| **Snitt (n=7 mätbara)** | **~7.4** | Något bättre än Case 1 (~7.3). |

**B119-status:** ej skuggat ännu (kräver scrape — Case 3).

**B120-verifikation:** ✅ stängd live.
- `_apply_location_from_address` regex matchar `Götgatan 12, 11646 Stockholm` → `location.city = "Stockholm"`. Renderas både på Hero och /om-oss.

**B128-verifikation (sekundär — fallback-fall):** ✅ håller.
- Story-text `"Frisör i Stockholm med tydligt erbjudande..."` är fallback från `_planner_note_or_fallback` eftersom operatör skippade Steg 4 (aboutText). Texten är `_company_business_label("hair-salon", "sv")` + city + customer-safe boilerplate. Ingen Bygg-/Skapa-imperativ. Bekräftar att B128:s fallback-bana också är ren.

**Hero-CTA-fallback för tom CTA-val:** ✅ håller.
- Operatören valde inget CTA-chip i Steg 5. `_apply_cta_field` returnerar utan att skriva conversionGoals (operatör-input tomt). Men briefModel hade redan returnerat `conversionGoals: ["booking"]` baserat på master-prompten. `_hero_cta_variant` matchar conversionGoals → booking-variant → "Boka tid" + /kontakt-target. Konsistent och förväntat utfall för en frisörsalong.

**Obs 1 (icke-blocker) — siteId-bug konsistent:** Bekräftar Case 1:s observation. siteId-derivation tar fortfarande `[Operatörens beskrivning]`-headern istället för `company.name`. Konsistent buggbeteende — inte case-specifikt. Förslag: när buggen registreras som B-ID, fix:en är att `slugify_site_id` (eller motsvarande helper) preferar `company.name` om den finns.

**Obs 2 (icke-blocker) — `requestedCapabilities` har semantisk duplikat:** `booking` (från `_PAGE_TO_CAPABILITY["Bokning online"]`) och `online-booking` (från briefModels egen capability-extraction) är båda listade. Resolverns dedup-logik fångar bara exakt string-match. Skapar en `capability-unknown` fallbackWarning på `online-booking` (slug saknas i `capability-map.v1.json`). Inte produktblocker men brus i Doctor-output.

**Obs 3 (icke-blocker) — Page Intent gap bekräftat (Case 5 gratis):** Wizardens mustHave-array går till `requestedCapabilities` (gallery, map, booking, etc.) men **bygger inga extra routes**. Scaffolden `local-service-business` har 4 hardcoded routes (`/`, `/tjanster`, `/om-oss`, `/kontakt`) och builder ignorerar mustHave för route-emission. Ingen warning, ingen mismatch-signal — operatören får tyst en mindre sajt än hen valde i wizarden. **Detta är samma fynd som Case 5 ("2 sidor"-case) skulle testa**, så vi har redan svaret: Page Intent är en gap som skulle behöva fix om småföretagarens sidantal-önskan ska respekteras.

**Källa:** Shell-output 2026-05-19 12:24-12:30 UTC+2: PI sidecar (`data/prompt-inputs/operatorens-beskrivning-092284.v1.project-input.json`), generated TSX (`..\sajtbyggaren-output\.generated\operatorens-beskrivning-092284\app\{page,om-oss/page,tjanster/page}.tsx`).

### Case 3a (1753skincare som prompt-build UTAN scrape) — KÖRD 2026-05-19 12:44 UTC+2

**Wizard-input:** rawPrompt=`En ny sajt för ett företag inom hud och hälsa`, companyName=`1753skincare`, offer=`Säljer krämer`, existingSite=`https://www.1753skincare.com` **(Hämta-knappen klickades INTE — scrape-runnern kördes aldrig, verifierat via terminal: bara `POST /api/prompt`, ingen `POST /api/scrape-site`)**, kontakt-fält tomma, kategori=`Webshop / E-handel`, mustHave=5 sidor (Startsida/Hero, Om oss/Om mig, Kontaktformulär, FAQ, Webshop/Produkter), CTA tom.

**siteId:** `operatorens-beskrivning-574c13` (Obs 1, tredje gången — konsistent).
**RunId:** `20260519T104436.322Z-c792194e-operatorens-beskrivning-574c13`.
**Build-status:** `ok` (briefSource=real, 2.0 min totalt — längre än Case 1+2 pga LLM-call på obekant företag).

**Project Input** (från sidecar):
- `company.name: "1753skincare"` (wizard) ✅
- `company.businessType: "ecommerce"` (briefModel) ✅
- `company.tagline: "Säljer krämer"` (wizard)
- `company.story: "Webbshop med tydligt erbjudande..."` (fallback — ingen aboutText från operatör)
- `contact.phone: "+46 8 000 00 00"` (DUMMY — fynd 1)
- `contact.email: "kontakt@example.se"` (DUMMY)
- `contact.addressLines: ["Adress lämnas på förfrågan"]` (B88-fallback)
- `location.city: "Sverige"`, `location.country: "Sverige"` (country-only — `_location_is_country_only` triggar Hero-suppress, ✅ B95/B98 håller)
- `services`: 1 entry (`saljer-kramer` — bara 1 service-card på /produkter)
- `conversionGoals: ["purchase", "contact-form-submission"]` (briefModel auto-derived)
- `requestedCapabilities: ["contact-form", "faq", "ecommerce", "payments", "webshop"]` — `ecommerce` + `webshop` är semantisk duplikat (B131-bekräftelse)
- `scaffoldId: "ecommerce-lite"`, `variantId: "clean-store"` ✅

**Routes byggda:** `/`, `/produkter`, `/om-oss`, `/kontakt` (4 st). **Önskat men ej byggt:** `/faq` (Obs 3 / B132-bekräftelse).
**fallbackWarnings i discoveryDecision:** 5 stycken (`capability-gap` × 2 på `contact-form` + `payments`, `capability-unknown` × 3 på `faq` + `ecommerce` + `webshop`).

| Kriterium | Poäng /10 | Anteckning |
| --- | --- | --- |
| intentMatch | 6 | Branch korrekt (e-handel) men 1753skincare-DNA saknas helt — scrape kördes aldrig så briefModel hade bara prompt + wizard-fragment att gå på. "krämer" är inte 1753skincare's faktiska sortiment (de säljer CBD-baserad hudvård). |
| branchMatch | 8 | scaffold=ecommerce-lite, variant=clean-store, starter=commerce-base. Korrekt ecommerce-mapping. |
| routeStructure | 7 | 4 routes byggda, FAQ-page önskad i wizard men inte i scaffold-defaults. **Page Intent gap (Obs 3) bekräftat 3:e gången.** |
| copyConcrete | 4 | Hero har companyName + tagline OK. Men: bara 1 service-card "Säljer krämer" på /produkter, story är generic fallback, **alla contact-fält är dummy-fallback** (kontakt-sidan visar +46 8 000 00 00, kontakt@example.se, "Adress lämnas på förfrågan"). |
| branchCredibility | 5 | Generic shop-känsla. Ingen skincare-DNA, inga produktnamn, inga priser. Confusion-risk: sajten ser "klar att leverera" ut men data är dummy. |
| ctaClarity | 9 | Shoppa nu → /produkter, Hör av dig för att beställa → /kontakt, Ring → tel:+4680000000 (dummy). CTA-flödet är konsekvent (B101+B102 håller). |
| mobileFirstImpression | n/a | Ingen rendering testad. |
| followUpReadiness | n/a | Case 6. |
| visualPolish | n/a | Ingen rendering. |
| conversionClarity | 7 | Hero-CTA + ring-CTA + bottom-CTA. Tydligt flöde, men dummy-telefon på Hero-sekundär drar ner credibility. |
| **Snitt (n=7 mätbara)** | **~6.6** | Lägre än Case 1 (~7.3) + Case 2 (~7.4) pga dummy contact + svag products-listning. |

**Verifierat live (B-IDs som passet adresserade):**
- ✅ B101 stängd (Hero-CTA `Shoppa nu` → `/produkter`).
- ✅ B102 stängd (`/produkter` bottom-CTA `Hör av dig för att beställa`).
- ✅ B128 stängd (även i fallback-fall).
- ✅ B95/B98 country-only-suppress håller (Hero har ingen "Sverige"-tag trots `location.city = "Sverige"`).

**Fynd 1 — dummy contact-data renderas publikt** (möjligt B-ID-kandidat, ej registrerat per direktiv). Operatör som inte fyller kontaktfält OCH inte kör scrape får en sajt med `+46 8 000 00 00` på Hero + `/kontakt`-sidan. Inte regression (B88 designade fallback-värdena), men confusion-risk eftersom sajten kommunicerar "aktivt företag" med dummy-data.

**Fynd 2 — B131-bekräftelse starkare** — `requestedCapabilities` har 5 entries varav 2 är capability-gap, 3 är capability-unknown. Plus `ecommerce` + `webshop` är semantisk duplikat — exakt det B131 ska fixa.

**Fynd 3 — Obs 1 / B130 bekräftat 3:e gången** — siteId `operatorens-beskrivning-574c13` även när companyName är "1753skincare".

**Fynd 4 — Obs 3 / B132 bekräftat 3:e gången** — wizard-mustHave `FAQ` byggde inte `/faq`-route, ingen warning.

**Källa:** Shell-output 2026-05-19 12:46 UTC+2: PI sidecar (`data/prompt-inputs/operatorens-beskrivning-574c13.v1.project-input.json`), meta sidecar (full discoveryDecision + originalPrompt), generated TSX (`..\sajtbyggaren-output\.generated\operatorens-beskrivning-574c13\app\{page,om-oss/page,produkter/page,kontakt/page}.tsx`).

**Scope-status:** Case 3a är **prompt-build**, inte scrape-test. B113/B118/B119 förblir oprövade i overlay-flödet. Optional Case 3b med riktig `Hämta`-klick kan följa om operatören vill skugga scrape-runner-kedjan.

### Case 3b (1753skincare med riktig scrape) — _ej körd ännu, valfri_

_Skuggar B113 (SSRF-redirect), B118 (scrape SIGKILL), B119 (email-kvalitet) live om operatören kör._

### Case 4 (sköldpaddssoppa / conflict) — _ej körd ännu_

_Mall som ovan._

### Case 5 ("2 sidor") — _ej körd ännu_

_Mall som ovan._

### Case 6 (follow-up) — _ej körd ännu_

_Mall som ovan._

## Topp 5 hinder (regression vs nytt fynd)

_Ifylls efter att caseen körts. Format per hinder: `{B-ID eller "ny"} | {regression|nytt fynd} | {kort beskrivning} | {prio}`._

## Builder-prio i ordning

_Ifylls efter att caseen körts. Tre kandidatspår identifierade pre-scout:_

1. **Intent Guard** — om Case 4 visar att fri prompt och wizard kan motsäga varandra utan signal. Modell-nivå: 6/10 (medel insats — ny guard-modul plus testfall).
2. **Page Intent** — om Case 5 visar att operatörs sidantal ignoreras tyst. Modell-nivå: 7/10 (medelhög — kräver scaffold-frigjord plan-helper eller routes.json-override).
3. **B119/B120 contact-data hardening** — om Case 2 eller 3 visar fel city eller alfabetisk email. Modell-nivå: 4/10 (låg — riktade regex-/scoring-fix).
4. **Variant/style-selection** (PR #38-spår) — kvarstår parkerat per coach-direktiv tills variant-promotion-sprint körs.
5. **Project DNA / semantic follow-up** — endast om totalsnitt ≥7/10 och inget case <6.5.
6. **Specifik B-ID-fix** (t.ex. B71 unverified) — om Case 6 visar regression.

## Bug-ID:n som bör öppnas

_Ifylls efter att caseen körts. Föreslås av Scout — registreras formellt av Builder/Steward._

## Verdict mot beslutsregel

_Ifylls efter att caseen körts._

- ≥7/10 OCH inget case <6.5 → **Project DNA-sprint** (Queue #5).
- Annars → **riktad bug-sweep** på det case som dröjer.

## Färdig copy-paste Builder-prompt för rekommenderat nästa steg

_Ifylls efter att caseen körts. Smal prompt — ett B-ID eller ett spår, tydligt scope, modell-nivå-rekommendation._

---

## Operatör-instruktioner — Case 1 (KERAMIK)

Det här är instruktionerna Scout skickade live till operatören för Case 1. Sparas i rapporten för spårbarhet.

### 0. Pre-flight (gör en gång innan första caset)

1. Öppna PowerShell i repo-roten (`C:\Users\jakem\Desktop\sajtbyggaren`).
2. Verifiera att `apps/viewser/.env.local` finns och innehåller `OPENAI_API_KEY=sk-...`. Om filen saknas: kopiera från `.env.example` och lägg till nyckeln.
3. Verifiera att port 3000 är ledig:
   ```powershell
   Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
   ```
   Om något lyssnar: stäng den processen eller starta Viewser med `-Port 3001`.
4. Se till att `mkcert`-certen för `-Https`-flaggan finns. Första gången måste du köra `mkcert -install` följt av `mkcert localhost 127.0.0.1 ::1` i `apps/viewser/`-mappen. Om certet saknas och du inte vill installera mkcert just nu: använd `http://`-fallback enligt steg 1b nedan, men då fungerar inte StackBlitz-preview (bara Run Details + lokal `npm run build`).

### 1. Starta dev-servern

**Med HTTPS (rekommenderat — krävs för StackBlitz embed):**

```powershell
.\scripts\dev-viewser.ps1 -Https
```

**Utan HTTPS (preview funkar inte men resten av flödet kan testas):**

```powershell
.\scripts\dev-viewser.ps1
```

Vänta tills terminalen säger `▲ Next.js 16.x.y - Local: https://localhost:3000`. Det tar 10-30 sek första gången.

### 2. Öppna Viewser i Chrome (Edge/Brave/Vivaldi funkar också, **inte** Safari/Firefox för preview)

Gå till `https://localhost:3000` (eller `http://localhost:3000` om du körde utan -Https). Acceptera cert-varningen om Chrome klagar (`mkcert`-cert är self-signed).

### 3. Kör Case 1 — KERAMIK E-HANDEL

3a. **Klicka i prompt-fältet** längst ner och skriv:
```
Liten e-handel på svenska för försäljning av keramik med fokus på köpkonvertering
```
Tryck **Enter** (eller klicka pilknappen). DiscoveryWizarden ska öppnas.

3b. **Steg 1 — Företag:**
- Företagsnamn: `Atelje Vit Lera` (eller välj eget — inte viktigt för B-ID-verifikation).
- Beskrivning: din originalprompt ska redan stå där; lämna oförändrad.
- Telefon/E-post/Adress: lämna tomt (vi testar fel-fri keramik-baseline här, inte adress-extraktion).

Klicka **Fortsätt**.

3c. **Steg 2 — Kategori:**
- Klicka chip:en **`Webshop / E-handel`** (id `ecommerce`).
- Verifiera att en gulorange notice INTE dyker upp (ecommerce är `active` i taxonomi, så inget fallback-meddelande).

Klicka **Fortsätt**.

3d. **Steg 3 — Innehåll (e-handel-gren):**
- Lägg till minst 1-2 produkter:
  - Namn: `Stengods-mugg`, pris: `280 kr`.
  - Namn: `Vas i seladon`, pris: `750 kr`.
- Du kan hoppa över USP/prisnivå.

Klicka **Fortsätt**.

3e. **Steg 4 — Story:**
- Skriv en kort om-text (svensk, INGEN imperativ): `Liten studio i Hagsätra som drejar bruksföremål för vardagsbordet — varje pjäs är unik.`
- Lämna Historia/Vision/Kontakt-intro tomt.

Klicka **Fortsätt**.

3f. **Steg 5 — Sidor och CTA:**
- Verifiera att de fem rekommenderade chip:sen är förvalda: `Startsida / Hero`, `Webshop / Produkter`, `Om oss / Om mig`, `FAQ`, `Kontaktformulär`. Om så inte är fallet, klicka i dem.
- Primär CTA: klicka chip:en **`Köp nu`**.
- Målgrupp: lämna tomt.

Klicka **Fortsätt**.

3g. **Steg 6 — Bilder:** klicka **Hoppa över**.

3h. **Steg 7 — Ton:** klicka **Hoppa över**.

3i. **Klicka "Skapa sajt →"**.

3j. **Vänta**. Du ska se en BuildProgressCard mitt på skärmen som visar "thinking" → "building" → resultat. Total tid 30-90 sek (briefModel + npm install + npm run build).

### 4. Verifiera utfallet

4a. **Vänta på `Build klar`** (grön strip) eller `Build klar med varning` (orange) eller `Build misslyckades` (röd) längst ner.

4b. **Öppna ConsoleDrawer (om den finns synlig — annars dra upp den från botten).** Notera ev. fel.

4c. **Klicka på preview** (StackBlitz embed eller länken till Run Details).

4d. **Skicka tillbaka till Scout:**

   1. **Build-ID** (kort string, t.ex. `atelje-vit-lera-2026-05-19-abc123` eller liknande). Det syns i strip:en ovanför prompten OCH i Run History-listan till höger.
   2. **Site-ID** (t.ex. `atelje-vit-lera`).
   3. **Status från strip:** ok / degraded / failed.
   4. **Screenshot av Hero på `/`** (förstasidan i preview). Vi vill se Hero-CTA-knappens **text** OCH att hovra över knappen visar dess `href` (eller skicka HTML från Run Details/files-vyn).
   5. **Screenshot av `/produkter`** (klicka "Shoppa nu"-knappen i Hero — det ska ta dig till `/produkter`. Om det tar dig till `/kontakt` är det en B101-regression). Visa botten av `/produkter`-sidan så vi ser bottom-CTA-texten.
   6. **Screenshot av `/om-oss`**. Visa hela "Om oss"-paragrafen.
   7. **Eventuell felmeddelande från ConsoleDrawer.**
   8. **Sökväg till `data/runs/<runId>/`** så Scout kan läsa `build-result.json` + `site-plan.json` + `input.json`. Eller skicka filerna direkt via t.ex. `cat data/runs/<runId>/site-plan.json` i PowerShell.

4e. **Om bygget kraschar:** skicka stack trace + senaste loggade build-fas från ConsoleDrawer eller terminal.

### 5. Stop & wait

Skicka tillbaka steg 4d-resultatet till Scout. Vi går igenom det innan vi tar Case 2. Om något i 4d är konstigt eller missvisande, säg till så ger Scout follow-up-frågor eller testar samma case igen.

---

## Operatör-instruktioner — Case 2-6

_Skickas efter att Case 1 är godkänt och ev. blockers från det är hanterade._

---

## Spår B — Variant-experiment (körs efter Case 1-6)

PR #38 lyfte in 8 nya canonical Scaffold Variants:

- **`local-service-business/variants/`:** `nordic-trust` (default), `clinical-calm`, `midnight-counsel`, `pulse-fit`, `warm-craft`.
- **`ecommerce-lite/variants/`:** `clean-store` (default), `earth-wellness`, `mono-tech`, `noir-editorial`, `street-vivid`.

Alla är `enabled: true`, schema-valida, men **inaktiverade i prod** av `_DEFAULT_VARIANT_BY_SCAFFOLD`-guarden. För Spår B testar vi 2 av dem som visuell jämförelse mot defaults — inte som del av Scout-poängsättningen för Case 1-6.

### Metod (säkrast för Scout-disciplin)

Vi rör **inte** `packages/generation/planning/plan.py` (Scout-off-limits). Istället:

1. Identifiera Project Input-filen från en avslutad Case 1- eller Case 2-build (PI = Project Input, dvs `data/prompt-inputs/<siteId>.v1.project-input.json`).
2. Kopiera den till en ny fil med variant-suffix.
3. Editera `variantId`-fältet i kopian.
4. Bygg om via `python scripts/build_site.py --dossier <kopia-path>`.
5. Visuell jämförelse mot Case 1- eller Case 2-baseline (samma input, olika variant).

Inget LLM-anrop görs i steg 4 (briefModel kördes i Case 1/2; planning är pinned eftersom PI redan har `scaffoldId`/`variantId`). Båda experimenten klar på ~30 sek per build.

### Experiment B1 — keramik med earth-wellness

**Förutsättning:** Case 1 är klart med build-status `ok`.

**Vald variant:** `earth-wellness` (ecommerce-lite).
- **Visuell signatur:** background `#f4f1e8` (varm vit), primary `#5f7d52` (olivgrön), accent `#b98f63` (terracotta), rounded `0.875rem` corners, motion `subtle`.
- **Förväntad kontrast mot `clean-store`:** organiskt + jordfärg + rundare hörn istället för minimal-modern shop-känsla.

**Steg:**

```powershell
# 1. Hitta Case 1 PI (siteId från strip:en eller Run History)
$siteId = "atelje-vit-lera"   # byt till faktiskt siteId
$baseline = "data/prompt-inputs/$siteId.v1.project-input.json"
$variant = "data/prompt-inputs/$siteId-earth-wellness.v1.project-input.json"

# 2. Kopiera + edita variantId i kopian
Copy-Item $baseline $variant
# Öppna $variant i editor (notepad eller Cursor), byt:
#   "variantId": "clean-store"
# till:
#   "variantId": "earth-wellness"
# Spara.

# 3. Bygg om från kopian
python scripts/build_site.py --dossier $variant
```

**Rapportera tillbaka:**

1. Build-ID (annorlunda än Case 1 — det är ny run).
2. Status (förväntat: `ok` — earth-wellness är schema-valid, scaffold = ecommerce-lite oförändrat, samma routes som Case 1).
3. Screenshot av Hero `/` jämförd mot Case 1 Hero. Visa både gamla och nya screenshots sida-vid-sida om möjligt.
4. Screenshot av `/produkter`.
5. **Subjektiv kommentar:** känns det mer keramik/handcraft-passande? Hur stor är skillnaden visuellt? Skala 1-10 där 1 = "ser identisk ut" och 10 = "uppenbart annan sajt".

### Experiment B2 — tjänsteföretag med warm-craft

**Förutsättning:** Case 2 är klart med build-status `ok`.

**Vald variant:** `warm-craft` (local-service-business).
- **Visuell signatur:** background `#f6f1e8` (krämvit), primary `#7a4b2f` (varm brun), accent `#b98a52` (mässing), `scaleRatio: 1.23` (tightare typografi).
- **Förväntad kontrast mot `nordic-trust`:** varm hantverkare istället för skandinavisk professionell-neutral.

**Steg:** identisk procedur som B1, men med Case 2:s siteId och `"variantId": "nordic-trust"` → `"warm-craft"`.

**Rapportera tillbaka:** samma fyra punkter som B1 + skala 1-10.

### Vad Spår B besvarar

- Är de 8 nya varianterna visuellt distinkta från defaults? (Om båda B1 och B2 ger ≤3/10 är variant-skapandet underdimensionerat — fynd för PR #38-uppföljning.)
- Är de produktmässigt rimliga för småföretagskunder? (Subjektiv operatörsbedömning.)
- Påverkas build-status / quality-gate negativt av variant-bytet? (Förväntat: nej, men loggas om så är fallet.)

Resultat skrivs in i en **Bilaga B** sektion i rapporten när experimenten är klara. Inte del av Case 1-6-snittet.

### Vad Spår B INTE besvarar

- Hur variant-selection-logiken ska se ut (taxonomy-edit, dossier-rationale, wizard-val, operator-pin) — det är variant-promotion-sprintens jobb.
- Hela ekosystemets bredd (8 varianter × ~20 case = 160 kombos) — Scout testar 2.
- B129-skuldens prioritet — registrerad men inte argumenterad här.

