/**
 * Konfiguration för programmatisk SEO-generering.
 *
 * Varje lista driver en slug-familj — ändra här för att lägga till/ta bort
 * landningssidor. Content genereras per slug av
 * `scripts/seo/generate-landings.ts` och renderas av motsvarande route under
 * `src/app/`.
 *
 * Invånarantal är avrundat (SCB 2023/2024) och används bara som kontext i
 * promten — inte i ren text på sidan. Ändra inte slugs när en sida väl är
 * publicerad (det bryter inkommande länkar); lägg hellre till redirects.
 */

import type {
  SeoAiConfig,
  SeoCityConfig,
  SeoCityUsecaseConfig,
  SeoCompareConfig,
  SeoIndustryConfig,
  SeoUsecaseConfig,
} from "./types";

/* ── Städer (60 st största kommuner) ─────────────────────────────── */

export const SEO_CITIES: SeoCityConfig[] = [
  { slug: "stockholm", label: "Stockholm", region: "Stockholms län", population: 980000 },
  { slug: "goteborg", label: "Göteborg", region: "Västra Götalands län", population: 590000 },
  { slug: "malmo", label: "Malmö", region: "Skåne län", population: 360000 },
  { slug: "uppsala", label: "Uppsala", region: "Uppsala län", population: 240000 },
  { slug: "vasteras", label: "Västerås", region: "Västmanlands län", population: 160000 },
  { slug: "orebro", label: "Örebro", region: "Örebro län", population: 160000 },
  { slug: "linkoping", label: "Linköping", region: "Östergötlands län", population: 170000 },
  { slug: "helsingborg", label: "Helsingborg", region: "Skåne län", population: 150000 },
  { slug: "jonkoping", label: "Jönköping", region: "Jönköpings län", population: 145000 },
  { slug: "norrkoping", label: "Norrköping", region: "Östergötlands län", population: 145000 },
  { slug: "lund", label: "Lund", region: "Skåne län", population: 130000 },
  { slug: "umea", label: "Umeå", region: "Västerbottens län", population: 132000 },
  { slug: "gavle", label: "Gävle", region: "Gävleborgs län", population: 105000 },
  { slug: "boras", label: "Borås", region: "Västra Götalands län", population: 115000 },
  { slug: "eskilstuna", label: "Eskilstuna", region: "Södermanlands län", population: 110000 },
  { slug: "sodertalje", label: "Södertälje", region: "Stockholms län", population: 105000 },
  { slug: "karlstad", label: "Karlstad", region: "Värmlands län", population: 95000 },
  { slug: "taby", label: "Täby", region: "Stockholms län", population: 75000 },
  { slug: "vaxjo", label: "Växjö", region: "Kronobergs län", population: 95000 },
  { slug: "halmstad", label: "Halmstad", region: "Hallands län", population: 105000 },
  { slug: "sundsvall", label: "Sundsvall", region: "Västernorrlands län", population: 100000 },
  { slug: "lulea", label: "Luleå", region: "Norrbottens län", population: 80000 },
  { slug: "trollhattan", label: "Trollhättan", region: "Västra Götalands län", population: 60000 },
  { slug: "ostersund", label: "Östersund", region: "Jämtlands län", population: 65000 },
  { slug: "borlange", label: "Borlänge", region: "Dalarnas län", population: 53000 },
  { slug: "tumba", label: "Tumba", region: "Stockholms län", population: 90000 },
  { slug: "upplands-vasby", label: "Upplands Väsby", region: "Stockholms län", population: 48000 },
  { slug: "falun", label: "Falun", region: "Dalarnas län", population: 60000 },
  { slug: "kalmar", label: "Kalmar", region: "Kalmar län", population: 71000 },
  { slug: "kristianstad", label: "Kristianstad", region: "Skåne län", population: 87000 },
  { slug: "skelleftea", label: "Skellefteå", region: "Västerbottens län", population: 75000 },
  { slug: "karlskrona", label: "Karlskrona", region: "Blekinge län", population: 66000 },
  { slug: "landskrona", label: "Landskrona", region: "Skåne län", population: 47000 },
  { slug: "uddevalla", label: "Uddevalla", region: "Västra Götalands län", population: 57000 },
  { slug: "motala", label: "Motala", region: "Östergötlands län", population: 45000 },
  { slug: "trelleborg", label: "Trelleborg", region: "Skåne län", population: 47000 },
  { slug: "varberg", label: "Varberg", region: "Hallands län", population: 67000 },
  { slug: "solna", label: "Solna", region: "Stockholms län", population: 85000 },
  { slug: "sollentuna", label: "Sollentuna", region: "Stockholms län", population: 74000 },
  { slug: "nacka", label: "Nacka", region: "Stockholms län", population: 105000 },
  { slug: "huddinge", label: "Huddinge", region: "Stockholms län", population: 115000 },
  { slug: "botkyrka", label: "Botkyrka", region: "Stockholms län", population: 95000 },
  { slug: "jarfalla", label: "Järfälla", region: "Stockholms län", population: 82000 },
  { slug: "haninge", label: "Haninge", region: "Stockholms län", population: 95000 },
  { slug: "norrtalje", label: "Norrtälje", region: "Stockholms län", population: 64000 },
  { slug: "sigtuna", label: "Sigtuna", region: "Stockholms län", population: 50000 },
  { slug: "tyreso", label: "Tyresö", region: "Stockholms län", population: 50000 },
  { slug: "upplands-bro", label: "Upplands-Bro", region: "Stockholms län", population: 30000 },
  { slug: "mora", label: "Mora", region: "Dalarnas län", population: 21000 },
  { slug: "vetlanda", label: "Vetlanda", region: "Jönköpings län", population: 28000 },
  { slug: "enkoping", label: "Enköping", region: "Uppsala län", population: 47000 },
  { slug: "kungsbacka", label: "Kungsbacka", region: "Hallands län", population: 85000 },
  { slug: "skovde", label: "Skövde", region: "Västra Götalands län", population: 57000 },
  { slug: "lidkoping", label: "Lidköping", region: "Västra Götalands län", population: 40000 },
  { slug: "alingsas", label: "Alingsås", region: "Västra Götalands län", population: 41000 },
  { slug: "katrineholm", label: "Katrineholm", region: "Södermanlands län", population: 34000 },
  { slug: "nykoping", label: "Nyköping", region: "Södermanlands län", population: 58000 },
  { slug: "pitea", label: "Piteå", region: "Norrbottens län", population: 42000 },
  { slug: "vaggeryd", label: "Vaggeryd", region: "Jönköpings län", population: 14000 },
  { slug: "visby", label: "Visby", region: "Gotlands län", population: 25000 },
];

