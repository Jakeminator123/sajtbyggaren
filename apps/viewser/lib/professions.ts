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
 */
export type Profession = {
  slug: string;
  image: string;
  displayName: string;
  headline: string;
  pitch: string;
};

export const PROFESSIONS: ReadonlyArray<Profession> = [
  {
    slug: "bilmekaniker",
    image: "/Bilder/bilmekaniker.webp",
    displayName: "Bilverkstad",
    headline: "Verkstaden kunderna litar på — online.",
    pitch:
      "Dina kunder googlar “bilverkstad nära mig” redan vid frukosten. Ge dem en sida som visar tider, tjänster och vägen in — innan de ringer någon annan.",
  },
  {
    slug: "frisorsalong",
    image: "/Bilder/frisorsalong.webp",
    displayName: "Frisörsalong",
    headline: "En fullbokad kalender börjar med en snygg sida.",
    pitch:
      "Visa stilen, teamet och hur man bokar. En ren, personlig sida som får nya kunder att vilja sätta sig i just din stol.",
  },
  {
    slug: "bageri",
    image: "/Bilder/bageri.webp",
    displayName: "Bageri",
    headline: "Doften kan vi inte ladda upp — allt annat fixar vi.",
    pitch:
      "Surdeg, öppettider och dagens bröd, vackert presenterat. Låt grannskapet hitta er innan brödet tar slut.",
  },
  {
    slug: "blomsterhandel",
    image: "/Bilder/blomsterhandel.webp",
    displayName: "Blomsterhandel",
    headline: "Buketter förtjänar mer än ett skyltfönster.",
    pitch:
      "Visa dina arrangemang och gör det lätt att beställa till bröllop, begravning eller bara för att. En sida lika omsorgsfull som dina buketter.",
  },
  {
    slug: "snickare",
    image: "/Bilder/snickare.webp",
    displayName: "Snickare",
    headline: "Hantverket talar — låt sidan göra det också.",
    pitch:
      "Bilder på färdiga projekt säger mer än tusen offerter. Ge kunderna ett enkelt sätt att se vad du kan och höra av sig.",
  },
  {
    slug: "tandlakare",
    image: "/Bilder/tandlakare.webp",
    displayName: "Tandläkare",
    headline: "Trygghet börjar innan patienten kliver in.",
    pitch:
      "En lugn, professionell sida med tjänster, team och tidsbokning. Få nya patienter att känna sig trygga redan vid första klicket.",
  },
  {
    slug: "yogastudio",
    image: "/Bilder/yogastudio.webp",
    displayName: "Yogastudio",
    headline: "Hitta lugnet — och nya elever.",
    pitch:
      "Schema, pass och känslan i studion på en stillsam, vacker sida. Låt nya elever andas ut redan innan första passet.",
  },
  {
    slug: "keramik",
    image: "/Bilder/keramik.webp",
    displayName: "Keramikstudio",
    headline: "Varje pjäs är unik. Din sida borde också vara det.",
    pitch:
      "Visa dina verk, kurser och beställningar i en galleri-ren sida. Gör det lätt för samlare och nyfikna att hitta dig.",
  },
  {
    slug: "bygg",
    image: "/Bilder/bygg.webp",
    displayName: "Byggfirma",
    headline: "Bygg förtroende innan första spadtaget.",
    pitch:
      "Referensprojekt, tjänster och kontakt — tydligt och proffsigt. Den kund som ser att ni levererar hör av sig först.",
  },
  {
    slug: "hundvard",
    image: "/Bilder/hundvard.webp",
    displayName: "Hundvård",
    headline: "Viftande svansar börjar med en bokning.",
    pitch:
      "Trim, dagis eller pensionat — visa tjänsterna och gör det enkelt att boka. En varm, tydlig sida som både matte och husse litar på.",
  },
  {
    slug: "cykelreperator",
    image: "/Bilder/cykelreperator.webp",
    displayName: "Cykelreparatör",
    headline: "Snabb service förtjänar en snabb sida.",
    pitch:
      "Reparationer, priser och öppettider direkt. Få cyklisten att rulla in till dig i stället för att leta vidare.",
  },
  {
    slug: "revisor",
    image: "/Bilder/revisor.webp",
    displayName: "Revisor",
    headline: "Ordning och reda — redan på första sidan.",
    pitch:
      "Tjänster, branscher och kontakt presenterat med förtroende. Visa att deras siffror är i trygga händer.",
  },
  {
    slug: "bagare",
    image: "/Bilder/bagare.webp",
    displayName: "Bagare",
    headline: "Från ugn till skärm — utan krångel.",
    pitch:
      "Berätta om hantverket, sortimentet och var man hittar er. En aptitlig sida som lockar in nya stamkunder.",
  },
  {
    slug: "bokhandel",
    image: "/Bilder/bokhandel.webp",
    displayName: "Bokhandel",
    headline: "En bra historia förtjänar en bra sida.",
    pitch:
      "Visa sortiment, evenemang och själen i butiken. Få läsare att kliva in — på riktigt och på nätet.",
  },
  {
    slug: "delikatess",
    image: "/Bilder/delikatess.webp",
    displayName: "Delikatessbutik",
    headline: "Smak som syns redan på sidan.",
    pitch:
      "Chark, ostar och läckerheter, vackert presenterat. Gör det lätt för matälskare att hitta er hylla.",
  },
  {
    slug: "skraddare",
    image: "/Bilder/skraddare.webp",
    displayName: "Skräddare",
    headline: "Skräddarsytt — ända in i sista detaljen.",
    pitch:
      "Visa hantverket, tjänsterna och passformen. En elegant sida för kunder som vet skillnaden på sytt och välsytt.",
  },
  {
    slug: "musiklarare",
    image: "/Bilder/musiklarare.webp",
    displayName: "Musiklärare",
    headline: "Nästa elev letar efter dig just nu.",
    pitch:
      "Instrument, nivåer och hur man bokar en lektion. En personlig sida som får föräldrar och elever att höra av sig.",
  },
  {
    slug: "tygbutik",
    image: "/Bilder/tygbutik.webp",
    displayName: "Tygbutik",
    headline: "Färg, mönster och känsla — på en sida.",
    pitch:
      "Visa sortimentet och inspirera till nästa projekt. Gör det lätt för sömnadssugna att hitta just ditt tyg.",
  },
  {
    slug: "atelje",
    image: "/Bilder/atelje.webp",
    displayName: "Ateljé",
    headline: "Din konst, inramad precis rätt.",
    pitch:
      "Verk, utställningar och beställningar i en stilren portfolio. Låt ateljén synas utan att stjäla fokus från konsten.",
  },
  {
    slug: "kontor",
    image: "/Bilder/kontor.webp",
    displayName: "Kontor & tjänster",
    headline: "Professionellt första intryck, varje gång.",
    pitch:
      "Tjänster, team och kontakt presenterat rent och tydligt. Ge kunderna förtroende redan innan första mötet.",
  },
];

/** Slå upp ett yrke på slug. Används av /for/[yrke] (notFound vid okänd). */
export function getProfession(slug: string): Profession | undefined {
  return PROFESSIONS.find((p) => p.slug === slug);
}
