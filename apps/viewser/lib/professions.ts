/**
 * Yrkesregister för marknadssajten. Delad källa för bildväggen på startsidan
 * (P2/P3) och de per-yrke-landningssidorna (P4, /for/[yrke]).
 *
 * - slug: ASCII (inga åäö) = bildens filstam, används i URL:en /for/[slug].
 *   "cykelreperator" behålls som slug (matchar filnamnet) men visas som
 *   "Cykelreparatör".
 * - image: serveras från apps/viewser/public/Bilder/<slug>.webp
 *   (genererad av scripts/optimize-images.mjs).
 * - displayName: svenskt visningsnamn.
 * - headline/pitch: känslomässig, bransch-specifik copy för landningssidan.
 * - family/category: speglar BUSINESS_FAMILIES / WIZARD_CATEGORIES i
 *   discovery-wizard/wizard-constants.ts. Driver "starter"-handoffen så att
 *   knappen "Bygg din sida" landar i DiscoveryWizarden FÖRIFYLLD med rätt
 *   verksamhet i stället för en tom studio (se lib/init-prompt-handoff.ts).
 * - promptSeed: naturlig svensk start-mening som förifyller wizardens
 *   "Vad gör ni?"-fält.
 */
import type {
  BusinessFamilyId,
  WizardCategoryId,
} from "@/components/discovery-wizard/wizard-constants";

export type Profession = {
  slug: string;
  image: string;
  displayName: string;
  headline: string;
  pitch: string;
  family: BusinessFamilyId;
  category: WizardCategoryId;
  promptSeed: string;
};

