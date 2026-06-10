/**
 * Demo-profiler för Discovery Wizard.
 *
 * Operatören kan klicka "Fyll demo" i wizard-footern för att slippa
 * skriva igenom alla 5 stegen varje gång under utveckling. Profilerna
 * är realistiska små-företags-exempel som täcker olika scaffold/branch-
 * kombinationer:
 *
 *   1. Måleri & Bygg Genberg — `construction` → local-service-business
 *      scaffold med portfolio + team + USP:er.
 *   2. Lilla Bageriet Sigtuna — `restaurant` → restaurant-hospitality
 *      scaffold (Path A active) med meny, kök, kostalternativ och
 *      `warm-bistro`-vibe.
 *   3. Norrlands CBD — `ecommerce` → ecommerce-lite scaffold med
 *      produkter, prisnivå och webshop-CTA.
 *
 * Alla tre profiler är komplett valida mot `validateWizardStep` så
 * operatören kan klicka "Skapa sajt" direkt efter att ha tryckt
 * "Fyll demo". Profilerna roterar med varje klick så man kan testa
 * alla tre branches utan att stänga och öppna wizarden.
 *
 * 2026-05-19 — uppdaterad för 5-stegs-strukturen. Nya fält
 * (`businessFamily`, `vibe`, `selectedFunctions`, `specialRequests`,
 * `media`, `moodImages`) är ifyllda med vettiga defaults per profil.
 */

import type { WizardAnswers } from "./wizard-types";

export type DemoProfile = {
  id: string;
  /** Kort etikett som visas i toasten efter att profilen fyllts i. */
  label: string;
  /** Komplett WizardAnswers-objekt som ersätter användarens state. */
  build: () => WizardAnswers;
};