/* ── Användningsområden (40 st) ──────────────────────────────────── */

export const SEO_USECASES: SeoUsecaseConfig[] = [
  { slug: "webshop", label: "Webshop", targetKeyword: "skapa hemsida webshop", audience: "en handlare som säljer produkter online" },
  { slug: "restaurang", label: "Restaurang", targetKeyword: "hemsida restaurang", audience: "en restaurang, café eller pizzeria" },
  { slug: "cafe", label: "Café", targetKeyword: "hemsida café", audience: "ett kafé eller bageri" },
  { slug: "salong", label: "Salong", targetKeyword: "hemsida salong", audience: "en frisör eller skönhetssalong" },
  { slug: "portfolio", label: "Portfolio", targetKeyword: "skapa portfolio-sida", audience: "en designer, fotograf eller frilansare" },
  { slug: "blogg", label: "Blogg", targetKeyword: "starta blogg hemsida", audience: "en skribent, influencer eller bloggare" },
  { slug: "landningssida", label: "Landningssida", targetKeyword: "skapa landningssida", audience: "en marknadsförare eller startup som lanserar en produkt" },
  { slug: "event", label: "Event", targetKeyword: "hemsida event", audience: "en eventarrangör eller bröllopsplanerare" },
  { slug: "foretag", label: "Företag", targetKeyword: "hemsida företag", audience: "ett mindre eller medelstort företag" },
  { slug: "startup", label: "Startup", targetKeyword: "hemsida startup", audience: "en tidig startup som validerar sin idé" },
  { slug: "konsult", label: "Konsult", targetKeyword: "hemsida konsult", audience: "en konsult eller byrå" },
  { slug: "freelance", label: "Freelance", targetKeyword: "hemsida freelance", audience: "en frilansare eller konsult" },
  { slug: "forening", label: "Förening", targetKeyword: "hemsida förening", audience: "en ideell förening eller klubb" },
  { slug: "gym", label: "Gym", targetKeyword: "hemsida gym", audience: "ett gym eller PT-studio" },
  { slug: "pt", label: "Personlig tränare", targetKeyword: "hemsida personlig tränare", audience: "en personlig tränare eller coach" },
  { slug: "yoga", label: "Yoga", targetKeyword: "hemsida yoga", audience: "en yogastudio eller lärare" },
  { slug: "klinik", label: "Klinik", targetKeyword: "hemsida klinik", audience: "en klinik eller mottagning" },
  { slug: "tandlakare", label: "Tandläkare", targetKeyword: "hemsida tandläkare", audience: "en tandläkarpraktik" },
  { slug: "advokat", label: "Advokat", targetKeyword: "hemsida advokatbyrå", audience: "en advokat eller jurist" },
  { slug: "redovisning", label: "Redovisning", targetKeyword: "hemsida redovisningsbyrå", audience: "en redovisningsbyrå eller revisor" },
  { slug: "fastighetsmaklare", label: "Fastighetsmäklare", targetKeyword: "hemsida fastighetsmäklare", audience: "en mäklare eller mäklarbyrå" },
  { slug: "bygg", label: "Bygg", targetKeyword: "hemsida byggföretag", audience: "en byggfirma eller entreprenör" },
  { slug: "vvs", label: "VVS", targetKeyword: "hemsida VVS", audience: "en VVS-installatör" },
  { slug: "elektriker", label: "Elektriker", targetKeyword: "hemsida elektriker", audience: "en elektriker eller el-firma" },
  { slug: "snickare", label: "Snickare", targetKeyword: "hemsida snickare", audience: "en snickare eller hantverkare" },
  { slug: "stadfirma", label: "Städfirma", targetKeyword: "hemsida städfirma", audience: "en städfirma" },
  { slug: "akeri", label: "Åkeri", targetKeyword: "hemsida åkeri", audience: "ett åkeri eller transportbolag" },
  { slug: "bilverkstad", label: "Bilverkstad", targetKeyword: "hemsida bilverkstad", audience: "en bilverkstad eller däckfirma" },
  { slug: "fotograf", label: "Fotograf", targetKeyword: "hemsida fotograf", audience: "en fotograf eller videograf" },
  { slug: "musiker", label: "Musiker", targetKeyword: "hemsida musiker", audience: "en artist, band eller musikproducent" },
  { slug: "konstnar", label: "Konstnär", targetKeyword: "hemsida konstnär", audience: "en konstnär eller illustratör" },
  { slug: "bokning", label: "Bokning", targetKeyword: "hemsida med bokning", audience: "ett företag som behöver onlinebokning" },
  { slug: "hotell", label: "Hotell", targetKeyword: "hemsida hotell", audience: "ett hotell, B&B eller vandrarhem" },
  { slug: "bnb", label: "B&B", targetKeyword: "hemsida B&B", audience: "ett bed & breakfast eller stuguthyrare" },
  { slug: "skola", label: "Skola", targetKeyword: "hemsida skola", audience: "en skola eller utbildningsaktör" },
  { slug: "kurs", label: "Kurs", targetKeyword: "hemsida kurs", audience: "en kursarrangör eller utbildare" },
  { slug: "podcast", label: "Podcast", targetKeyword: "hemsida podcast", audience: "en podcaster eller podd" },
  { slug: "bokningssystem", label: "Bokningssystem", targetKeyword: "hemsida med bokningssystem", audience: "ett företag som behöver integrerad bokning" },
  { slug: "medlemsklubb", label: "Medlemsklubb", targetKeyword: "hemsida medlemsklubb", audience: "en medlemsorganisation eller klubb" },
  { slug: "saas", label: "SaaS", targetKeyword: "hemsida saas", audience: "ett SaaS-bolag eller mjukvaruprodukt" },
];

