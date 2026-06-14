"""Viewser marketing site: pages, professions, cookies, legal and hero CTA."""

from __future__ import annotations

import json
import re

import pytest

from tests.support.viewser import VIEWSER_DIR


def test_b160_logo_image_has_explicit_auto_width() -> None:
    """B160: logon i ``site-header.tsx``, ``discovery-wizard.tsx`` och
    ``marketing-header.tsx`` renderas via next/image med höjden styrd av en
    Tailwind-klass (``h-7`` resp. ``h-[22px]``). Utan en inline ``style`` med
    ``width: "auto"`` varnar Next ("Image ... has either width or height
    modified, but not the other") eftersom Next läser inline-style, inte
    Tailwind-klassen ``w-auto``. Lås att ALLA tre logo-renderarna har
    ``style.width: "auto"`` så devtools-bruset/CLS-risken inte återkommer i
    någon header-yta.
    """
    for rel in (
        ("components", "layout", "site-header.tsx"),
        ("components", "discovery-wizard", "discovery-wizard.tsx"),
        ("components", "marketing", "marketing-header.tsx"),
    ):
        path = VIEWSER_DIR.joinpath(*rel)
        content = path.read_text(encoding="utf-8")
        assert 'src="/sajtbyggaren_logo.png"' in content, (
            f"{path.name} ska rendera sajtbyggaren-logon"
        )
        assert re.search(r'style=\{\{\s*width:\s*"auto"\s*\}\}', content), (
            f"{path.name}: logo-Image måste ha style={{ width: 'auto' }} "
            "för att tysta Next:s aspect-ratio-varning (B160)"
        )


# ----------------------------------------------------------------------
# Marknadssajt P0 (scout-marketing-site, 2026-06-01)
# Route-group-split: (marketing) äger "/", konsolen flyttad till
# (console)/studio. Minimal header/footer + serverad optimerad bild.
# ----------------------------------------------------------------------


def test_console_moved_to_studio_route_group() -> None:
    """Konsolen ska ligga i app/(console)/studio/page.tsx (flyttad från
    app/page.tsx) och fortfarande vara klient-konsolen — INTE kvar på "/".
    """
    old_path = VIEWSER_DIR / "app" / "page.tsx"
    new_path = VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx"
    assert not old_path.exists(), 'app/page.tsx ska vara flyttad — (marketing) äger nu "/"'
    assert new_path.exists(), "Konsolen ska bo i app/(console)/studio/page.tsx"
    console = new_path.read_text(encoding="utf-8")
    assert '"use client"' in console, "Konsol-sidan ska förbli en klientkomponent"
    # Regressionsvakt: ⌘K-listenern + build-wiringen ska ha följt med oförändrad.
    assert 'event.key !== "k"' in console, "⌘K-listenern ska ha följt med konsolen till studio"
    # (console)-layouten ska sätta noindex så konsolen aldrig indexeras publikt.
    console_layout = (VIEWSER_DIR / "app" / "(console)" / "layout.tsx").read_text(encoding="utf-8")
    assert "index: false" in console_layout, (
        "(console)/layout.tsx måste sätta robots index:false (noindex)"
    )


def test_marketing_header_has_exact_nav_items() -> None:
    """Marknads-headern ska ha exakt Hem/Produkt/Om oss + en primär bygg-CTA
    som pekar in i studion. Auth/billing (Priser-nav + login-entry) är PARKERAT
    i den här PR:en, så headern får inte importera auth-config eller rendera
    en login-/Priser-yta.
    """
    header = (VIEWSER_DIR / "components" / "marketing" / "marketing-header.tsx").read_text(
        encoding="utf-8"
    )
    for label in ('label: "Hem"', 'label: "Produkt"', 'label: "Om oss"'):
        assert label in header, f"Headern saknar nav-item {label}"
    assert 'label: "Priser"' not in header, (
        "Priser-nav är parkerat tillsammans med billing — får inte finnas i den här auth-fria PR:en"
    )
    assert "auth-config" not in header and "authHeaderEntry" not in header, (
        "Headern får inte importera auth-config-seamen i den här PR:en (parkerat)"
    )
    assert 'from "@/lib/routes"' in header and "STUDIO_HREF" in header, (
        "Bygg-CTA:n ska peka in i studion via den auth-fria route-konstanten"
    )