function genbergPainter(): WizardAnswers {
  return {
    companyName: "Måleri & Bygg Genberg",
    offer:
      "Familjeägt måleri- och byggföretag i Stockholm sedan 2008. Allt från inomhusmålning till totalrenovering — fast pris efter platsbesök, eget team, inga underentreprenörer.",
    existingSite: "",
    contact: {
      phone: "08-123 45 67",
      email: "kontakt@malerigenberg.se",
      address: "Sveavägen 42, 113 50 Stockholm",
      openingHours: "Mån-fre 07-17, helger efter överenskommelse",
    },
    businessFamily: "construction",
    sniCode: "43.341",
    siteType: ["construction"],
    vibe: {
      vibeId: "warm-craft",
      useCustomColors: true,
      typographyFeel: "classic-serif",
      references: "byggcompaniet.se, klipporna.se",
      layoutHint: "",
      sectionTreatments: {},
    },
    brand: {
      toneTags: ["Professionell", "Varm och personlig"],
      designStyle: "Naturlig och varm",
      primaryColorHex: "#2D5F3F",
      accentColorHex: "#D4A574",
      wordsToAvoid: "billig, snabbfix, lågpris",
    },
    moodImages: [],
    selectedFunctions: [
      "fn-team",
      "fn-pricing",
      "fn-gallery",
      "fn-contact",
      "fn-quote",
      "fn-reviews",
    ],
    mustHave: [
      "Startsida / Hero",
      "Portfolio / Case",
      "Om oss / Om mig",
      "Kundrecensioner",
      "Kontaktformulär",
      "Vårt team",
      "Priser och paket",
      "Bildgalleri",
    ],
    primaryCta: "Begär offert",
    specialRequests:
      "Vi vill ha en före/efter-slider på portfolio-sidan om det är möjligt.",
    products: [],
    menuItems: [],
    services: [
      {
        id: "svc-1",
        name: "Inomhusmålning",
        price: "från 350 kr/m²",
        durationMinutes: 240,
        description:
          "Tak, väggar och snickerier. Vi flyttar möbler, täcker golv och städar efter oss.",
      },
      {
        id: "svc-2",
        name: "Fasadrenovering",
        price: "Offert",
        description:
          "Skrapning, grundning och färg. Höglandsen, ställning och säkerhetsutrustning ingår.",
      },
      {
        id: "svc-3",
        name: "Köks- och badrumsrenovering",
        price: "Offert",
        description:
          "Kakelsättning, VVS-koordinering och kompletta entreprenader med fast tidsplan.",
      },
    ],
    team: [
      {
        id: "team-1",
        name: "Christopher Genberg",
        role: "Grundare och måleri-mästare",
        bio: "Tredje generationens målare med över 20 års erfarenhet i Stockholms innerstad.",
      },
      {
        id: "team-2",
        name: "Anna Lindqvist",
        role: "Projektledare",
        bio: "Säkerställer tidsplaner, kvalitet och kommunikation på varje uppdrag.",
      },
    ],
    projects: [
      {
        id: "proj-1",
        name: "Totalrenovering Vasastan",
        client: "Privatkund",
        description:
          "Helrenovering av sekelskifteslägenhet, 110 m². Kök, badrum, golv och målning.",
      },
      {
        id: "proj-2",
        name: "Fasadmålning BRF Parkudden",
        client: "BRF Parkudden",
        description:
          "Komplett fasadrenovering av fyra huskroppar, slutfört 2024.",
      },
    ],
    cuisineTags: [],
    dietaryTags: [],
    priceTier: "",
    bookingUrl: "",
    uniqueSellingPoints: [
      "Fast pris efter platsbesök",
      "Försäkring och certifiering",
      "Eget team — inga underentreprenörer",
    ],
    aboutText:
      "Genberg har målat och byggt i Stockholm sedan 2008. Vi tror på hederlighet, hantverksskicklighet och att lämna ett hem bättre än vi mötte det.",
    historyText:
      "Grundades 2008 av Christopher Genberg efter 15 år som anställd målare. Vi växte från en man till ett team på 12 personer under 2010-talet och har idag stamkunder över hela Stockholm.",
    visionText:
      "Att vara Stockholms mest pålitliga måleri- och byggteam. Inga genvägar, ingen prutmun, bara hantverk som håller.",
    contactIntroText:
      "Hör av dig så bokar vi ett platsbesök inom en vecka. Vi svarar inom 24 timmar på vardagar.",
    targetAudience:
      "Privatpersoner och bostadsrättsföreningar i Stockholms innerstad som värdesätter kvalitet och pålitlighet före lägsta pris.",
    assets: { logo: null, heroImage: null, gallery: [] },
    media: { favicon: null, ogImage: null, backgroundVideo: null },
    scrapedFields: {},
  };
}