/* ── Branscher (50 st) ───────────────────────────────────────────── */

export const SEO_INDUSTRIES: SeoIndustryConfig[] = [
  { slug: "frisor", label: "Frisör", targetKeyword: "hemsida för frisör", typicalServices: "klippning, färgning, bokning online" },
  { slug: "skonhetssalong", label: "Skönhetssalong", targetKeyword: "hemsida för skönhetssalong", typicalServices: "hudvård, ansiktsbehandling, naglar" },
  { slug: "nagelsalong", label: "Nagelsalong", targetKeyword: "hemsida för nagelsalong", typicalServices: "manikyr, pedikyr, gelnaglar" },
  { slug: "massage", label: "Massage", targetKeyword: "hemsida för massage", typicalServices: "klassisk massage, taktil, idrottsmassage" },
  { slug: "spa", label: "Spa", targetKeyword: "hemsida för spa", typicalServices: "spa-paket, ansiktsbehandlingar, massage" },
  { slug: "personlig-tranare", label: "Personlig tränare", targetKeyword: "hemsida för personlig tränare", typicalServices: "PT-pass, onlinecoaching, kostplaner" },
  { slug: "yogastudio", label: "Yogastudio", targetKeyword: "hemsida för yogastudio", typicalServices: "yogapass, yogaretreater, lärarutbildning" },
  { slug: "restaurang", label: "Restaurang", targetKeyword: "hemsida för restaurang", typicalServices: "meny, bordsbokning, catering" },
  { slug: "cafe", label: "Café", targetKeyword: "hemsida för café", typicalServices: "meny, öppettider, beställning" },
  { slug: "bageri", label: "Bageri", targetKeyword: "hemsida för bageri", typicalServices: "sortiment, tårtbeställning, leverans" },
  { slug: "catering", label: "Catering", targetKeyword: "hemsida för catering", typicalServices: "meny, event-paket, offert" },
  { slug: "foodtruck", label: "Food truck", targetKeyword: "hemsida för food truck", typicalServices: "schema, meny, event-bokning" },
  { slug: "fotograf", label: "Fotograf", targetKeyword: "hemsida för fotograf", typicalServices: "portfolio, bröllop, porträtt, prislista" },
  { slug: "videograf", label: "Videograf", targetKeyword: "hemsida för videograf", typicalServices: "film-reel, företagsfilm, bröllopsfilm" },
  { slug: "grafisk-designer", label: "Grafisk designer", targetKeyword: "hemsida för grafisk designer", typicalServices: "logotyper, identitet, print, digital" },
  { slug: "illustrator", label: "Illustratör", targetKeyword: "hemsida för illustratör", typicalServices: "portfolio, uppdrag, prints" },
  { slug: "musiker", label: "Musiker", targetKeyword: "hemsida för musiker", typicalServices: "musik, konsertkalender, kontakt" },
  { slug: "dj", label: "DJ", targetKeyword: "hemsida för DJ", typicalServices: "spellistor, bokning, event" },
  { slug: "konstnar", label: "Konstnär", targetKeyword: "hemsida för konstnär", typicalServices: "galleri, utställningar, köp" },
  { slug: "bygg", label: "Bygg", targetKeyword: "hemsida för byggföretag", typicalServices: "nybyggnation, renovering, referenser" },
  { slug: "snickare", label: "Snickare", targetKeyword: "hemsida för snickare", typicalServices: "kök, inredning, specialtillverkning" },
  { slug: "malare", label: "Målare", targetKeyword: "hemsida för målare", typicalServices: "invändig, utvändig, tapetsering" },
  { slug: "elektriker", label: "Elektriker", targetKeyword: "hemsida för elektriker", typicalServices: "installation, service, solceller" },
  { slug: "vvs", label: "VVS", targetKeyword: "hemsida för VVS-firma", typicalServices: "värmepump, badrum, akut-jour" },
  { slug: "takfirma", label: "Takfirma", targetKeyword: "hemsida för takfirma", typicalServices: "takbyte, takomläggning, reparation" },
  { slug: "golvlaggare", label: "Golvläggare", targetKeyword: "hemsida för golvläggare", typicalServices: "parkett, klinker, slipning" },
  { slug: "markfirma", label: "Markfirma", targetKeyword: "hemsida för markfirma", typicalServices: "schaktning, markarbeten, asfalt" },
  { slug: "tradgardsfirma", label: "Trädgårdsfirma", targetKeyword: "hemsida för trädgårdsfirma", typicalServices: "design, anläggning, skötsel" },
  { slug: "stadfirma", label: "Städfirma", targetKeyword: "hemsida för städfirma", typicalServices: "hemstäd, flyttstäd, företagsstäd" },
  { slug: "akeri", label: "Åkeri", targetKeyword: "hemsida för åkeri", typicalServices: "transport, logistik, kranbilar" },
  { slug: "bilverkstad", label: "Bilverkstad", targetKeyword: "hemsida för bilverkstad", typicalServices: "service, reparation, däck" },
  { slug: "bilhandlare", label: "Bilhandlare", targetKeyword: "hemsida för bilhandlare", typicalServices: "lagerbilar, värdering, finansiering" },
  { slug: "fastighetsmaklare", label: "Fastighetsmäklare", targetKeyword: "hemsida för fastighetsmäklare", typicalServices: "objekt, värdering, referenser" },
  { slug: "advokat", label: "Advokat", targetKeyword: "hemsida för advokatbyrå", typicalServices: "familjerätt, affärsjuridik, brottmål" },
  { slug: "jurist", label: "Jurist", targetKeyword: "hemsida för jurist", typicalServices: "avtal, tvister, rådgivning" },
  { slug: "redovisning", label: "Redovisningsbyrå", targetKeyword: "hemsida för redovisningsbyrå", typicalServices: "bokföring, löner, årsbokslut" },
  { slug: "revisor", label: "Revisor", targetKeyword: "hemsida för revisor", typicalServices: "revision, rådgivning, skatt" },
  { slug: "konsult", label: "Konsult", targetKeyword: "hemsida för konsult", typicalServices: "strategi, genomförande, referenser" },
  { slug: "tandlakare", label: "Tandläkare", targetKeyword: "hemsida för tandläkare", typicalServices: "kontroll, tandvård, blekning" },
  { slug: "kiropraktor", label: "Kiropraktor", targetKeyword: "hemsida för kiropraktor", typicalServices: "rygg, nacke, behandlingsplan" },
  { slug: "naprapat", label: "Naprapat", targetKeyword: "hemsida för naprapat", typicalServices: "smärta, rehab, idrottsskador" },
  { slug: "optiker", label: "Optiker", targetKeyword: "hemsida för optiker", typicalServices: "glasögon, synundersökning, linser" },
  { slug: "psykolog", label: "Psykolog", targetKeyword: "hemsida för psykolog", typicalServices: "KBT, par, online-terapi" },
  { slug: "veterinar", label: "Veterinär", targetKeyword: "hemsida för veterinär", typicalServices: "smådjur, kirurgi, akut" },
  { slug: "hundfrisor", label: "Hundfrisör", targetKeyword: "hemsida för hundfrisör", typicalServices: "klippning, trimning, bad" },
  { slug: "skogsbruk", label: "Skogsbruk", targetKeyword: "hemsida för skogsbruk", typicalServices: "avverkning, gallring, virke" },
  { slug: "lantbruk", label: "Lantbruk", targetKeyword: "hemsida för lantbruk", typicalServices: "gårdsbutik, växtodling, djur" },
  { slug: "industri", label: "Industri", targetKeyword: "hemsida för industriföretag", typicalServices: "legotillverkning, CNC, svets" },
  { slug: "mekanisk-verkstad", label: "Mekanisk verkstad", targetKeyword: "hemsida för mekanisk verkstad", typicalServices: "svarvning, fräsning, prototyp" },
  { slug: "solcellsforetag", label: "Solcellsföretag", targetKeyword: "hemsida för solcellsföretag", typicalServices: "installation, batteri, bidrag" },
];

