# data/starters/

Körbara basprojekt som scaffolds patchas ovanpå. Varje starter är en självständig Next.js-app med uppfyllda hårda krav (Next.js 16, TypeScript strict, Tailwind 4, shadcn/ui, npm, ESLint+Prettier).

Reviewerns rekommendation: **fem starters täcker våra 14 scaffolds**. Se ADR 0011 för varför scaffold-registret är ärvt arbetsmaterial.

## Starters

| ID | Roll | Källa | Status |
|----|------|-------|--------|
| `marketing-base` | 9 av 14 scaffolds (local-service-business, professional-services, restaurant-hospitality, clinic-healthcare, real-estate, nonprofit-community, event-campaign, app-landing, consultant-expert) | Egen bas via `create-next-app` + `shadcn init` | Klar, build verifierad |
| `saas-base` | `saas-product` | Fork av [vercel/platforms](https://github.com/vercel/platforms) | Mapp finns, kod saknas |
| `commerce-base` | `ecommerce-lite` | Fork av [vercel/commerce](https://github.com/vercel/commerce) | Vendor-import klar (2026-05-11, upstream `1df2cf6`); bygger lokalt; runtime-mapping aktiverad i B20 step 2 (kör genom `deterministic-v1` codegen tills real-codegen-scope utvidgas) |
| `portfolio-base` | `portfolio-creator` | Fork av [vercel/examples → solutions/blog](https://github.com/vercel/examples/tree/main/solutions/blog) | Vendor-import klar (2026-05-14, upstream `72aaac1`); bygger lokalt; runtime-mapping aktiveras inte i denna PR. `agency-studio` mappades ursprungligen hit men flyttades till `marketing-base` 2026-05-25 när Path B-aktiveringen landade — section-driven dispatch klarar agency-strukturen utan att byta starter, så ingen vendor-runtime krävs förrän en framtida portfolio-creator-aktivering tar tillbaka portfolio-base. |
| `docs-base` | `course-education` | Fork av [shuding/nextra](https://github.com/shuding/nextra) | Vendor-import klar (2026-05-14, upstream `36ba79c`); bygger lokalt; runtime-mapping aktiveras inte i denna PR |

## Scaffold → Starter routing (målbild)

Den här listan är målbilden för vilken Starter respektive Scaffold ska köra på
när varje starter är aktiverad. Aktiv runtime styrs fortfarande av
`packages/generation/planning/plan.py:SCAFFOLD_TO_STARTER`, som MÅSTE vara en
delmängd av (och konsistent med) listan nedan. I nuläget är `portfolio-base`
harmoniserad som starter-underlag, men `portfolio-creator` och `agency-studio`
är inte aktiverade i runtime-mappningen. Drift fångas av
`tests/test_starter_scaffold_mapping.py`.

Format: en rad per scaffold med exakt en mål-starter. Om aktiv runtime avviker
från målbilden ska det framgå i status-/handoff-dokumenten eller via B-ID i
`docs/known-issues.md`, så review kan skilja avsedd vänteläge från regression.

<!-- scaffold-starter-mapping:start -->
- local-service-business: marketing-base
- professional-services: marketing-base
- restaurant-hospitality: marketing-base
- clinic-healthcare: marketing-base
- real-estate: marketing-base
- nonprofit-community: marketing-base
- event-campaign: marketing-base
- app-landing: marketing-base
- consultant-expert: marketing-base
- ecommerce-lite: commerce-base
- saas-product: saas-base
- portfolio-creator: portfolio-base
- agency-studio: marketing-base
- course-education: docs-base
<!-- scaffold-starter-mapping:end -->

## Hårda krav per starter

Efter fork eller setup ska följande gälla:

- Next.js 16 (`package.json:dependencies.next` minst `^16.0.0`)
- TypeScript strict (`tsconfig.json:compilerOptions.strict: true`)
- Tailwind 4 (`package.json:devDependencies.tailwindcss` minst `^4.0.0`)
- shadcn/ui initialiserat (`components.json` finns i roten)
- npm-lockfil (`package-lock.json`, inte `pnpm-lock.yaml` eller `yarn.lock`)
- ESLint flat config + Prettier
- `npm run dev`, `npm run build`, `npm run start` ska finnas i `package.json:scripts`
- Tom eller minimal `.env.example`, **aldrig** `.env`
- **Inget** av: auth, databas, betalningar, CMS-koppling, analytics, hårdkodad copy, hårdkodade färger, hårdkodade CTA-länkar

Auth/databas/betalningar/CMS-integrationer hör hemma i `hard` Dossier, inte i starter.

## Hur en starter används vid generation

```
Project Input (Deep Brief)
   ↓
Plan väljer starterId (t.ex. "marketing-base")
   ↓
Engine kopierar data/starters/marketing-base/ → tmp-projekt
   ↓
Scaffold injicerar routes och sektioner
   ↓
Variant injicerar CSS-tokens
   ↓
Project Input tillför copy/bilder/site-data
   ↓
Dossiers (soft / hard) kopplas på där de är kompatibla
   ↓
Verify → Repair → Preview → Release
```

## Säkerhet och versioning

- Lockfiler (`package-lock.json`) committas alltid
- `.env.example` committas, `.env` ignoreras via `.gitignore`
- Stora binär-assets (bilder, fonter) hör inte hit - lägg dem i scaffold eller dossier
- När en starter uppgraderas: ny ADR + uppdatera "Status"-kolumnen ovan

## Roller och städning

Varje starter:
1. Klonas eller skapas i `data/starters/<id>/`
2. Harmoniseras till våra hårda krav (det är ofta huvudarbetet vid fork)
3. Testas: `cd data/starters/<id> && npm install && npm run build` ska gå igenom
4. Dokumenteras i sin egen `README.md` med vad som ändrats från originalet

## Vad agenten får göra autonomt

- Skapa/uppdatera `data/starters/<id>/README.md`
- Köra `npm install`, `npm run build`, `npm run dev` i en starter
- Föreslå uppgraderingar via ADR

## Vad agenten inte gör autonomt

- Lägga till nya beroenden i en starter (kräver operatör-godkännande)
- Byta starter-källa (kräver ADR)
- Pusha en starter till en separat repo (kräver operatör)
