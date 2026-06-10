"""Skelett-generator för industry-profiles.v1.json (ADR 0045).

Stdlib-only. Läser SNI 2025-spegeln + sni-discovery-map och skriver en
branschprofil per SNI-huvudgrupp (87 st) till
``governance/policies/industry-profiles.v1.json``.

Merge-semantik (säker att köra om):

- Befintliga profiler i policyn skrivs ALDRIG över — kurerat innehåll
  är operatörens och bevaras byte-för-byte.
- Saknade huvudgrupper får ett skelett: kategori-defaults från
  ``CATEGORY_DEFAULTS`` (märkt ``curated: false``) eller, om huvudgruppen
  finns i ``DIVISION_SEEDS``, ett kurerat branschinnehåll
  (märkt ``curated: true``).
- ``--check`` validerar bara täckningen (exit 1 om någon huvudgrupp
  saknar profil) utan att skriva.

Kurering sker därefter direkt i policy-JSON (sätt ``curated: true`` och
bumpa policy-version). DIVISION_SEEDS är engångs-frö för första
kureringsbatchen, inte en levande källa — policy-filen är sanningen.

Körs från repo-roten::

    python scripts/generate_industry_profiles.py
    python scripts/generate_industry_profiles.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SNI_TAXONOMY_PATH = REPO_ROOT / "data" / "taxonomies" / "sni" / "sni-2025.v1.json"
SNI_MAP_PATH = REPO_ROOT / "governance" / "policies" / "sni-discovery-map.v1.json"
POLICY_PATH = REPO_ROOT / "governance" / "policies" / "industry-profiles.v1.json"

POLICY_PURPOSE = (
    "En branschprofil per SNI-huvudgrupp (ADR 0045) som beskriver vad branschens "
    "hemsida behöver — extra capabilities, rekommenderade sidor, copy-vinkel, "
    "trust-signaler, primär CTA och bildspråk. Profilen berikar kategorins "
    "discovery-taxonomy-defaults; den väljer aldrig scaffold/variant/starter/"
    "Dossier. Konsumeras av Discovery Resolver (answers.sniCode) och wizardens "
    "branschsök-prefill."
)

POLICY_PRINCIPLES = [
    "Profilen är en mjuk berikning — Discovery Taxonomy äger fortsatt scaffold/variant/starter/capabilities-grunden.",
    "wizardCategoryId i profilen måste matcha sni-discovery-map-resolutionen för samma huvudgrupp (testlåst).",
    "extraCapabilities använder bara canonical slugs ur capability-map.v1.json (testlåst).",
    "curated: false betyder ärligt skelett med kategori-defaults; ingen påhittad branschkunskap.",
    "Kurering sker i policy-JSON i batchar per SNI-avdelning; generatorn skriver aldrig över befintliga profiler.",
]

# ---------------------------------------------------------------------------
# Kategori-defaults — ärliga baslinjer per wizardCategoryId.
# Capability-slugs måste finnas i capability-map.v1.json.
# primaryCta måste vara en av wizardens CTA-etiketter.
# ---------------------------------------------------------------------------

CATEGORY_DEFAULTS: dict[str, dict[str, Any]] = {
    "business": {
        "copyAngle": "Tydlig presentation av tjänster och en enkel väg till kontakt.",
        "toneHints": ["förtroendeingivande", "rak"],
        "trustSignals": ["F-skattsedel", "Organisationsnummer synligt", "Referenser"],
        "primaryCta": "Kontakta oss",
        "extraCapabilities": ["contact-form", "hours", "location"],
        "recommendedPages": ["Startsida / Hero", "Tjänster", "Kontaktformulär", "Karta / Hitta hit"],
        "imageryHints": ["verksamhetsmiljö", "medarbetare i arbete"],
    },
    "ecommerce": {
        "copyAngle": "Produkterna i fokus med tydlig väg till köp och trygga villkor.",
        "toneHints": ["säljande", "tydlig"],
        "trustSignals": ["Trygg betalning", "Leverans- och returvillkor", "Kundrecensioner"],
        "primaryCta": "Köp nu",
        "extraCapabilities": ["payments", "gallery", "reviews"],
        "recommendedPages": ["Webshop / Produkter", "Kundrecensioner", "Leverans & retur", "Kontaktformulär"],
        "imageryHints": ["produktbilder i enhetligt ljus"],
    },
    "restaurant": {
        "copyAngle": "Atmosfär och meny i centrum med enkel bokning.",
        "toneHints": ["varm", "inbjudande"],
        "trustSignals": ["Aktuella öppettider", "Allergiinformation", "Gästrecensioner"],
        "primaryCta": "Boka tid",
        "extraCapabilities": ["menu", "booking", "hours", "location", "gallery"],
        "recommendedPages": ["Meny / Matsedel", "Bokning online", "Karta / Hitta hit", "Bildgalleri"],
        "imageryHints": ["maträtter i närbild", "lokalens atmosfär"],
    },
    "portfolio": {
        "copyAngle": "Verken talar — minimal text, maximal visning av arbete.",
        "toneHints": ["personlig", "avskalad"],
        "trustSignals": ["Utvalda verk", "Utställningar / publikationer"],
        "primaryCta": "Kontakta oss",
        "extraCapabilities": ["gallery", "contact-form"],
        "recommendedPages": ["Portfolio / Case", "Om oss / Om mig", "Kontaktformulär"],
        "imageryHints": ["egna verk i hög upplösning"],
    },
    "landing": {
        "copyAngle": "Ett budskap, en handling — allt på en sida.",
        "toneHints": ["koncis"],
        "trustSignals": ["Socialt bevis", "Tydligt erbjudande"],
        "primaryCta": "Registrera dig",
        "extraCapabilities": ["contact-form", "newsletter-subscribe"],
        "recommendedPages": ["Startsida / Hero", "Nyhetsbrev"],
        "imageryHints": ["en stark hjältebild"],
    },
    "blog": {
        "copyAngle": "Innehållet är produkten — läsbarhet och prenumeration först.",
        "toneHints": ["redaktionell"],
        "trustSignals": ["Publiceringsrytm", "Om redaktionen"],
        "primaryCta": "Registrera dig",
        "extraCapabilities": ["newsletter-subscribe", "contact-form"],
        "recommendedPages": ["Blogg / Nyheter", "Nyhetsbrev", "Om oss / Om mig"],
        "imageryHints": ["artikelbilder med enhetlig ton"],
    },
    "consulting": {
        "copyAngle": "Expertis och resultat — kundcase som bevis, enkel offertväg.",
        "toneHints": ["professionell", "koncis"],
        "trustSignals": ["Kundcase med resultat", "Branschexpertis", "Referenskunder"],
        "primaryCta": "Begär offert",
        "extraCapabilities": ["contact-form", "team-section", "faq-section"],
        "recommendedPages": ["Portfolio / Case", "Vårt team", "Kontaktformulär"],
        "imageryHints": ["arbetsmöten", "resultatpresentationer"],
    },
    "tech": {
        "copyAngle": "Produktnyttan först, teknisk trovärdighet direkt efter.",
        "toneHints": ["modern", "självsäker"],
        "trustSignals": ["Referenskunder", "Säkerhet & GDPR", "Uptime / support"],
        "primaryCta": "Registrera dig",
        "extraCapabilities": ["contact-form", "faq-section", "newsletter-subscribe"],
        "recommendedPages": ["Startsida / Hero", "FAQ", "Nyhetsbrev", "Kontaktformulär"],
        "imageryHints": ["produkt-screenshots", "teamet bakom"],
    },
    "healthcare": {
        "copyAngle": "Trygghet och tillgänglighet före allt — boka enkelt, känn dig sedd.",
        "toneHints": ["lugn", "omhändertagande"],
        "trustSignals": ["Legitimerad personal", "Patientsäkerhet", "Sekretess"],
        "primaryCta": "Boka tid",
        "extraCapabilities": ["booking", "contact-form", "hours", "location", "faq-section"],
        "recommendedPages": ["Bokning online", "Behandlingar", "FAQ", "Karta / Hitta hit"],
        "imageryHints": ["ljusa lokaler", "personal i möte med patient"],
    },
    "realestate": {
        "copyAngle": "Objekt och områdeskännedom i fokus — personlig kontakt nära.",
        "toneHints": ["förtroendeingivande", "lokal"],
        "trustSignals": ["Registrerad mäklare", "Områdeskännedom", "Nöjda säljare"],
        "primaryCta": "Kontakta oss",
        "extraCapabilities": ["contact-form", "gallery", "team-section"],
        "recommendedPages": ["Bildgalleri", "Vårt team", "Kontaktformulär"],
        "imageryHints": ["objektfoton", "områdesbilder"],
    },
    "salon": {
        "copyAngle": "Resultat och stämning — visa arbetet, gör bokningen självklar.",
        "toneHints": ["personlig", "varm"],
        "trustSignals": ["Certifierade behandlare", "Produktmärken", "Kundomdömen"],
        "primaryCta": "Boka tid",
        "extraCapabilities": ["booking", "pricing", "gallery", "hours"],
        "recommendedPages": ["Bokning online", "Prislista", "Bildgalleri", "Karta / Hitta hit"],
        "imageryHints": ["före/efter-resultat", "salongsmiljö"],
    },
    "fitness": {
        "copyAngle": "Energi och gemenskap — sänk tröskeln till första passet.",
        "toneHints": ["energisk", "peppande"],
        "trustSignals": ["Certifierade instruktörer", "Prova-på-erbjudande", "Medlemsomdömen"],
        "primaryCta": "Registrera dig",
        "extraCapabilities": ["pricing", "booking", "contact-form", "hours"],
        "recommendedPages": ["Prislista", "Schema / Pass", "Bokning online", "Kontaktformulär"],
        "imageryHints": ["träning i rörelse", "lokalerna"],
    },
    "construction": {
        "copyAngle": "Referensjobb och trygghet — offert utan krångel.",
        "toneHints": ["rak", "pålitlig"],
        "trustSignals": ["F-skattsedel", "Försäkring & garantier", "ID06", "Referensprojekt"],
        "primaryCta": "Begär offert",
        "extraCapabilities": ["contact-form", "gallery", "guarantees"],
        "recommendedPages": ["Portfolio / Case", "Tjänster", "Kontaktformulär"],
        "imageryHints": ["färdiga projekt", "hantverkare i arbete"],
    },
    "education": {
        "copyAngle": "Resultat och pedagogik — gör nästa steg (anmälan) tydligt.",
        "toneHints": ["pedagogisk", "uppmuntrande"],
        "trustSignals": ["Behöriga lärare", "Resultat / omdömen", "Tydlig kursplan"],
        "primaryCta": "Registrera dig",
        "extraCapabilities": ["contact-form", "faq-section"],
        "recommendedPages": ["Kurser / Program", "FAQ", "Kontaktformulär"],
        "imageryHints": ["undervisningssituationer"],
    },
    "event": {
        "copyAngle": "Känslan av eventet — visa tidigare produktioner, förenkla förfrågan.",
        "toneHints": ["festlig", "professionell"],
        "trustSignals": ["Genomförda event", "Kundomdömen", "Tydlig process"],
        "primaryCta": "Begär offert",
        "extraCapabilities": ["booking", "gallery", "contact-form"],
        "recommendedPages": ["Bildgalleri", "Tjänster", "Kontaktformulär"],
        "imageryHints": ["event i full gång", "detaljer och dukningar"],
    },
    "nonprofit": {
        "copyAngle": "Uppdraget främst — visa vad engagemang och stöd leder till.",
        "toneHints": ["engagerande", "transparent"],
        "trustSignals": ["Organisationsnummer", "90-konto", "Årsredovisning"],
        "primaryCta": "Registrera dig",
        "extraCapabilities": ["contact-form", "newsletter-subscribe"],
        "recommendedPages": ["Om oss / Om mig", "Engagera dig", "Nyhetsbrev"],
        "imageryHints": ["verksamheten i fält", "medlemmar"],
    },
    "music": {
        "copyAngle": "Ljudet och scenen i centrum — musik, datum, kontakt.",
        "toneHints": ["personlig", "atmosfärisk"],
        "trustSignals": ["Spelningar / releaser", "Press / omnämnanden"],
        "primaryCta": "Kontakta oss",
        "extraCapabilities": ["gallery", "hero-video", "newsletter-subscribe"],
        "recommendedPages": ["Musik / Releaser", "Spelningar", "Kontaktformulär"],
        "imageryHints": ["livebilder", "studiomiljö"],
    },
    "hotel": {
        "copyAngle": "Vistelsen säljer sig visuellt — rum, läge och enkel bokning.",
        "toneHints": ["välkomnande", "lugn"],
        "trustSignals": ["Recensionsbetyg", "Avbokningsvillkor", "Läge"],
        "primaryCta": "Boka tid",
        "extraCapabilities": ["booking", "gallery", "location", "faq-section"],
        "recommendedPages": ["Rum & Priser", "Bokning online", "Bildgalleri", "Karta / Hitta hit"],
        "imageryHints": ["rum i dagsljus", "omgivningen"],
    },
    "legal": {
        "copyAngle": "Specialisering och sekretess — sänk tröskeln för första kontakten.",
        "toneHints": ["saklig", "förtroendeingivande"],
        "trustSignals": ["Advokatsamfundet", "Specialisering", "Sekretess"],
        "primaryCta": "Kontakta oss",
        "extraCapabilities": ["contact-form", "team-section", "faq-section"],
        "recommendedPages": ["Rättsområden", "Vårt team", "Kontaktformulär"],
        "imageryHints": ["kontorsmiljö", "rådgivningsmöte"],
    },
    "accounting": {
        "copyAngle": "Ordning och proaktivitet — visa vad kunden slipper tänka på.",
        "toneHints": ["saklig", "trygg"],
        "trustSignals": ["Auktoriserad redovisningskonsult", "SRF/FAR-medlemskap", "Digitala arbetssätt"],
        "primaryCta": "Begär offert",
        "extraCapabilities": ["contact-form", "pricing", "faq-section"],
        "recommendedPages": ["Tjänster", "Prislista", "FAQ", "Kontaktformulär"],
        "imageryHints": ["rådgivningsmöte", "lugn kontorsmiljö"],
    },
    "auto": {
        "copyAngle": "Snabb hjälp och tydliga priser — gör verkstadsbesöket enkelt.",
        "toneHints": ["rak", "hjälpsam"],
        "trustSignals": ["Auktoriserad verkstad", "Garanti på arbete", "Transparent prissättning"],
        "primaryCta": "Boka tid",
        "extraCapabilities": ["contact-form", "booking", "hours", "location"],
        "recommendedPages": ["Tjänster", "Bokning online", "Karta / Hitta hit"],
        "imageryHints": ["verkstaden i arbete"],
    },
    "travel": {
        "copyAngle": "Resan börjar på sajten — inspiration först, trygghet i villkoren.",
        "toneHints": ["inspirerande", "trygg"],
        "trustSignals": ["Resegaranti", "Paketreselagen", "Resenärsomdömen"],
        "primaryCta": "Boka tid",
        "extraCapabilities": ["booking", "gallery", "faq-section"],
        "recommendedPages": ["Resor / Upplevelser", "Bildgalleri", "FAQ", "Kontaktformulär"],
        "imageryHints": ["resmål i naturligt ljus"],
    },
    "food": {
        "copyAngle": "Råvaror och hantverk — visa maten, förenkla beställningen.",
        "toneHints": ["aptitlig", "personlig"],
        "trustSignals": ["Egenkontroll livsmedel", "Allergihantering", "Lokala råvaror"],
        "primaryCta": "Begär offert",
        "extraCapabilities": ["menu", "contact-form", "gallery"],
        "recommendedPages": ["Meny / Matsedel", "Bildgalleri", "Kontaktformulär"],
        "imageryHints": ["mat i närbild", "tillagning"],
    },
    "photo": {
        "copyAngle": "Bilderna är beviset — portfölj främst, paket och pris nära.",
        "toneHints": ["visuell", "personlig"],
        "trustSignals": ["Portfölj", "Leveranstid", "Kundomdömen"],
        "primaryCta": "Begär offert",
        "extraCapabilities": ["gallery", "pricing", "contact-form"],
        "recommendedPages": ["Portfolio / Case", "Prislista", "Kontaktformulär"],
        "imageryHints": ["egna foton i hög upplösning"],
    },
    "other": {
        "copyAngle": "Tydlighet före allt — vad verksamheten gör och hur man hör av sig.",
        "toneHints": ["neutral"],
        "trustSignals": ["Organisationsnummer synligt"],
        "primaryCta": "Kontakta oss",
        "extraCapabilities": ["contact-form"],
        "recommendedPages": ["Startsida / Hero", "Kontaktformulär"],
        "imageryHints": ["verksamhetsmiljö"],
    },
}

# ---------------------------------------------------------------------------
# Första kureringsbatchen — branschspecifikt innehåll per huvudgrupp.
# Engångs-frö: körs bara in när huvudgruppen saknas i policyn.
# Nycklar som utelämnas faller tillbaka på kategori-defaulten.
# ---------------------------------------------------------------------------

DIVISION_SEEDS: dict[str, dict[str, Any]] = {
    "01": {
        "copyAngle": "Gårdens berättelse och produkter — närproducerat med ansikte.",
        "trustSignals": ["KRAV / EU-ekologiskt", "Gårdsförsäljning", "Öppen gård"],
        "recommendedPages": ["Startsida / Hero", "Gårdsbutik", "Om gården", "Karta / Hitta hit"],
        "imageryHints": ["gården och markerna", "djur och odling", "produkter"],
    },
    "10": {
        "copyAngle": "Hantverk och råvaror i fokus — från recept till leverans.",
        "trustSignals": ["Egenkontroll livsmedel", "Lokala råvaror", "Återförsäljare"],
        "recommendedPages": ["Produkter", "Återförsäljare", "Om oss / Om mig", "Kontaktformulär"],
        "imageryHints": ["produktionen", "färdiga produkter i närbild"],
    },
    "16": {
        "copyAngle": "Trähantverk med precision — visa materialkänslan och referensjobben.",
        "trustSignals": ["Certifierat virke", "Referensprojekt", "Leveranstider"],
        "imageryHints": ["verkstaden", "träets detaljer"],
    },
    "18": {
        "copyAngle": "Från fil till färdigt tryck — kvalitet, upplagor och snabba svar.",
        "trustSignals": ["Provtryck", "Miljömärkt tryck", "Leveranstider"],
        "recommendedPages": ["Tjänster", "Portfolio / Case", "Begär offert"],
        "imageryHints": ["pressar och produktion", "trycksaker i närbild"],
    },
    "31": {
        "copyAngle": "Möbler med hantverkskänsla — material, mått och beställningsväg.",
        "trustSignals": ["Massivt material", "Måttanpassning", "Referenskunder"],
        "imageryHints": ["möbler i miljö", "verkstadsdetaljer"],
    },
    "33": {
        "copyAngle": "Maskinerna ska rulla — snabb service, tydliga avtal.",
        "trustSignals": ["Servicetekniker med certifikat", "Jourservice", "Serviceavtal"],
        "recommendedPages": ["Tjänster", "Serviceavtal", "Kontaktformulär"],
        "imageryHints": ["tekniker i arbete"],
    },
    "38": {
        "copyAngle": "Återvinning som gör skillnad — enkla flöden för hämtning och sortering.",
        "trustSignals": ["Miljötillstånd", "Spårbarhet", "Avfallstrappan"],
        "recommendedPages": ["Tjänster", "Hämtning / Beställning", "Kontaktformulär"],
        "imageryHints": ["sorterings- och återvinningsmiljö"],
    },
    "41": {
        "copyAngle": "Byggprojekt från grund till nyckel — referenser och trygg process.",
        "trustSignals": ["F-skattsedel", "Försäkring & garantier", "ID06", "Referensprojekt"],
        "recommendedPages": ["Portfolio / Case", "Tjänster", "Begär offert", "Kontaktformulär"],
        "imageryHints": ["pågående byggen", "färdiga hus"],
    },
    "42": {
        "copyAngle": "Anläggning med maskinkraft — kapacitet, referenser, snabb offert.",
        "trustSignals": ["Maskinpark", "Trafikverket-erfarenhet", "Försäkring & garantier"],
        "imageryHints": ["maskiner i arbete", "färdig mark och vägar"],
    },
    "43": {
        "copyAngle": "Specialisthantverk — visa yrkesbeviset och de senaste jobben.",
        "trustSignals": ["Behörigheter (el/VVS)", "Säker Vatten / branschregler", "Garantier", "ID06"],
        "recommendedPages": ["Tjänster", "Portfolio / Case", "Begär offert"],
        "imageryHints": ["hantverkare i arbete", "före/efter"],
    },
    "46": {
        "copyAngle": "Sortiment och leveranssäkerhet för företagskunder — B2B utan friktion.",
        "trustSignals": ["Leveranssäkerhet", "Sortimentbredd", "Återförsäljaravtal"],
        "recommendedPages": ["Sortiment", "Bli kund", "Kontaktformulär"],
        "imageryHints": ["lager och logistik", "produkter"],
    },
    "47": {
        "copyAngle": "Butikens utbud med köpkänsla — oavsett om köpet sker online eller i butik.",
        "trustSignals": ["Trygg betalning", "Öppet köp / byten", "Kundrecensioner"],
        "recommendedPages": ["Webshop / Produkter", "Butik & öppettider", "Kundrecensioner"],
        "imageryHints": ["produkter i enhetligt ljus", "butiksmiljö"],
    },
    "49": {
        "copyAngle": "Transporter i tid — kapacitet, områden och enkel bokningsväg.",
        "trustSignals": ["Trafiktillstånd", "Försäkrat gods", "Punktlighet"],
        "recommendedPages": ["Tjänster", "Områden", "Begär offert"],
        "imageryHints": ["fordon på väg", "lastning"],
    },
    "55": {
        "copyAngle": "Vistelsen säljer sig visuellt — rum, läge och enkel bokning.",
        "trustSignals": ["Recensionsbetyg", "Avbokningsvillkor", "Frukost & faciliteter"],
        "imageryHints": ["rum i dagsljus", "frukost och gemensamma ytor", "omgivningen"],
    },
    "56": {
        "copyAngle": "Atmosfär och meny i centrum — boka bord eller beställ direkt.",
        "trustSignals": ["Aktuella öppettider", "Allergiinformation", "Gästrecensioner"],
        "imageryHints": ["signaturrätter", "lokalens kvällsljus"],
    },
    "58": {
        "copyAngle": "Utgivningen i fokus — titlar, författare och prenumeration.",
        "trustSignals": ["Utgivningslista", "Recensioner / priser"],
        "recommendedPages": ["Titlar / Utgivning", "Nyhetsbrev", "Kontaktformulär"],
        "imageryHints": ["omslag i grid"],
    },
    "59": {
        "copyAngle": "Showreel först — låt produktionerna tala, gör förfrågan enkel.",
        "trustSignals": ["Showreel", "Produktionslista", "Samarbetspartners"],
        "recommendedPages": ["Portfolio / Case", "Tjänster", "Kontaktformulär"],
        "imageryHints": ["stillbilder ur produktioner", "bakom kulisserna"],
    },
    "62": {
        "copyAngle": "Teknisk spets utan floskler — vad ni bygger, för vem, med vilket resultat.",
        "trustSignals": ["Referenskunder", "Certifieringar (ISO/moln)", "Säkerhet & GDPR"],
        "recommendedPages": ["Tjänster", "Portfolio / Case", "Vårt team", "Kontaktformulär"],
        "imageryHints": ["teamet i arbete", "produkt-screenshots"],
    },
    "64": {
        "copyAngle": "Finansiell trygghet — tillstånd, process och personlig rådgivning.",
        "trustSignals": ["Finansinspektionens tillstånd", "Ansvarsförsäkring", "Sekretess"],
        "imageryHints": ["rådgivningsmöte", "lugn kontorsmiljö"],
    },
    "68": {
        "copyAngle": "Objekt och områdeskännedom i fokus — personlig mäklare nära.",
        "trustSignals": ["Registrerad fastighetsmäklare", "Områdesstatistik", "Nöjda säljare"],
        "imageryHints": ["objektfoton i dagsljus", "kvartersbilder"],
    },
    "69": {
        "copyAngle": "Specialisering och sekretess — rätt byrå för rätt ärende.",
        "trustSignals": ["Advokatsamfundet / auktorisation", "Specialisering", "Sekretess"],
        "notesSv": "Huvudgruppen spänner över juridik (691) och redovisning (692); profilen följer legal-defaulten medan 692-företag fångas av accounting-kategorin via group-override.",
    },
    "70": {
        "copyAngle": "Strategisk rådgivning med mätbara resultat — case före löften.",
        "trustSignals": ["Kundcase med resultat", "Seniora konsulter", "Branschexpertis"],
        "imageryHints": ["workshops", "presentationer"],
    },
    "71": {
        "copyAngle": "Teknisk precision — projekt, behörigheter och tydlig process.",
        "trustSignals": ["Certifierade ingenjörer/arkitekter", "Referensprojekt", "Ansvarsförsäkring"],
        "recommendedPages": ["Portfolio / Case", "Tjänster", "Vårt team", "Kontaktformulär"],
        "imageryHints": ["ritningar och modeller", "färdiga projekt"],
    },
    "73": {
        "copyAngle": "Kreativitet som konverterar — visa kampanjer och resultat.",
        "trustSignals": ["Kundcase med resultat", "Utmärkelser", "Långa kundrelationer"],
        "imageryHints": ["kampanjmaterial", "byråmiljö"],
    },
    "75": {
        "copyAngle": "Djurens trygghet först — legitimerad vård och enkel tidsbokning.",
        "trustSignals": ["Legitimerad veterinär", "Akuttider", "Försäkringsdirekt"],
        "recommendedPages": ["Bokning online", "Behandlingar", "Akut hjälp", "Karta / Hitta hit"],
        "imageryHints": ["djur och personal", "kliniken"],
    },
    "79": {
        "copyAngle": "Resan börjar på sajten — inspiration först, trygghet i villkoren.",
        "trustSignals": ["Resegaranti (Kammarkollegiet)", "Paketreselagen", "Resenärsomdömen"],
        "imageryHints": ["resmål i naturligt ljus", "resenärer på plats"],
    },
    "80": {
        "copyAngle": "Trygghet dygnet runt — auktorisation, snabb utryckning, tydliga avtal.",
        "trustSignals": ["Auktorisation (länsstyrelsen)", "Certifierad personal", "Jour dygnet runt"],
        "recommendedPages": ["Tjänster", "Avtal & priser", "Kontaktformulär"],
        "imageryHints": ["personal i uniform", "teknik och larm"],
    },
    "81": {
        "copyAngle": "Skötsel som syns — fasta avtal, pålitliga team, fina resultat.",
        "trustSignals": ["Kollektivavtal", "Försäkring", "Referensuppdrag"],
        "recommendedPages": ["Tjänster", "Avtal", "Begär offert"],
        "imageryHints": ["välskötta fastigheter och grönytor"],
    },
    "85": {
        "copyAngle": "Resultat och pedagogik — kursutbud med tydlig väg till anmälan.",
        "trustSignals": ["Behöriga lärare", "Kursresultat / omdömen", "Tydlig kursplan"],
        "recommendedPages": ["Kurser / Program", "Anmälan", "FAQ", "Kontaktformulär"],
        "imageryHints": ["undervisning i miljö", "elever/deltagare"],
    },
    "86": {
        "copyAngle": "Trygghet och tillgänglighet före allt — boka enkelt, känn dig sedd.",
        "trustSignals": ["Legitimerad personal", "Patientsäkerhet", "Sekretess", "Vårdgaranti"],
        "recommendedPages": ["Bokning online", "Behandlingar", "Priser & frikort", "FAQ"],
        "imageryHints": ["ljusa kliniklokaler", "personal i patientmöte"],
    },
    "90": {
        "copyAngle": "Konstnärskapet i centrum — verk, scenframträdanden och aktuella datum.",
        "trustSignals": ["Utställningar / uppsättningar", "Press / recensioner", "Stipendier"],
        "imageryHints": ["verk och scenbilder i hög upplösning"],
    },
    "93": {
        "copyAngle": "Energi och gemenskap — sänk tröskeln till första passet.",
        "trustSignals": ["Certifierade instruktörer", "Prova-på-erbjudande", "Medlemsomdömen"],
        "recommendedPages": ["Schema / Pass", "Prislista", "Bokning online", "Kontaktformulär"],
        "imageryHints": ["träning i rörelse", "gemenskap efter passet"],
    },
    "94": {
        "copyAngle": "Uppdraget främst — visa vad medlemskap och engagemang leder till.",
        "trustSignals": ["Organisationsnummer", "Årsredovisning", "Demokratisk styrning"],
        "recommendedPages": ["Om oss / Om mig", "Bli medlem", "Nyhetsbrev"],
        "imageryHints": ["medlemmar i aktivitet"],
    },
    "95": {
        "copyAngle": "Laga istället för slänga — snabb felsökning, ärliga priser.",
        "trustSignals": ["Garanti på reparationer", "Originaldelar", "Snabb återkoppling"],
        "recommendedPages": ["Tjänster", "Prislista", "Kontaktformulär"],
        "imageryHints": ["verkstadsbänk i arbete"],
    },
    "96": {
        "copyAngle": "Resultat och stämning — visa arbetet, gör bokningen självklar.",
        "trustSignals": ["Certifierade behandlare", "Hygienrutiner", "Kundomdömen"],
        "recommendedPages": ["Bokning online", "Prislista", "Bildgalleri", "Karta / Hitta hit"],
        "imageryHints": ["behandling i närbild", "salongsmiljö"],
    },
}

PROFILE_FIELD_ORDER = (
    "profileId",
    "sniCode",
    "labelSv",
    "wizardCategoryId",
    "curated",
    "copyAngle",
    "toneHints",
    "trustSignals",
    "primaryCta",
    "extraCapabilities",
    "recommendedPages",
    "imageryHints",
    "notesSv",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def division_rows() -> list[tuple[str, str]]:
    """(sniCode, labelSv) för alla huvudgrupper i SNI-spegeln."""
    taxonomy = load_json(SNI_TAXONOMY_PATH)
    return [
        (item["code"], item["labelSv"])
        for item in taxonomy["items"]
        if item["level"] == "division"
    ]


def division_category_map() -> dict[str, str]:
    """sniCode (huvudgrupp) -> wizardCategoryId enligt sni-discovery-map."""
    policy = load_json(SNI_MAP_PATH)
    return {
        row["sniCode"]: row["wizardCategoryId"]
        for row in policy["divisionMappings"]
    }


def build_profile(code: str, label: str, category_id: str) -> dict[str, Any]:
    defaults = CATEGORY_DEFAULTS.get(category_id, CATEGORY_DEFAULTS["other"])
    seed = DIVISION_SEEDS.get(code)
    merged: dict[str, Any] = dict(defaults)
    if seed:
        merged.update(seed)
    profile: dict[str, Any] = {
        "profileId": f"sni-{code}",
        "sniCode": code,
        "labelSv": label,
        "wizardCategoryId": category_id,
        "curated": seed is not None,
        **merged,
    }
    return {key: profile[key] for key in PROFILE_FIELD_ORDER if key in profile}


def generate(check_only: bool = False) -> int:
    categories = division_category_map()
    if POLICY_PATH.exists():
        policy = load_json(POLICY_PATH)
    else:
        policy = {
            "$schema": "../schemas/industry-profiles.schema.json",
            "policyId": "industry-profiles.v1",
            "version": 1,
            "status": "draft-but-authoritative",
            "purpose": POLICY_PURPOSE,
            "principles": POLICY_PRINCIPLES,
            "referenceTaxonomy": "data/taxonomies/sni/sni-2025.v1.json",
            "divisionProfiles": [],
        }

    existing = {row["sniCode"] for row in policy["divisionProfiles"]}
    missing: list[tuple[str, str]] = [
        (code, label)
        for code, label in division_rows()
        if code not in existing
    ]

    if check_only:
        if missing:
            print(
                f"FEL: {len(missing)} huvudgrupper saknar branschprofil: "
                f"{[code for code, _ in missing][:10]}",
                file=sys.stderr,
            )
            return 1
        print(f"OK: alla {len(existing)} huvudgrupper har branschprofil.")
        return 0

    for code, label in missing:
        category_id = categories.get(code)
        if category_id is None:
            print(
                f"FEL: huvudgrupp {code} saknas i sni-discovery-map — kör fas 1 först.",
                file=sys.stderr,
            )
            return 1
        policy["divisionProfiles"].append(build_profile(code, label, category_id))

    policy["divisionProfiles"].sort(key=lambda row: row["sniCode"])
    POLICY_PATH.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    curated = sum(1 for row in policy["divisionProfiles"] if row.get("curated"))
    print(
        f"Skrev {len(policy['divisionProfiles'])} profiler "
        f"({len(missing)} nya, {curated} kurerade) till {POLICY_PATH.relative_to(REPO_ROOT)}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validera bara täckningen utan att skriva.",
    )
    args = parser.parse_args()
    return generate(check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