/* ── AI-kluster (30 st) ──────────────────────────────────────────── */

export const SEO_AI_VARIANTS: SeoAiConfig[] = [
  { slug: "ai-hemsida", label: "AI-hemsida", targetKeyword: "ai hemsida", searchIntent: "vad en AI-hemsida är och hur den fungerar" },
  { slug: "bygga-hemsida-med-ai", label: "Bygga hemsida med AI", targetKeyword: "bygga hemsida med ai", searchIntent: "hur man praktiskt bygger en hemsida med AI" },
  { slug: "skapa-hemsida-med-ai", label: "Skapa hemsida med AI", targetKeyword: "skapa hemsida med ai", searchIntent: "hur man kommer igång med AI för att skapa en hemsida" },
  { slug: "gratis-ai-hemsida", label: "Gratis AI-hemsida", targetKeyword: "gratis ai hemsida", searchIntent: "om det går att skapa en AI-hemsida utan kostnad" },
  { slug: "chatgpt-hemsida", label: "ChatGPT hemsida", targetKeyword: "chatgpt hemsida", searchIntent: "om man kan använda ChatGPT för att bygga en hemsida" },
  { slug: "ai-webbplats", label: "AI-webbplats", targetKeyword: "ai webbplats", searchIntent: "vad en AI-webbplats är och vad den kan göra" },
  { slug: "ai-sajtbyggare", label: "AI-sajtbyggare", targetKeyword: "ai sajtbyggare", searchIntent: "hur en AI-sajtbyggare skiljer sig från traditionella verktyg" },
  { slug: "ai-site-builder", label: "AI site builder", targetKeyword: "ai site builder sverige", searchIntent: "bästa AI-site-builder för svenska företag" },
  { slug: "automatisk-hemsida", label: "Automatisk hemsida", targetKeyword: "automatisk hemsida", searchIntent: "hur en automatisk hemsida skapas" },
  { slug: "ai-webbutveckling", label: "AI-webbutveckling", targetKeyword: "ai webbutveckling", searchIntent: "hur AI förändrar webbutveckling" },
  { slug: "ai-generera-hemsida", label: "AI som genererar hemsida", targetKeyword: "ai generera hemsida", searchIntent: "hur en AI genererar en hemsida från text" },
  { slug: "prompt-hemsida", label: "Hemsida från prompt", targetKeyword: "hemsida från prompt", searchIntent: "att skapa hemsida genom att skriva en prompt" },
  { slug: "ai-hemsida-foretag", label: "AI-hemsida för företag", targetKeyword: "ai hemsida företag", searchIntent: "hur företag använder AI för sina hemsidor" },
  { slug: "ai-hemsida-webshop", label: "AI-hemsida webshop", targetKeyword: "ai hemsida webshop", searchIntent: "AI-driven webshop" },
  { slug: "bast-ai-hemsida", label: "Bäst AI-hemsida", targetKeyword: "bäst ai hemsida", searchIntent: "vilket AI-verktyg som är bäst för hemsidor" },
  { slug: "ai-vs-wix", label: "AI vs Wix", targetKeyword: "ai hemsida vs wix", searchIntent: "skillnaden mellan AI och traditionella byggare som Wix" },
  { slug: "ai-vs-squarespace", label: "AI vs Squarespace", targetKeyword: "ai hemsida vs squarespace", searchIntent: "om AI är bättre än Squarespace" },
  { slug: "ai-hemsida-pa-minuter", label: "AI-hemsida på minuter", targetKeyword: "hemsida på minuter ai", searchIntent: "hur snabbt AI kan bygga en hemsida" },
  { slug: "ai-copywriting", label: "AI-copywriting för hemsida", targetKeyword: "ai copywriting hemsida", searchIntent: "hur AI skriver texter till en hemsida" },
  { slug: "ai-design-hemsida", label: "AI-design hemsida", targetKeyword: "ai design hemsida", searchIntent: "hur AI designar en hemsida" },
  { slug: "ai-logotyp-hemsida", label: "AI-logotyp och hemsida", targetKeyword: "ai logotyp hemsida", searchIntent: "AI-genererad logotyp tillsammans med hemsida" },
  { slug: "ai-bilder-hemsida", label: "AI-bilder för hemsida", targetKeyword: "ai bilder hemsida", searchIntent: "hur man får AI-bilder på sin hemsida" },
  { slug: "ai-seo-hemsida", label: "AI-SEO för hemsida", targetKeyword: "ai seo hemsida", searchIntent: "hur AI kan optimera en hemsida för sök" },
  { slug: "ai-hemsida-utan-kod", label: "AI-hemsida utan kod", targetKeyword: "ai hemsida utan kod", searchIntent: "no-code AI-hemsida" },
  { slug: "ai-hemsida-svenska", label: "AI-hemsida på svenska", targetKeyword: "ai hemsida på svenska", searchIntent: "AI som skriver hemsida på svenska" },
  { slug: "ai-hemsida-frilansare", label: "AI-hemsida för frilansare", targetKeyword: "ai hemsida frilansare", searchIntent: "frilansare som bygger hemsida med AI" },
  { slug: "ai-hemsida-startup", label: "AI-hemsida för startup", targetKeyword: "ai hemsida startup", searchIntent: "startups som använder AI för hemsidor" },
  { slug: "ai-hemsida-sma-foretag", label: "AI-hemsida för små företag", targetKeyword: "ai hemsida små företag", searchIntent: "små företag som bygger hemsida med AI" },
  { slug: "ai-webbyra", label: "AI-webbyrå", targetKeyword: "ai webbyrå", searchIntent: "om man kan ersätta en webbyrå med AI" },
  { slug: "ai-hemsida-kostnad", label: "AI-hemsida kostnad", targetKeyword: "ai hemsida kostnad", searchIntent: "vad en AI-hemsida kostar" },
];