def test_marketing_header_centers_nav() -> None:
    """Operatörsönskemål (juni 2026): menyvalen ska ligga centrerat i headern."""
    header = (VIEWSER_DIR / "components" / "marketing" / "marketing-header.tsx").read_text(
        encoding="utf-8"
    )
    # Centrerad nav: absolut-centrerad via left-1/2 + -translate-x-1/2.
    assert "left-1/2" in header and "-translate-x-1/2" in header, (
        "Desktop-nav:en ska vara horisontellt centrerad i headern"
    )


def test_marketing_footer_has_legal_links() -> None:
    """Footern ska länka till de juridiska/hjälpsidor som byggs ut senare
    (de finns som platshållare i P0 så länkarna inte 404:ar).
    """
    footer = (VIEWSER_DIR / "components" / "marketing" / "marketing-footer.tsx").read_text(
        encoding="utf-8"
    )
    for href in ("/cookies", "/integritetspolicy", "/anvandarvillkor", "/kontakt"):
        assert f'href: "{href}"' in footer, f"Footern saknar länk till {href}"


def test_marketing_homepage_serves_optimized_image() -> None:
    """Startsidan ska rendera optimerade (WebP) yrkesbilder som faktiskt
    serveras från apps/viewser/public/Bilder — beviset på asset-pipelinen.
    P2: bilderna renderas via ProfessionGrid över det delade professions-
    registret i st.f. en hårdkodad <img> i page.tsx.
    """
    home = (VIEWSER_DIR / "app" / "(marketing)" / "page.tsx").read_text(encoding="utf-8")
    assert "ProfessionGrid" in home, "Startsidan ska rendera ProfessionGrid (bildväggen)"
    professions = (VIEWSER_DIR / "lib" / "professions.ts").read_text(encoding="utf-8")
    assert "/Bilder/bilmekaniker.webp" in professions, (
        "professions.ts ska peka på de optimerade WebP-bilderna"
    )
    served = VIEWSER_DIR / "public" / "Bilder" / "bilmekaniker.webp"
    assert served.exists(), (
        "Den optimerade bilden måste finnas i apps/viewser/public/Bilder "
        "(kör npm run assets:images)"
    )


def test_optimize_images_script_targets_served_public() -> None:
    """optimize-images.mjs ska läsa repo-root public/Bilder och skriva till
    apps/viewser/public/Bilder (den enda mapp Next.js serverar).
    """
    script = (VIEWSER_DIR / "scripts" / "optimize-images.mjs").read_text(encoding="utf-8")
    assert '"../../../public/Bilder"' in script, (
        "Scriptet ska läsa repo-root public/Bilder som källa"
    )
    assert '"../public/Bilder"' in script, (
        "Scriptet ska skriva till apps/viewser/public/Bilder (serverad mapp)"
    )


def test_marketing_header_has_active_state_and_mobile_menu() -> None:
    """P1: headern ska markera aktiv route (usePathname → aria-current) och
    ha en mobil Sheet-meny så nav:en aldrig trängs ihop på smal viewport.
    """
    header = (VIEWSER_DIR / "components" / "marketing" / "marketing-header.tsx").read_text(
        encoding="utf-8"
    )
    assert '"use client"' in header, (
        "Headern måste vara en klientkomponent för usePathname-aktivstate"
    )
    assert "usePathname" in header and 'aria-current={active ? "page"' in header, (
        "Headern ska härleda aktiv route och sätta aria-current=page"
    )
    assert "SheetTrigger" in header and "SheetContent" in header, (
        "Headern ska ha en mobil Sheet-meny (SheetTrigger/SheetContent)"
    )