function lillaBageriet(): WizardAnswers {
  return {
    companyName: "Lilla Bageriet Sigtuna",
    offer:
      "Sigtunas hantverksbageri sedan 2015. Surdegsbröd, kanelbullar och säsongsbakelser bakade på riktigt smör och svenska råvaror — på plats i vår lilla butik vid Stora Gatan.",
    existingSite: "",
    contact: {
      phone: "08-555 12 34",
      email: "hej@lillabagerietsigtuna.se",
      address: "Stora Gatan 18, 193 30 Sigtuna",
      openingHours: "Tis-fre 07-17, lör 08-15, sön 09-14, mån stängt",
    },
    businessFamily: "restaurant",
    sniCode: "56.110",
    siteType: ["restaurant"],
    vibe: {
      vibeId: "warm-bistro",
      useCustomColors: true,
      typographyFeel: "classic-serif",
      references: "saturday-bakeries.com, fabrique.com",
      layoutHint: "",
      sectionTreatments: {},
    },
    brand: {
      toneTags: ["Varm och personlig", "Lugn och förtroendeingivande"],
      designStyle: "Naturlig och varm",
      primaryColorHex: "#7C4A2F",
      accentColorHex: "#E8D5B7",
      wordsToAvoid: "industriellt, fryst, massproducerat",
    },
    moodImages: [],
    selectedFunctions: [
      "fn-menu",
      "fn-tableresv",
      "fn-gallery",
      "fn-map",
      "fn-hours",
      "fn-contact",
    ],
    mustHave: [
      "Startsida / Hero",
      "Meny / Matsedel",
      "Bildgalleri",
      "Karta / Hitta hit",
      "Om oss / Om mig",
      "Bokning online",
      "Kontaktformulär",
    ],
    primaryCta: "Hitta hit",
    specialRequests:
      "Instagram-feed på startsidan skulle vara grymt — vi postar mycket varje dag.",
    products: [],
    menuItems: [
      {
        id: "menu-1",
        name: "Levainbröd",
        price: "65 kr",
        description: "Långjäst surdegsbröd, dinkel och rågmjöl från Värmland.",
        category: "Bröd",
      },
      {
        id: "menu-2",
        name: "Kanelbulle",
        price: "32 kr",
        description:
          "Klassisk, med smör, kanel och pärlsocker. Bakas hela dagen.",
        category: "Bakverk",
      },
      {
        id: "menu-3",
        name: "Säsongstårta",
        price: "från 85 kr/bit",
        description:
          "Vad vi har av frukt och bär just nu. Fråga i butiken eller följ oss på Instagram.",
        category: "Tårta",
      },
      {
        id: "menu-4",
        name: "Frukostfralla",
        price: "55 kr",
        description:
          "Levainbröd, hyvlad ost, ägg och avokado. Bara på lör-sön.",
        category: "Frukost",
      },
    ],
    services: [],
    team: [
      {
        id: "team-1",
        name: "Maja Bergström",
        role: "Bagare & grundare",
        bio: "Bakade sig genom Saint Vincent i Paris innan hon flyttade hem till Sigtuna 2014.",
      },
    ],
    projects: [],
    cuisineTags: ["Café / Fika", "Svenskt"],
    dietaryTags: ["Vegetariskt", "Laktosfritt"],
    priceTier: "Mellan",
    bookingUrl: "",
    uniqueSellingPoints: [
      "Allt bakas på plats varje dag",
      "Råvaror från svenska kvarnar och gårdar",
      "Inga konserveringsmedel — slut är slut",
    ],
    aboutText:
      "Lilla Bageriet öppnade på Stora Gatan 2015. Vi är fyra personer som bakar varje dag innan butiken öppnar, och håller på tills det vi gjort tar slut.",
    historyText:
      "Maja bakade sig genom Saint Vincent i Paris 2010-2013 och flyttade hem till Sigtuna för att starta något eget. Bageriet växte långsamt och vi expanderade till en större lokal 2020.",
    visionText:
      "Att vara den självklara fikastunden för Sigtunaborna och en värd anledning att stanna till för förbipasserande.",
    contactIntroText:
      "Vi tar gärna emot beställningar för fester och kaffeleveranser till kontor — ring eller maila minst tre dagar innan.",
    targetAudience:
      "Sigtunabor, helgbesökare från Stockholm och Uppsala, samt företagskunder som vill imponera på sina gäster med riktig fika.",
    assets: { logo: null, heroImage: null, gallery: [] },
    media: { favicon: null, ogImage: null, backgroundVideo: null },
    scrapedFields: {},
  };
}