export const PROFESSIONS: ReadonlyArray<Profession> = [
  {
    slug: "bilmekaniker",
    image: "/Bilder/bilmekaniker.webp",
    displayName: "Bilverkstad",
    headline: "Verkstaden kunderna litar på — online.",
    pitch:
      "Dina kunder googlar “bilverkstad nära mig” redan vid frukosten. Ge dem en sida som visar tider, tjänster och vägen in — innan de ringer någon annan.",
    family: "service",
    category: "auto",
    promptSeed:
      "Jag driver en bilverkstad och vill ha en hemsida med tjänster, öppettider och hur man bokar tid.",
  },
  {
    slug: "frisorsalong",
    image: "/Bilder/frisorsalong.webp",
    displayName: "Frisörsalong",
    headline: "En fullbokad kalender börjar med en snygg sida.",
    pitch:
      "Visa stilen, teamet och hur man bokar. En ren, personlig sida som får nya kunder att vilja sätta sig i just din stol.",
    family: "health",
    category: "salon",
    promptSeed:
      "Jag driver en frisörsalong och vill ha en hemsida som visar stil, team och hur man bokar tid.",
  },
  {
    slug: "bageri",
    image: "/Bilder/bageri.webp",
    displayName: "Bageri",
    headline: "Doften kan vi inte ladda upp — allt annat fixar vi.",
    pitch:
      "Surdeg, öppettider och dagens bröd, vackert presenterat. Låt grannskapet hitta er innan brödet tar slut.",
    family: "restaurant",
    category: "restaurant",
    promptSeed:
      "Vi är ett bageri och vill ha en hemsida med sortiment, öppettider och var man hittar oss.",
  },
  {
    slug: "blomsterhandel",
    image: "/Bilder/blomsterhandel.webp",
    displayName: "Blomsterhandel",
    headline: "Buketter förtjänar mer än ett skyltfönster.",
    pitch:
      "Visa dina arrangemang och gör det lätt att beställa till bröllop, begravning eller bara för att. En sida lika omsorgsfull som dina buketter.",
    family: "ecommerce",
    category: "ecommerce",
    promptSeed:
      "Jag driver en blomsterhandel och vill ha en hemsida där man kan se arrangemang och beställa buketter.",
  },
  {
    slug: "snickare",
    image: "/Bilder/snickare.webp",
    displayName: "Snickare",
    headline: "Hantverket talar — låt sidan göra det också.",
    pitch:
      "Bilder på färdiga projekt säger mer än tusen offerter. Ge kunderna ett enkelt sätt att se vad du kan och höra av sig.",
    family: "construction",
    category: "construction",
    promptSeed:
      "Jag är snickare och vill ha en hemsida med referensprojekt, tjänster och offertförfrågan.",
  },
  {
    slug: "tandlakare",
    image: "/Bilder/tandlakare.webp",
    displayName: "Tandläkare",
    headline: "Trygghet börjar innan patienten kliver in.",
    pitch:
      "En lugn, professionell sida med tjänster, team och tidsbokning. Få nya patienter att känna sig trygga redan vid första klicket.",
    family: "health",
    category: "healthcare",
    promptSeed:
      "Vi är en tandläkarmottagning och vill ha en trygg hemsida med tjänster, team och tidsbokning.",
  },
  {
    slug: "yogastudio",
    image: "/Bilder/yogastudio.webp",
    displayName: "Yogastudio",
    headline: "Hitta lugnet — och nya elever.",
    pitch:
      "Schema, pass och känslan i studion på en stillsam, vacker sida. Låt nya elever andas ut redan innan första passet.",
    family: "health",
    category: "fitness",
    promptSeed:
      "Jag driver en yogastudio och vill ha en hemsida med schema, pass och hur man bokar.",
  },
  {
    slug: "keramik",
    image: "/Bilder/keramik.webp",
    displayName: "Keramikstudio",
    headline: "Varje pjäs är unik. Din sida borde också vara det.",
    pitch:
      "Visa dina verk, kurser och beställningar i en galleri-ren sida. Gör det lätt för samlare och nyfikna att hitta dig.",
    family: "creative",
    category: "portfolio",
    promptSeed:
      "Jag har en keramikstudio och vill ha en galleri-ren hemsida med mina verk, kurser och beställningar.",
  },
  {
    slug: "bygg",
    image: "/Bilder/bygg.webp",
    displayName: "Byggfirma",
    headline: "Bygg förtroende innan första spadtaget.",
    pitch:
      "Referensprojekt, tjänster och kontakt — tydligt och proffsigt. Den kund som ser att ni levererar hör av sig först.",
    family: "construction",
    category: "construction",
    promptSeed:
      "Vi är en byggfirma och vill ha en hemsida med referensprojekt, tjänster och offertförfrågan.",
  },
  {
    slug: "hundvard",
    image: "/Bilder/hundvard.webp",
    displayName: "Hundvård",
    headline: "Viftande svansar börjar med en bokning.",
    pitch:
      "Trim, dagis eller pensionat — visa tjänsterna och gör det enkelt att boka. En varm, tydlig sida som både matte och husse litar på.",
    family: "service",
    category: "business",
    promptSeed:
      "Jag driver en hundvårdsverksamhet och vill ha en hemsida med tjänster och hur man bokar.",
  },
  {
    slug: "cykelreperator",
    image: "/Bilder/cykelreperator.webp",
    displayName: "Cykelreparatör",
    headline: "Snabb service förtjänar en snabb sida.",
    pitch:
      "Reparationer, priser och öppettider direkt. Få cyklisten att rulla in till dig i stället för att leta vidare.",
    family: "service",
    category: "business",
    promptSeed:
      "Jag är cykelreparatör och vill ha en hemsida med reparationer, priser och öppettider.",
  },
  {
    slug: "revisor",
    image: "/Bilder/revisor.webp",
    displayName: "Revisor",
    headline: "Ordning och reda — redan på första sidan.",
    pitch:
      "Tjänster, branscher och kontakt presenterat med förtroende. Visa att deras siffror är i trygga händer.",
    family: "service",
    category: "accounting",
    promptSeed:
      "Jag är revisor och vill ha en hemsida med tjänster, branscher och kontakt som inger förtroende.",
  },
  {
    slug: "bagare",
    image: "/Bilder/bagare.webp",
    displayName: "Bagare",
    headline: "Från ugn till skärm — utan krångel.",
    pitch:
      "Berätta om hantverket, sortimentet och var man hittar er. En aptitlig sida som lockar in nya stamkunder.",
    family: "restaurant",
    category: "restaurant",
    promptSeed:
      "Jag är bagare och vill ha en hemsida med sortiment, hantverk och var man hittar mig.",
  },
  {
    slug: "bokhandel",
    image: "/Bilder/bokhandel.webp",
    displayName: "Bokhandel",
    headline: "En bra historia förtjänar en bra sida.",
    pitch:
      "Visa sortiment, evenemang och själen i butiken. Få läsare att kliva in — på riktigt och på nätet.",
    family: "ecommerce",
    category: "ecommerce",
    promptSeed:
      "Jag driver en bokhandel och vill ha en hemsida med sortiment, evenemang och själen i butiken.",
  },
  {
    slug: "delikatess",
    image: "/Bilder/delikatess.webp",
    displayName: "Delikatessbutik",
    headline: "Smak som syns redan på sidan.",
    pitch:
      "Chark, ostar och läckerheter, vackert presenterat. Gör det lätt för matälskare att hitta er hylla.",
    family: "ecommerce",
    category: "food",
    promptSeed:
      "Vi driver en delikatessbutik och vill ha en hemsida med sortiment och var man hittar oss.",
  },
  {
    slug: "skraddare",
    image: "/Bilder/skraddare.webp",
    displayName: "Skräddare",
    headline: "Skräddarsytt — ända in i sista detaljen.",
    pitch:
      "Visa hantverket, tjänsterna och passformen. En elegant sida för kunder som vet skillnaden på sytt och välsytt.",
    family: "service",
    category: "business",
    promptSeed:
      "Jag är skräddare och vill ha en elegant hemsida med hantverk, tjänster och kontakt.",
  },
  {
    slug: "musiklarare",
    image: "/Bilder/musiklarare.webp",
    displayName: "Musiklärare",
    headline: "Nästa elev letar efter dig just nu.",
    pitch:
      "Instrument, nivåer och hur man bokar en lektion. En personlig sida som får föräldrar och elever att höra av sig.",
    family: "service",
    category: "music",
    promptSeed:
      "Jag är musiklärare och vill ha en hemsida med instrument, nivåer och hur man bokar en lektion.",
  },
  {
    slug: "tygbutik",
    image: "/Bilder/tygbutik.webp",
    displayName: "Tygbutik",
    headline: "Färg, mönster och känsla — på en sida.",
    pitch:
      "Visa sortimentet och inspirera till nästa projekt. Gör det lätt för sömnadssugna att hitta just ditt tyg.",
    family: "ecommerce",
    category: "ecommerce",
    promptSeed:
      "Jag driver en tygbutik och vill ha en hemsida med sortiment som inspirerar till nästa projekt.",
  },
  {
    slug: "atelje",
    image: "/Bilder/atelje.webp",
    displayName: "Ateljé",
    headline: "Din konst, inramad precis rätt.",
    pitch:
      "Verk, utställningar och beställningar i en stilren portfolio. Låt ateljén synas utan att stjäla fokus från konsten.",
    family: "creative",
    category: "portfolio",
    promptSeed:
      "Jag har en ateljé och vill ha en stilren portfolio-hemsida med verk, utställningar och beställningar.",
  },
  {
    slug: "kontor",
    image: "/Bilder/kontor.webp",
    displayName: "Kontor & tjänster",
    headline: "Professionellt första intryck, varje gång.",
    pitch:
      "Tjänster, team och kontakt presenterat rent och tydligt. Ge kunderna förtroende redan innan första mötet.",
    family: "consulting",
    category: "consulting",
    promptSeed:
      "Vi erbjuder kontorstjänster och vill ha en hemsida med tjänster, team och kontakt.",
  },
];

/** Slå upp ett yrke på slug. Används av /for/[yrke] (notFound vid okänd). */
export function getProfession(slug: string): Profession | undefined {
  return PROFESSIONS.find((p) => p.slug === slug);
}