def test_marketing_homepage_has_hero_and_sections() -> None:
    """P2: startsidan ska ha en video-hero (reduced-motion-säker) + de
    centrala scroll-sektionerna (så-funkar-det-steg, bildvägg, slut-CTA).
    """
    home = (VIEWSER_DIR / "app" / "(marketing)" / "page.tsx").read_text(encoding="utf-8")
    assert "HeroVideo" in home, "Startsidan ska rendera HeroVideo"
    assert "Så funkar det" in home, "Startsidan saknar 'Så funkar det'-sektionen"
    for step in ("Beskriv", "Bygg", "Förhandsgranska", "Förfina"):
        assert f'"{step}"' in home, f"Så-funkar-det saknar steget {step}"

    hero = (VIEWSER_DIR / "components" / "marketing" / "hero-video.tsx").read_text(encoding="utf-8")
    assert '"use client"' in hero, "HeroVideo måste vara klient (matchMedia)"
    assert "prefers-reduced-motion" in hero, (
        "HeroVideo måste respektera prefers-reduced-motion (still poster)"
    )
    assert "hero-poster.webp" in hero, "HeroVideo ska använda den committade poster-framen"
    poster = VIEWSER_DIR / "public" / "hero-poster.webp"
    assert poster.exists(), "hero-poster.webp måste finnas i apps/viewser/public"


def test_professions_registry_covers_all_images() -> None:
    """P2: det delade yrkesregistret ska täcka alla 20 optimerade bilder och
    varje slug ha en serverad WebP (grid + framtida /for/[yrke] delar källan).
    """
    professions = (VIEWSER_DIR / "lib" / "professions.ts").read_text(encoding="utf-8")
    slugs = re.findall(r'slug:\s*"([^"]+)"', professions)
    assert len(slugs) == 20, f"Förväntade 20 yrken, fann {len(slugs)}"
    bilder_dir = VIEWSER_DIR / "public" / "Bilder"
    for slug in slugs:
        assert (bilder_dir / f"{slug}.webp").exists(), f"Saknar optimerad bild för slug {slug}"


def test_profession_grid_is_interactive_living_wall() -> None:
    """P3: bildväggen ska vara en interaktiv FLIP-swap-wall (Framer Motion)
    som är reduced-motion-säker och pausar vid hover/fokus/dold flik/utanför
    viewport — annars glider en ruta bort från en klickare.
    """
    grid = (VIEWSER_DIR / "components" / "marketing" / "profession-grid.tsx").read_text(
        encoding="utf-8"
    )
    assert '"use client"' in grid, "Living wall måste vara klientkomponent"
    assert 'from "motion/react"' in grid, "Living wall ska använda Framer Motion (motion/react)"
    assert "motion.li" in grid and "layout" in grid, (
        "Tiles ska vara motion.li med layout-prop för FLIP-swap"
    )
    assert "useReducedMotion" in grid and "if (reduced) return" in grid, (
        "Auto-swap måste stängas av vid prefers-reduced-motion"
    )
    assert "IntersectionObserver" in grid and "document.hidden" in grid, (
        "Auto-swap ska pausa utanför viewport och när fliken är dold"
    )
    assert "onMouseEnter" in grid and "onFocusCapture" in grid, (
        "Auto-swap ska pausa vid hover och fokus"
    )
    # motion-depen ska vara deklarerad i package.json.
    pkg = json.loads((VIEWSER_DIR / "package.json").read_text(encoding="utf-8"))
    assert "motion" in pkg.get("dependencies", {}), (
        "motion (Framer Motion) ska vara en deklarerad dependency (D3)"
    )