/* ── Konkurrent-jämförelser (15 st) ──────────────────────────────── */

export const SEO_COMPARE: SeoCompareConfig[] = [
  { slug: "wix", label: "Wix", targetKeyword: "alternativ till wix", competitorSummary: "klassisk drag-and-drop webbplatsbyggare" },
  { slug: "squarespace", label: "Squarespace", targetKeyword: "alternativ till squarespace", competitorSummary: "mall-driven byggare populär för portfolios och småföretag" },
  { slug: "webflow", label: "Webflow", targetKeyword: "alternativ till webflow", competitorSummary: "avancerad visuell byggare för designers" },
  { slug: "shopify", label: "Shopify", targetKeyword: "alternativ till shopify", competitorSummary: "e-handelsplattform för webshoppar" },
  { slug: "framer", label: "Framer", targetKeyword: "alternativ till framer", competitorSummary: "design-first byggare som kombinerar Figma och webb" },
  { slug: "duda", label: "Duda", targetKeyword: "alternativ till duda", competitorSummary: "byråfokuserad byggare med white-label" },
  { slug: "tilda", label: "Tilda", targetKeyword: "alternativ till tilda", competitorSummary: "blockbaserad byggare från Ryssland, populär i Norden" },
  { slug: "elementor", label: "Elementor", targetKeyword: "alternativ till elementor", competitorSummary: "WordPress-plugin för drag-and-drop redigering" },
  { slug: "wordpress", label: "WordPress", targetKeyword: "alternativ till wordpress", competitorSummary: "traditionellt CMS med plugin-ekosystem" },
  { slug: "jimdo", label: "Jimdo", targetKeyword: "alternativ till jimdo", competitorSummary: "enklare tysk byggare med AI-assistans" },
  { slug: "godaddy", label: "GoDaddy", targetKeyword: "alternativ till godaddy", competitorSummary: "domänförsäljare med bonusbyggare" },
  { slug: "weebly", label: "Weebly", targetKeyword: "alternativ till weebly", competitorSummary: "äldre mall-byggare, numera del av Square" },
  { slug: "one-se", label: "One.com", targetKeyword: "alternativ till one.com", competitorSummary: "populär svensk/skandinavisk webbhotells- och byggare" },
  { slug: "loopia", label: "Loopia", targetKeyword: "alternativ till loopia", competitorSummary: "svensk webbhotellleverantör med sajtbyggare" },
  { slug: "v0", label: "v0", targetKeyword: "alternativ till v0", competitorSummary: "AI-baserat UI/komponent-verktyg från Vercel" },
];