function norrlandsCbd(): WizardAnswers {
  return {
    companyName: "Norrlands CBD",
    offer:
      "Skandinaviens renaste CBD-olja. Ekologiskt odlad hampa från Jämtland, koldioxidextraherad, tredje-parts-testad. Snabb leverans inom Sverige.",
    existingSite: "",
    contact: {
      phone: "063-456 78 90",
      email: "kundtjanst@norrlandscbd.se",
      address: "Storgatan 5, 831 30 Östersund",
      openingHours: "Webbshop öppen dygnet runt. Kundtjänst mån-fre 09-17.",
    },
    businessFamily: "ecommerce",
    sniCode: "47.752",
    siteType: ["ecommerce"],
    vibe: {
      vibeId: "earth-wellness",
      useCustomColors: true,
      typographyFeel: "organic",
      references: "loveandsage.se, the-ordinary.com",
      layoutHint: "",
      sectionTreatments: {},
    },
    brand: {
      toneTags: ["Lugn och förtroendeingivande", "Professionell"],
      designStyle: "Minimalistisk",
      primaryColorHex: "#1F3A2E",
      accentColorHex: "#A8C49A",
      wordsToAvoid: "rusa, hög, drog",
    },
    moodImages: [],
    selectedFunctions: [
      "fn-catalog",
      "fn-cart",
      "fn-checkout",
      "fn-prodreview",
      "fn-faq",
      "fn-contact",
      "fn-newsletter",
    ],
    mustHave: [
      "Startsida / Hero",
      "Webshop / Produkter",
      "Om oss / Om mig",
      "FAQ",
      "Kontaktformulär",
      "Nyhetsbrev",
    ],
    primaryCta: "Köp nu",
    specialRequests:
      "Vi behöver visa testresultat (PDF) per sats — gärna nedladdningsbara.",
    products: [
      {
        id: "prod-1",
        name: "CBD-olja 5% — 10 ml",
        price: "395 kr",
        description:
          "Vår mildaste olja, perfekt för nybörjare. Naturlig hampsmak, dropp under tungan.",
        category: "Oljor",
      },
      {
        id: "prod-2",
        name: "CBD-olja 15% — 10 ml",
        price: "895 kr",
        description:
          "Mid-range styrka för dagligt bruk. Ekologiskt MCT-kokosolja som bärare.",
        category: "Oljor",
      },
      {
        id: "prod-3",
        name: "CBG-olja 10% — 10 ml",
        price: "1 295 kr",
        description:
          'CBG kallas "moderkannabinoiden". Vår mest premium produkt — mindre volym, högre koncentration.',
        category: "Oljor",
      },
      {
        id: "prod-4",
        name: "CBD-kapslar 25 mg — 60 st",
        price: "595 kr",
        description:
          "Smaklös och praktisk. Bra alternativ om man inte gillar oljornas smak.",
        category: "Kapslar",
      },
    ],
    menuItems: [],
    services: [],
    team: [],
    projects: [],
    cuisineTags: [],
    dietaryTags: [],
    priceTier: "Premium",
    bookingUrl: "",
    uniqueSellingPoints: [
      "Ekologiskt odlad i Jämtland",
      "Tredje-parts-testat — resultat på varje sats",
      "Fri frakt över 500 kr, leverans inom 2 arbetsdagar",
    ],
    aboutText:
      "Norrlands CBD grundades 2021 av två agronomer som tröttnade på utländska CBD-produkter med oklar bakgrund. Vi odlar, extraherar och tappar allt i Östersund.",
    historyText:
      "Erik och Sara träffades på SLU i Umeå 2015 och började experimentera med hampa-odling i en växthus utanför Östersund 2019. 2021 fick vi vårt första EU-godkännande och öppnade webshopen.",
    visionText:
      "Att vara Nordens mest transparenta CBD-leverantör — från frö till flaska, ingen mellanhand, inga hemligheter.",
    contactIntroText:
      "Frågor om dosering eller leverans? Kundtjänsten svarar inom 4 timmar på vardagar.",
    targetAudience:
      "Hälsomedvetna konsumenter 30-65 år som värdesätter ekologi, spårbarhet och nordiskt ursprung framför lägsta pris.",
    assets: { logo: null, heroImage: null, gallery: [] },
    media: { favicon: null, ogImage: null, backgroundVideo: null },
    scrapedFields: {},
  };
}

/**
 * Ordnad lista av demo-profiler. Wizarden roterar genom dem så
 * varje "Fyll demo"-klick laddar nästa i ordningen. Lägg till nya
 * profiler genom att pusha till listan — UI:t plockar upp dem
 * automatiskt.
 */
export const DEMO_PROFILES: DemoProfile[] = [
  {
    id: "genberg-painter",
    label: "Måleri Genberg",
    build: genbergPainter,
  },
  {
    id: "lilla-bageriet",
    label: "Lilla Bageriet Sigtuna",
    build: lillaBageriet,
  },
  {
    id: "norrlands-cbd",
    label: "Norrlands CBD",
    build: norrlandsCbd,
  },
];