def test_profession_landing_pages_are_static_and_seo() -> None:
    """P4: /for/[yrke] ska SSG:a alla 20 yrken (generateStaticParams),
    404:a okända slugs (dynamicParams=false + notFound) och ha per-yrke SEO
    (generateMetadata + OG-bild). Varje yrke ska ha headline + pitch.
    """
    page = (VIEWSER_DIR / "app" / "(marketing)" / "for" / "[yrke]" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "generateStaticParams" in page, "/for/[yrke] måste exportera generateStaticParams (SSG)"
    assert "export const dynamicParams = false" in page, (
        "Okända slugs ska inte renderas on-demand (dynamicParams=false)"
    )
    assert "notFound()" in page, "Okänd slug ska ge 404 via notFound()"
    assert "generateMetadata" in page and "openGraph" in page, (
        "/for/[yrke] måste ha per-yrke generateMetadata med OG-bild"
    )

    professions = (VIEWSER_DIR / "lib" / "professions.ts").read_text(encoding="utf-8")
    # Räkna bara fält med strängvärde (datat) — typdefinitionen
    # ``headline: string`` har inget citat och ska inte räknas med.
    assert len(re.findall(r'headline:\s*"', professions)) == 20, (
        "Alla 20 yrken måste ha en headline för landningssidan"
    )
    assert len(re.findall(r'pitch:\s*"', professions)) == 20, (
        "Alla 20 yrken måste ha en pitch för landningssidan"
    )

    # Bildväggen ska nu länka till landningssidorna, inte rakt in i studion.
    grid = (VIEWSER_DIR / "components" / "marketing" / "profession-grid.tsx").read_text(
        encoding="utf-8"
    )
    assert "href={`/for/${p.slug}`}" in grid, (
        "ProfessionGrid-tiles ska länka till /for/[slug] (P4-rewire)"
    )


def test_professions_have_starter_seed_mapping() -> None:
    """Starters-banan: varje yrke ska mappa till en verksamhetsfamilj +
    kategori + en svensk prompt-seed så landningssidans CTA kan förifylla
    DiscoveryWizarden. Alla 20 yrken måste ha alla tre fälten.
    """
    professions = (VIEWSER_DIR / "lib" / "professions.ts").read_text(encoding="utf-8")
    # Typerna ska komma från wizard-constants (samma källa som wizarden) så
    # familj/kategori aldrig driftar isär från BUSINESS_FAMILIES.
    assert "wizard-constants" in professions, (
        "professions.ts ska importera BusinessFamilyId/WizardCategoryId från "
        "discovery-wizard/wizard-constants"
    )
    assert len(re.findall(r"\bfamily:\s*\"", professions)) == 20, (
        "Alla 20 yrken måste ha en verksamhetsfamilj"
    )
    assert len(re.findall(r"\bcategory:\s*\"", professions)) == 20, (
        "Alla 20 yrken måste ha en kategori"
    )
    assert (
        len(re.findall(r"\bpromptSeed:\s*$", professions, re.MULTILINE))
        + len(re.findall(r"\bpromptSeed:\s*\"", professions))
        >= 20
    ), "Alla 20 yrken måste ha en promptSeed"


def test_profession_landing_cta_seeds_wizard_not_empty_studio() -> None:
    """Starters-banan: yrkessidans "Bygg din sida" ska gå via StarterCta som
    lämnar en wizard-seed (familj/kategori/prompt) i stället för att länka
    rakt till en TOM /studio. Seed:en får bara bära hints — aldrig starterId.
    """
    page = (VIEWSER_DIR / "app" / "(marketing)" / "for" / "[yrke]" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "StarterCta" in page, "/for/[yrke] ska använda StarterCta för bygg-knappen"
    assert "profession.promptSeed" in page and "profession.family" in page, (
        "StarterCta ska seedas från yrkets promptSeed + family/category"
    )

    cta = (VIEWSER_DIR / "components" / "marketing" / "starter-cta.tsx").read_text(encoding="utf-8")
    assert "setWizardSeed" in cta and "STUDIO_HREF" in cta, (
        "StarterCta ska lämna en wizard-seed och navigera till studion"
    )
    assert "starterId" not in cta, (
        "Starter-seed:en får inte sätta starterId (backend äger scaffold-valet)"
    )


def test_hero_has_starter_chips() -> None:
    """Starters-banan: heron ska visa klickbara starter-chips som förifyller
    prompten OCH förväljer verksamhet i wizarden (initialAnswers).
    """
    hero = (VIEWSER_DIR / "components" / "marketing" / "hero-prompt-form.tsx").read_text(
        encoding="utf-8"
    )
    assert "STARTER_PRESETS" in hero, "Heron ska rendera starter-presets som chips"
    assert "startWithPreset" in hero, (
        "Heron ska ha en preset-handler som förifyller prompt + familj"
    )
    assert "initialAnswers" in hero, (
        "Heron ska skicka förvalda svar till DiscoveryWizarden vid chip-klick"
    )


def test_about_page_has_founders_and_philosophy() -> None:
    """P5: /om-oss ska presentera båda grundarna (verbatim-roller) via
    FounderCard och den delade filosofin med slagordet.
    """
    about = (VIEWSER_DIR / "app" / "(marketing)" / "om-oss" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "FounderCard" in about, "/om-oss ska rendera grundarkort"
    assert "Jakob Eberg" in about and "Christopher Genberg" in about, (
        "Båda grundarna ska finnas med på /om-oss"
    )
    # Operatörens verbatim-beskrivningar.
    assert "AI-fantast och smått galen" in about, "Jakobs verbatim-roll ska stå kvar oförändrad"
    assert "Fullstack-utvecklare & bipolär" in about, (
        "Christophers verbatim-roll ska stå kvar oförändrad"
    )
    assert "Lämna huvudvärken att bygga och underhålla en hemsida med oss." in about, (
        "Slagordet ska finnas på /om-oss"
    )
    # Startsidans teaser (P2) ska länka in till /om-oss.
    home = (VIEWSER_DIR / "app" / "(marketing)" / "page.tsx").read_text(encoding="utf-8")
    assert 'href="/om-oss"' in home, "Startsidans grundar-teaser ska länka till /om-oss"


def test_marketing_layout_has_skip_link() -> None:
    """P1: marknads-layouten ska ha en skip-länk till #main-content (WCAG
    2.4.1) och ett main-landmärke med matchande id.
    """
    layout = (VIEWSER_DIR / "app" / "(marketing)" / "layout.tsx").read_text(encoding="utf-8")
    assert 'href="#main-content"' in layout, "Layouten saknar skip-länk till #main-content"
    assert 'id="main-content"' in layout, (
        'Layouten saknar <main id="main-content"> som skip-länken pekar på'
    )


def test_cookie_consent_provider_persists_versioned_choice() -> None:
    """P6: cookie-consent ska vara en klient-provider som läser/skriver ett
    versionerat localStorage-val via det sanktionerade async-IIFE-mönstret
    (await Promise.resolve() före setState) — inte synkront setState i effect.
    """
    consent = (VIEWSER_DIR / "components" / "marketing" / "cookie-consent.tsx").read_text(
        encoding="utf-8"
    )
    assert consent.lstrip().startswith('"use client"'), (
        "cookie-consent måste vara en klientkomponent"
    )
    assert "sajtbyggaren.cookie-consent.v1" in consent, (
        "Consent-nyckeln ska vara versionerad så den kan migreras senare"
    )
    assert '"granted"' in consent and '"denied"' in consent, (
        "Consent ska lagra explicit granted/denied"
    )
    assert "await Promise.resolve()" in consent, (
        "Storage-läsningen ska följa async-IIFE-mönstret (set-state-in-effect)"
    )
    assert "localStorage.setItem" in consent, "Valet ska persisteras i localStorage"
    assert "export function useCookieConsent" in consent, "useCookieConsent-hooken ska exporteras"


def test_cookie_banner_is_non_blocking_with_manager() -> None:
    """P6: cookie-baren ska vara icke-blockerande (role=region, ingen
    cookie-wall) med accept/avvisa och en manager-dialog som kan öppnas igen.
    """
    banner = (VIEWSER_DIR / "components" / "marketing" / "cookie-banner.tsx").read_text(
        encoding="utf-8"
    )
    assert 'role="region"' in banner, "Cookie-baren ska vara en region, inte en wall"
    assert "Acceptera alla" in banner and "Endast nödvändiga" in banner, (
        "Baren ska ge både accept och endast-nödvändiga"
    )
    assert "Dialog" in banner and "managerOpen" in banner, (
        "Managern ska vara en dialog som styrs av managerOpen"
    )
    assert "useCookieConsent" in banner, "Baren ska läsa consent-state via hooken"
    # Baren ska bara visas innan ett val gjorts (consent === null).
    assert "consent === null" in banner, "Baren ska bara visas tills ett val gjorts"

    layout = (VIEWSER_DIR / "app" / "(marketing)" / "layout.tsx").read_text(encoding="utf-8")
    assert "CookieConsentProvider" in layout and "CookieBanner" in layout, (
        "Layouten ska wrappa marknadssajten i provider + rendera baren"
    )


def test_footer_has_manage_cookies_trigger() -> None:
    """P6: footern ska ha en 'Hantera cookies'-trigger som öppnar managern."""
    footer = (VIEWSER_DIR / "components" / "marketing" / "marketing-footer.tsx").read_text(
        encoding="utf-8"
    )
    assert "ManageCookiesButton" in footer, "Footern ska rendera 'Hantera cookies'-knappen"
    button = (VIEWSER_DIR / "components" / "marketing" / "manage-cookies-button.tsx").read_text(
        encoding="utf-8"
    )
    assert "openManager" in button, "Knappen ska öppna cookie-managern via consent-hooken"


def test_legal_pages_use_shared_legal_layout() -> None:
    """P6: cookies/integritetspolicy/användarvillkor ska byggas på den delade
    LegalPageLayout-komponenten (konsekvent prose + utkast-notis).
    """
    layout = (VIEWSER_DIR / "components" / "marketing" / "legal-page-layout.tsx").read_text(
        encoding="utf-8"
    )
    assert "Senast uppdaterad" in layout, "Legal-layouten ska visa senast-uppdaterad"
    for slug in ("cookies", "integritetspolicy", "anvandarvillkor"):
        page = (VIEWSER_DIR / "app" / "(marketing)" / slug / "page.tsx").read_text(encoding="utf-8")
        assert "LegalPageLayout" in page, f"/{slug} ska använda den delade LegalPageLayout"
    # Kontaktsidan ska vara ärlig: mailto, inget fejkat formulär-flöde.
    contact = (VIEWSER_DIR / "app" / "(marketing)" / "kontakt" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "mailto:" in contact, (
        "Kontaktsidan ska länka till e-post (mailto) tills en backend finns"
    )


def test_marketing_hero_owns_build_cta() -> None:
    """u1: bygg-CTA:n ska bo på heron — besökaren beskriver sin sajt direkt
    där (HeroPromptForm) och slut-CTA:n scrollar tillbaka dit (#start),
    aldrig till studions tomma prompt-landning.
    """
    home = (VIEWSER_DIR / "app" / "(marketing)" / "page.tsx").read_text(encoding="utf-8")
    assert "HeroPromptForm" in home, (
        "Heron ska rendera HeroPromptForm (prompt direkt på startsidan)"
    )
    assert 'id="start"' in home and 'href="#start"' in home, (
        "Slut-CTA:n ska scrolla upp till hero-prompten (#start), inte studion"
    )


def test_hero_prompt_opens_wizard_and_hands_off_to_studio() -> None:
    """u1 (juni 2026): DiscoveryWizarden öppnas DIREKT på marknads-heron så
    besökaren stannar på den nya startsidan (hero + logotyp bakom popupen).
    Vid "Skapa sajt" lämnas hela wizard-resultatet över via wizard-handoffen
    och vi navigerar till studion, som bygger direkt utan en andra wizard.
    """
    form = (VIEWSER_DIR / "components" / "marketing" / "hero-prompt-form.tsx").read_text(
        encoding="utf-8"
    )
    assert "DiscoveryWizard" in form, "Heron ska rendera DiscoveryWizarden som popup på startsidan"
    assert "setWizardHandoff" in form and "STUDIO_HREF" in form, (
        "Heron ska lämna över hela wizard-resultatet och navigera till studion"
    )
    # Scout-fynd (P1, 2026-06-05): hero-textarean kan vara TOM när besökaren
    # öppnade wizarden direkt och bara fyllde "Vad gör ni?" där (answers.offer).
    # Handoffen måste falla tillbaka på offer-svaret så discovery.rawPrompt
    # aldrig blir "" — annars tappas "Operatörens beskrivning" ur master-prompten.
    assert "prompt.trim() || answers.offer.trim()" in form, (
        "Hero-handoffen måste falla tillbaka på wizardens offer-svar när hero-"
        'textarean är tom — annars blir discovery.rawPrompt "" och '
        "'Operatörens beskrivning' tappas ur master-prompten på /studio."
    )
    builder = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(encoding="utf-8")
    assert "consumeWizardHandoff" in builder, (
        "PromptBuildern ska konsumera wizard-handoffen vid mount"
    )
    assert "startBuildFromWizardHandoff" in builder, (
        "PromptBuildern ska bygga direkt från wizard-handoffen (ingen andra wizard i studion)"
    )


def test_marketing_has_sitemap_and_robots() -> None:
    """P8: SEO-finish — sitemap ska täcka statiska sidor + 20 yrkessidor;
    robots ska indexera marknaden men blockera /studio + /api.
    """
    sitemap = (VIEWSER_DIR / "app" / "sitemap.ts").read_text(encoding="utf-8")
    assert "PROFESSIONS" in sitemap, (
        "Sitemap ska generera per-yrke-sidor från professions-registret"
    )
    assert "/for/" in sitemap, "Sitemap ska inkludera /for/[yrke]-sidorna"

    robots = (VIEWSER_DIR / "app" / "robots.ts").read_text(encoding="utf-8")
    assert "/studio" in robots and "/api/" in robots, (
        "Robots ska blockera konsolen (/studio) och /api"
    )
    assert "sitemap" in robots, "Robots ska peka på sitemap.xml"


@pytest.mark.tooling
def test_viewer_panel_hero_respects_reduced_motion() -> None:
    """P2: studio-hero-videorna autoplayade alltid (ingen reduced-motion-
    respekt). Source-lock att autoPlay/loop gat:as mot en reducedMotion-flagga
    läst via useSyncExternalStore (samma kontrakt som marketing-hero:n)."""
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")
    assert "useSyncExternalStore" in text and "reducedMotion" in text, (
        "ViewerPanel ska läsa prefers-reduced-motion via useSyncExternalStore."
    )
    assert text.count("autoPlay={!reducedMotion}") >= 2, (
        "Båda hero-videorna (mobil + desktop) ska sluta autoplaya under reduced-motion."
    )


@pytest.mark.tooling
def test_assets_step_auto_hero_is_decoupled() -> None:
    """P2: auto-hero delade objektreferens med galleri-raden (alt/placement
    forkade tyst) och en galleri-borttagning nollade inte hero. Source-lock att
    kandidaten klonas och att hero nollas när dess källrad tas bort."""
    text = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "steps" / "assets-step.tsx"
    ).read_text(encoding="utf-8")
    assert "heroImage: { ...candidate }" in text, (
        "Auto-hero ska klona kandidaten så den inte delar referens med galleri-raden."
    )
    assert "heroFromThisRow" in text, (
        "Borttagning av en galleri-rad ska nolla hero om den auto-pickades därifrån."
    )