/* ── Stad × Användningsområde (top-20 städer × top-10 typer = 200) ── */

const CITY_USECASE_CITY_SLUGS = [
  "stockholm", "goteborg", "malmo", "uppsala", "vasteras", "orebro",
  "linkoping", "helsingborg", "jonkoping", "norrkoping", "lund", "umea",
  "gavle", "boras", "eskilstuna", "sodertalje", "karlstad", "vaxjo",
  "halmstad", "sundsvall",
] as const;

const CITY_USECASE_USECASE_SLUGS = [
  "webshop", "restaurang", "salong", "portfolio", "foretag",
  "konsult", "bygg", "bilverkstad", "fotograf", "event",
] as const;

function buildCityUsecaseConfigs(): SeoCityUsecaseConfig[] {
  const configs: SeoCityUsecaseConfig[] = [];
  const cityBySlug = new Map(SEO_CITIES.map((c) => [c.slug, c]));
  const usecaseBySlug = new Map(SEO_USECASES.map((u) => [u.slug, u]));

  for (const citySlug of CITY_USECASE_CITY_SLUGS) {
    for (const usecaseSlug of CITY_USECASE_USECASE_SLUGS) {
      const city = cityBySlug.get(citySlug);
      const usecase = usecaseBySlug.get(usecaseSlug);
      if (!city || !usecase) continue;
      configs.push({
        slug: `${citySlug}/${usecaseSlug}`,
        citySlug,
        usecaseSlug,
        cityLabel: city.label,
        usecaseLabel: usecase.label,
        targetKeyword: `hemsida ${usecase.label.toLowerCase()} ${city.label.toLowerCase()}`,
      });
    }
  }

  return configs;
}

export const SEO_CITY_USECASES: SeoCityUsecaseConfig[] = buildCityUsecaseConfigs();

/* ── Populära slugs för intern länk-graf ─────────────────────────── */

export const POPULAR_CITY_SLUGS = [
  "stockholm", "goteborg", "malmo", "uppsala", "vasteras", "orebro",
  "linkoping", "helsingborg", "jonkoping", "norrkoping", "lund", "umea",
  "gavle", "boras", "eskilstuna", "sodertalje", "karlstad", "vaxjo",
  "halmstad", "sundsvall",
] as const;

export const POPULAR_USECASE_SLUGS = [
  "webshop", "restaurang", "salong", "portfolio", "foretag",
  "konsult", "bygg", "bilverkstad", "fotograf", "event",
] as const;

/* ── Helpers ─────────────────────────────────────────────────────── */

/**
 * Returnerar alla SEO-konfigurationer som flat-list för att iterera vid
 * generering/sitemap.
 */
export function listAllSeoSlugs(): Array<{
  family: "city" | "usecase" | "industry" | "ai" | "compare" | "city-usecase";
  slug: string;
}> {
  return [
    ...SEO_CITIES.map((c) => ({ family: "city" as const, slug: c.slug })),
    ...SEO_USECASES.map((u) => ({ family: "usecase" as const, slug: u.slug })),
    ...SEO_INDUSTRIES.map((i) => ({ family: "industry" as const, slug: i.slug })),
    ...SEO_AI_VARIANTS.map((a) => ({ family: "ai" as const, slug: a.slug })),
    ...SEO_COMPARE.map((c) => ({ family: "compare" as const, slug: c.slug })),
    ...SEO_CITY_USECASES.map((cu) => ({ family: "city-usecase" as const, slug: cu.slug })),
  ];
}

/** URL för en SEO-landning. */
export function hrefForSeoLanding(
  family: "city" | "usecase" | "industry" | "ai" | "compare" | "city-usecase",
  slug: string,
): string {
  switch (family) {
    case "city":
      return `/hemsida/${slug}`;
    case "usecase":
      return `/skapa-hemsida/${slug}`;
    case "industry":
      return `/hemsida-for/${slug}`;
    case "ai":
      return `/ai-hemsida/${slug}`;
    case "compare":
      return `/alternativ-till/${slug}`;
    case "city-usecase":
      return `/hemsida/${slug}`;
  }
}
