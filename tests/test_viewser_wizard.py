"""Viewser discovery wizard, step validation, keyboard and dialog interactions."""

from __future__ import annotations

import json
import re

import pytest

from tests.support.viewser import REPO_ROOT, VIEWSER_DIR


@pytest.mark.tooling
def test_discovery_options_route_reads_taxonomy_and_omits_starter_id() -> None:
    text = (VIEWSER_DIR / "app" / "api" / "discovery-options" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert "discovery-taxonomy.v1.json" in text, (
        "Discovery-options-routen måste läsa Discovery Taxonomy server-side."
    )
    assert "scaffold-contract.v1.json" in text, (
        "Discovery-options-routen måste slå upp targetScaffoldLabel från "
        "scaffold-kontraktet istället för att hårdkoda UI-labels."
    )
    assert "expectedStarterId" not in text and "starterId" not in text, (
        "Discovery-options-routen får inte exponera starterId/expectedStarterId till frontend."
    )
    for field in (
        "id",
        "label",
        "contentBranch",
        "supportStatus",
        "defaultVariantId",
        "targetScaffoldLabel",
        "fallbackLabel",
    ):
        assert field in text, f"Discovery-options-routen saknar fältet {field!r}."


@pytest.mark.tooling
def test_b166_scrape_patch_merges_contact_and_brand_preserving_operator() -> None:
    """B166: 'Hämta från webbplats' får inte nolla operatörens ifyllda fält.

    Scrape-backenden (scripts/scrape_site.py:run) fyller alltid komplett
    contact-shape med tomma strängar för fält den inte hittade. En shallow
    spread av patchen (updateAnswers gör ``{ ...prev, ...next }``) skulle
    då ERSÄTTA hela contact/brand-objektet och tyst radera operatörens
    redan ifyllda öppettider/telefon/toneTags. Källåset kräver att
    foundation-step merge:ar nested objekt per subfält med operatörens
    värde som vinnare.
    """
    text = (
        VIEWSER_DIR
        / "components"
        / "discovery-wizard"
        / "steps"
        / "foundation-step.tsx"
    ).read_text(encoding="utf-8")
    assert "mergeNestedPreservingOperator" in text, (
        "foundation-step.tsx måste merge:a nested scrape-objekt per subfält "
        "(B166) — en wholesale-ersättning av contact/brand raderar "
        "operatörens ifyllda fält."
    )
    assert "patch.contact = mergeNestedPreservingOperator(" in text, (
        "Scrape-patchens contact måste gå genom nested-merge med "
        "answers.contact som bas (B166)."
    )
    assert "patch.brand = mergeNestedPreservingOperator(" in text, (
        "Scrape-patchens brand måste gå genom nested-merge med "
        "answers.brand som bas (B166)."
    )
    assert "if (operatorFilled) continue;" in text, (
        "Nested-mergen måste låta operatörens ifyllda värde VINNA över "
        "scrape-värdet (B166)."
    )


@pytest.mark.tooling
def test_discovery_options_route_exposes_recommended_pages_from_taxonomy() -> None:
    """Inbox msg-0056 punkt 1: /api/discovery-options ska exponera taxonomins
    recommendedPages per kategori så FunctionsStep kan hämta sidförslag från
    API:t med TS-cachen i wizard-constants som fallback (samma mönster som
    kategori-options idag)."""
    route = (VIEWSER_DIR / "app" / "api" / "discovery-options" / "route.ts").read_text(
        encoding="utf-8"
    )
    options_ts = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-options.ts"
    ).read_text(encoding="utf-8")

    assert "recommendedPages: asStringArray(category.recommendedPages)" in route, (
        "Discovery-options-routen ska exponera taxonomins recommendedPages "
        "per kategori (sanerade via asStringArray)."
    )
    assert "recommendedPages?: readonly string[]" in options_ts, (
        "discoveryOption-typen ska bära recommendedPages som optionellt fält "
        "så TS-cache-fallbacken (som saknar fältet) fortsätter typchecka."
    )

    taxonomy = json.loads(
        (REPO_ROOT / "governance" / "policies" / "discovery-taxonomy.v1.json").read_text(
            encoding="utf-8"
        )
    )
    for category in taxonomy["categories"]:
        pages = category.get("recommendedPages")
        assert isinstance(pages, list) and pages, (
            f"Kategori {category['id']!r} saknar recommendedPages i taxonomin — "
            "API-fältet skulle bli tomt för den kategorin."
        )


@pytest.mark.tooling
def test_discovery_wizard_uses_governance_options_with_ts_cache_fallback() -> None:
    wizard = (VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx").read_text(
        encoding="utf-8"
    )
    site_type = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "steps" / "site-type-step.tsx"
    ).read_text(encoding="utf-8")
    constants = (VIEWSER_DIR / "components" / "discovery-wizard" / "wizard-constants.ts").read_text(
        encoding="utf-8"
    )

    assert 'fetch("/api/discovery-options"' in wizard, (
        "DiscoveryWizard måste hämta kategori-options från governance-routen när overlayen öppnas."
    )
    assert "fallbackDiscoveryOptions" in wizard, (
        "DiscoveryWizard behöver en lokal UI-cache fallback så overlayen inte "
        "blockas av ett transient route-fel."
    )
    assert 'source === "governance"' in site_type, (
        "SiteTypeStep ska skilja governance-källan från UI-cache-fallbacken "
        "(gat:ar supportHelper + renderSupportNotice)."
    )
    # Wave 3 (Steg 7): fallback/planned-status ska fortfarande vara begriplig
    # men i KUNDSPRÅK — den gamla 'Backendens resolver avgör slutlig scaffold'
    # -jargongen ersattes med en kundvänlig formulering.
    assert "Vi väljer en närliggande mall som grund så länge." in site_type, (
        "SiteTypeStep ska göra fallback/planned-status begriplig i kundspråk "
        "utan att frontend tar scaffold-beslutet."
    )
    assert "Discovery Taxonomy is the canonical" in constants, (
        "wizard-constants.ts måste dokumentera att TS-listan bara är UI-cache."
    )


@pytest.mark.tooling
def test_discovery_payload_blocks_unknown_categories_and_emits_schema_version_2() -> None:
    payload = (VIEWSER_DIR / "components" / "discovery-wizard" / "wizard-payload.ts").read_text(
        encoding="utf-8"
    )

    assert "schemaVersion: 1 | 2" in payload, (
        "DiscoveryPayload-typen måste fortsätta acceptera legacy v1 för bakåtkompatibilitet."
    )
    assert "schemaVersion: 2," in payload, (
        "buildDiscoveryPayload ska emit:a schemaVersion=2 när v2-directives skickas från wizarden."
    )
    assert "validateDiscoveryCategoryIds" in payload, (
        "buildDiscoveryPayload måste blocka category ids som saknas i governance-options."
    )
    assert "Okänd kategori" in payload, (
        "Okända category ids ska ge tydligt klientfel före /api/prompt."
    )
    assert "resolveScaffoldHintFromOptions" in payload, (
        "buildDiscoveryPayload ska härleda scaffoldHint från category-options "
        "så ecommerce inte skickar local-service-business som motsägande hint."
    )
    assert '"starterId"' not in payload, "Frontendens discovery payload får inte sätta starterId."


@pytest.mark.tooling
def test_discovery_payload_preserves_empty_list_tombstones() -> None:
    payload = (VIEWSER_DIR / "components" / "discovery-wizard" / "wizard-payload.ts").read_text(
        encoding="utf-8"
    )

    for key in (
        '"products"',
        '"moodImages"',
        '"requestedCapabilities"',
        '"conversionGoals"',
        '"uniqueSellingPoints"',
        '"sectionTreatments"',
        '"notesForPlanner"',
    ):
        assert key in payload, (
            f"wizard-payload.ts måste bevara tom lista för {key} så backend "
            "kan rensa tidigare wizard-värden när operatören tar bort allt."
        )
    assert "directives.requestedCapabilities = capabilities" in payload, (
        "requestedCapabilities måste skickas även när listan är tom."
    )
    # D2 (scout-fynd, 2026-06-05): conversionGoals ligger i PRESERVE_EMPTY_KEYS,
    # så en tom lista skickas som tombstone och NOLLAR backendens
    # conversion_goals. Det får BARA ske när operatören tömt CTA-valet — inte
    # när hen valt en CTA som bara inte keyword-matchar ("Läs mer"/"Registrera
    # dig"). Tidigare ``directives.conversionGoals = mapCtaToConversionGoals(...)``
    # nollade målen även då. Lås den nya distinktionen: mappa till en mellan-
    # variabel och emittera bara fältet vid tom CTA (tombstone) eller faktisk
    # matchning; omatchad icke-tom CTA utelämnar fältet så briefModel-
    # extraktionen står kvar.
    assert "const mappedGoals = mapCtaToConversionGoals(primaryCtaTrimmed);" in payload, (
        "conversionGoals måste mappas till en mellan-variabel så omatchad CTA "
        "kan utelämna fältet i stället för att nolla backendens mål."
    )
    assert "if (primaryCtaTrimmed.length === 0 || mappedGoals.length > 0) {" in payload, (
        "conversionGoals-tombstonen får bara emitteras vid tom CTA eller "
        "faktisk keyword-matchning — annars utelämnas fältet (D2)."
    )
    assert "directives.conversionGoals = mappedGoals;" in payload
    assert "directives.uniqueSellingPoints = answers.uniqueSellingPoints" in payload
    assert "directives.sectionTreatments = sectionPins" in payload


@pytest.mark.tooling
def test_prompt_route_rejects_discovery_starter_id_and_followup_discovery() -> None:
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")

    assert "Discovery-payload får inte sätta starterId" in text, (
        "/api/prompt måste avvisa starterId i discovery.answers."
    )
    assert "Discovery-wizarden används bara i init-läge" in text, (
        "Followup mode får inte acceptera discovery-payload."
    )


@pytest.mark.tooling
def test_b153_device_preset_hydrates_full_device_preset() -> None:
    """B153: sessionStorage-hydration måste inkludera
    ``"full"`` bland accepterade DevicePreset-värden. Tidigare listades bara
    ``"mobile"``/``"tablet"``/``"laptop"`` så en sparad ``"full"``-preset
    relied på att default-värdet råkade vara ``"full"``. Inkonsekvent
    med övriga preset-värden (alla restoreras explicit) och om default
    någonsin ändras tappas ``"full"``. AI Bug Review (P 84 %, impact
    5/10) flaggade detta på PR #117.

    Hydration-logiken flyttades 2026-05-26 från ``viewer-panel.tsx`` till
    den nya ``device-preset-context.tsx`` så toggle-UI:t kunde lyftas in i
    FloatingChat:s footer utan prop-drilling. Testet följer hydrationen
    dit; B153-fixen lever kvar i providern.

    Lock: hydration-checken ska innehålla alla fyra Device-värden.
    """
    text = (VIEWSER_DIR / "components" / "device-preset-context.tsx").read_text(encoding="utf-8")

    pattern = re.compile(
        r'stored\s*===\s*["\']mobile["\'][\s\S]{0,200}?'
        r'stored\s*===\s*["\']tablet["\'][\s\S]{0,200}?'
        r'stored\s*===\s*["\']laptop["\'][\s\S]{0,200}?'
        r'stored\s*===\s*["\']full["\']',
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "device-preset-context.tsx sessionStorage-hydration saknar "
        "``stored === 'full'`` i listan av accepterade DevicePreset-värden. "
        "Alla fyra preset-värden måste restoreras explicit per B153 — "
        "annars bryts persistensen för 'full' om default-värdet någonsin "
        "ändras."
    )


def test_tier2_page_registers_cmd_k_shortcut_for_console_drawer() -> None:
    """``app/page.tsx`` måste registrera en global Cmd/Ctrl+K-listener
    som togglar ConsoleDrawer. Listenern måste hoppa över input/textarea-
    fokus så genvägen inte stjäl tangenten från composern.
    """
    text = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")

    assert 'event.key !== "k"' in text or 'event.key === "k"' in text, (
        "page.tsx måste lyssna på 'k'-tangenten för Cmd+K-shortcut"
    )
    assert "metaKey" in text and "ctrlKey" in text, (
        "Cmd+K-listenern måste kolla både metaKey (Mac) och ctrlKey (Windows/Linux)"
    )
    assert "setConsoleOpen" in text, "page.tsx måste toggla setConsoleOpen från Cmd+K-listenern"
    # Bekräfta att vi hoppar över edit-targets (TEXTAREA / INPUT /
    # contentEditable) så vi inte stjäl tangent från composern.
    assert "TEXTAREA" in text and "isContentEditable" in text, (
        "Cmd+K-listenern måste hoppa över editable-element så den inte "
        "stjäl tangenten från composern"
    )


def test_tier2_console_drawer_shows_keyboard_hint() -> None:
    """``console-drawer.tsx`` måste visa en ⌘K-kbd-hint i headern så
    operatören upptäcker shortcuten.
    """
    text = (VIEWSER_DIR / "components" / "console-drawer.tsx").read_text(encoding="utf-8")

    assert "⌘K" in text or "Cmd+K" in text, (
        "console-drawer.tsx måste visa en synlig ⌘K-hint i headern"
    )
    assert "<kbd" in text, (
        "Hinten ska renderas som ett <kbd>-element (semantisk markering för tangentbordsgenvägar)"
    )


def test_pre_push_cmd_k_skips_select_targets() -> None:
    """⌘K-listenern i ``page.tsx`` ska hoppa över SELECT-element så
    operatören inte tappar fokus i ConsoleDrawer's projekt-väljare
    eller andra select:s i appen. Matchar DiscoveryWizard's egen
    ⌘K-skip-lista.
    """
    path = VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx"
    content = path.read_text(encoding="utf-8")
    # Hitta useEffect-blocket för ⌘K och säkerställ att SELECT-skip finns.
    assert re.search(
        r'tagName === "SELECT"',
        content,
    ), "⌘K-listenern måste skippa SELECT-element (matcha wizardens mönster)"


def test_handoff_c_more_info_dialog_resets_active_tab_on_open() -> None:
    """``more-info-dialog.tsx`` måste nollställa ``activeTab`` till den
    begärda ``initialTab`` (default "about") varje gång ``open`` flippar
    från false → true så operatören inte ser föregående flik (Radix
    Dialog-content unmountar inte tree:t mellan open-toggles när
    controlled).

    Reset:en görs som en render-tids state-justering (Reacts "föregående
    props"-mönster via ``wasOpen``) istället för en ``onOpenChange``-
    wrapper: dels ogillar React 19:s ``react-hooks/set-state-in-effect``
    effekt-driven setState, dels är dialogen fullt parent-controlled —
    Radix routar aldrig open-flanken genom onOpenChange, så en wrapper
    skulle inte hinna nollställa fliken vid öppning. Render-mönstret kör
    pålitligt på varje false→true-övergång oavsett trigger (knapp,
    telefon-nudge etc.).
    """
    path = VIEWSER_DIR / "components" / "discovery-wizard" / "more-info-dialog.tsx"
    content = path.read_text(encoding="utf-8")
    # initialTab-prop med "about"-default måste finnas.
    assert re.search(r'initialTab\s*=\s*"about"', content), (
        'MoreInfoDialog måste ha en initialTab-prop med default "about"'
    )
    # Render-tids reset: open !== wasOpen → setActiveTab(initialTab).
    assert re.search(
        r"if \(open !== wasOpen\)\s*\{\s*setWasOpen\(open\);\s*"
        r"setTrackedInitialTab\(initialTab\);\s*"
        r"if \(open\)\s*setActiveTab\(initialTab\);",
        content,
        re.DOTALL,
    ), (
        "MoreInfoDialog måste nollställa activeTab till initialTab på "
        "open-flanken via render-tids wasOpen-mönstret"
    )
    # initialTab-byte MEDAN dialogen är öppen ska också byta flik (djuplänk
    # som byter mål utan att stänga). Annars hängde activeTab kvar.
    assert re.search(
        r"else if \(open && initialTab !== trackedInitialTab\)\s*\{\s*"
        r"setTrackedInitialTab\(initialTab\);\s*setActiveTab\(initialTab\);",
        content,
        re.DOTALL,
    ), (
        "MoreInfoDialog måste byta flik när initialTab ändras medan open "
        "redan är true (annars följer djuplänken inte med)"
    )
    # Dialog ska drivas direkt av parent's onOpenChange (ingen wrapper
    # längre — reset:en bor i render-mönstret ovan).
    assert "<Dialog open={open} onOpenChange={onOpenChange}>" in content, (
        "Dialog ska driva sin onOpenChange direkt från parent"
    )


def test_wizard_contact_nudge_deeplinks_to_contact_tab() -> None:
    """``discovery-wizard.tsx`` ska visa en nudge när telefonnummer
    saknas och kunna öppna MoreInfoDialog direkt på Kontakt-fliken så
    operatören inte oavsiktligt publicerar platshållar-numret
    (+46 8 000 00 00). Ren UI/UX — backend-payloaden är oförändrad.
    """
    path = VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx"
    content = path.read_text(encoding="utf-8")
    # openMoreInfo-helper som sätter både flik och open.
    assert "const openMoreInfo = useCallback(" in content, (
        "Wizarden måste ha en openMoreInfo-helper som sätter flik + open"
    )
    # Nudge-knappen måste djuplänka till Kontakt-fliken.
    assert 'openMoreInfo("contact")' in content, (
        'Nudge-knappen måste djuplänka via openMoreInfo("contact")'
    )
    # Nudgen ska villkoras på saknat (trimmat) telefonnummer.
    assert "!answers.contact.phone.trim()" in content, (
        "Telefon-nudgen måste villkoras på answers.contact.phone.trim()"
    )
    # initialTab måste skickas vidare till MoreInfoDialog.
    assert "initialTab={moreInfoTab}" in content, (
        "MoreInfoDialog måste få initialTab={moreInfoTab} så djuplänken "
        "till Kontakt-fliken fungerar"
    )


def test_wizard_finish_timer_is_cancelled_on_close() -> None:
    """Scout-fynd (P1): submit-overlayns 700 ms-timer fyrade av onComplete
    (bygg-start) även om operatören stängde wizarden (Esc) under väntan.
    Timern måste sparas i en ref och avbrytas när ``open`` blir false samt
    vid unmount — annars startas ett oönskat bygge efter att hen backat ut.
    """
    content = (VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx").read_text(
        encoding="utf-8"
    )
    assert "submitTimerRef" in content, (
        "finish() måste spara submit-timern i submitTimerRef så den kan avbrytas"
    )
    assert "submitTimerRef.current = window.setTimeout(" in content, (
        "submit-timern måste lagras i submitTimerRef (inte en lös setTimeout)"
    )
    # Avbrott när open blir false (Esc/stäng).
    assert re.search(
        r"if \(open\) return;\s*\n\s*if \(submitTimerRef\.current !== null\)\s*\{\s*"
        r"clearTimeout\(submitTimerRef\.current\);",
        content,
        re.DOTALL,
    ), "Wizarden måste avbryta submit-timern i en effekt när open blir false"


def test_wizard_keyboard_help_lists_all_four_steps() -> None:
    """Scout-fynd (P1): genvägs-hjälpen sa 'Hoppa till tab 1–3' men wizarden
    har fyra steg (foundation→assets). Lås att hjälptexten listar steg 1–4.

    Wave 2 (Steg 4): steg-hoppet flyttades från ⌘/Ctrl+siffra till ⌥+siffra
    eftersom ⌘/Ctrl+siffra är webbläsarens egna flik-genvägar — matchningen
    görs på event.code (Digit1–9) eftersom Option+siffra ger specialtecken
    på Mac. ⌘/-genvägen har samma inEditable-guard som ?.
    """
    content = (VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx").read_text(
        encoding="utf-8"
    )
    assert '"⌥1", "⌥2", "⌥3", "⌥4"' in content, (
        "Genvägs-hjälpen måste lista alla fyra steg med ⌥-modifier (⌥1–⌥4)"
    )
    assert "Hoppa till tab 1–3" not in content, (
        "Den föråldrade 'tab 1–3'-texten måste bort — wizarden har fyra steg"
    )
    assert '"⌘1", "⌘2", "⌘3", "⌘4"' not in content, (
        "⌘-baserade steg-genvägar måste bort — de krockar med webbläsarens flik-genvägar (Steg 4)"
    )
    # Handlern måste matcha ⌥ + event.code (inte ⌘/Ctrl + event.key).
    assert "event.altKey" in content and re.search(
        r"/\^Digit\[1-9\]\$/\.test\(event\.code\)", content
    ), (
        "Steg-hoppet måste matcha event.altKey + event.code (Digit1–9) så det "
        "inte krockar med webbläsarens ⌘/Ctrl+siffra-flikbyte"
    )
    # Scout-fynd (P1, 2026-06-05): wizardens globala genvägar ligger på document
    # och fyrade bakom MoreInfoDialog (egen Dialog-portal ovanpå) — ⌘↵ kunde
    # avancera/submit:a wizarden utan att operatören såg det. Handlern måste
    # early-return:a när moreInfoOpen är true OCH ha moreInfoOpen i dep-arrayen.
    assert "if (moreInfoOpen) return;" in content, (
        "keydown-handlern måste lämna över tangentbordet till MoreInfoDialog "
        "(early-return på moreInfoOpen) så wizard-genvägar inte fyrar bakom modalen."
    )
    assert "goToStep, helpOpen, moreInfoOpen]" in content, (
        "moreInfoOpen måste ligga i keydown-effektens dep-array, annars läser "
        "guarden ett stale värde."
    )


def test_wizard_submit_overlay_uses_customer_language() -> None:
    """Scout-fynd (microcopy): submit-overlayn visade pipeline-jargong
    ('Discovery → Plan → Codegen') för en icke-teknisk kund. Lås kundvänlig
    svenska så kärnflödet prompt→sajt känns begripligt.
    """
    content = (VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx").read_text(
        encoding="utf-8"
    )
    assert "Discovery → Plan → Codegen" not in content, (
        "Pipeline-jargong får inte visas i den kundvända submit-overlayn"
    )
    assert "Vi läser dina svar, planerar sidorna och bygger sajten." in content, (
        "Submit-overlayn ska förklara bygget i kundvänlig svenska"
    )


def test_cmd_k_has_modal_guard() -> None:
    """Wave 2 (Steg 1): global ⌘K togglade ConsoleDrawer även när en annan
    modal (DiscoveryWizard/MoreInfoDialog/Verktyg/bygg-dialog) var öppen och
    ryckte upp en bakgrundspanel mitt i kärnflödet. Handlern måste suppressa
    öppning när konsolen är stängd OCH ett [role="dialog"]/[aria-modal]-
    element finns i DOM, men fortfarande kunna STÄNGA en öppen konsol.
    """
    content = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "consoleOpenRef" in content, (
        "⌘K-handlern måste spegla consoleOpen via en ref (lever i []-effekt)"
    )
    assert re.search(
        r"if \(!consoleOpenRef\.current\)\s*\{\s*if \(\s*document\.querySelector\(",
        content,
        re.DOTALL,
    ), (
        "⌘K måste suppressas när konsolen är stängd och en annan modal är "
        "öppen (querySelector på role=dialog/aria-modal)"
    )
    assert '[role="dialog"], [role="alertdialog"], [aria-modal="true"]' in content, (
        "Modal-guarden måste täcka role=dialog, role=alertdialog och aria-modal=true"
    )


def test_builder_actions_arrow_keys_scope_to_current_target() -> None:
    """Wave 2 (Steg 2), porterad till ToolsPopover (Verktyg fas 1
    2026-06-11): builder-actions.tsx är borttagen och Verktyg-panelen
    lever i tools-popover.tsx. Samma invariant gäller — tangenthanteraren
    måste scope:a sökningen till event.currentTarget (inte en yttre ref)
    så knapparna hittas oavsett var panelen renderas, och både flik-raden
    och verktygs-gridden måste ha varsin onKeyDown.
    """
    content = (VIEWSER_DIR / "components" / "builder" / "tools-popover.tsx").read_text(
        encoding="utf-8"
    )
    assert "const node = event.currentTarget;" in content, (
        "Tangenthanterarna måste scope:a sökningen till event.currentTarget "
        "(inte en yttre container-ref) så panelens knappar hittas"
    )
    assert "onKeyDown={handleTabsKeyDown}" in content, (
        "Flik-raden måste ha piltangentsnavigering (handleTabsKeyDown)"
    )
    assert "onKeyDown={handleGridKeyDown}" in content, (
        "Verktygs-gridden måste ha piltangentsnavigering (handleGridKeyDown)"
    )


def test_console_button_exposes_cmd_k_hint() -> None:
    """Wave 2 (Steg 3): ⌘K-hinten syntes bara inuti den redan öppna konsolen.
    Header-konsolknappen måste exponera genvägen (title + aria-label) så den
    är upptäckbar innan konsolen öppnats.
    """
    content = (VIEWSER_DIR / "components" / "layout" / "site-header.tsx").read_text(
        encoding="utf-8"
    )
    assert "⌘K (Ctrl+K på Windows)" in content, (
        "Header-konsolknappen måste ha en title som visar ⌘K-genvägen"
    )
    assert "(genväg ⌘K)" in content, "aria-label måste nämna ⌘K-genvägen för skärmläsare"


def test_wizard_help_button_visible_on_mobile() -> None:
    """Wave 2 (Steg 5): genvägs-/hjälp-knappen var ``hidden sm:inline-flex``
    → osynlig på smal viewport (t.ex. iPad i porträtt med tangentbord). Den
    måste vara synlig på alla viewports med ett 44px tap-target på mobil
    (min-tap).
    """
    content = (VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx").read_text(
        encoding="utf-8"
    )
    # Hjälp-knappens block (aria-label="Visa tangentbordsgenvägar") får inte
    # längre döljas på mobil.
    help_btn_idx = content.find('aria-label="Visa tangentbordsgenvägar"')
    assert help_btn_idx != -1, "Hjälp-knappen måste finnas kvar"
    btn_class_window = content[help_btn_idx : help_btn_idx + 600]
    assert "hidden" not in btn_class_window or "min-tap sm:min-tap-0" in btn_class_window, (
        "Hjälp-knappen får inte vara dold på mobil — gör den inline-flex med "
        "min-tap för 44px tap-target"
    )
    assert "min-tap sm:min-tap-0 inline-flex" in btn_class_window, (
        "Hjälp-knappen måste vara inline-flex med min-tap (44px) på mobil"
    )


def test_device_preset_keyboard_shortcuts() -> None:
    """Wave 3 (Steg 6): device-preset (375/768/1024/Full) saknade genvägar
    + kbd-hints. ⌥1–⌥4 ska växla preview-bredd (desktop, ej i composern,
    via event.code) och knapparna ska exponera genvägen via title.
    """
    content = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert re.search(r"/\^Digit\[1-4\]\$/\.test\(event\.code\)", content), (
        "Device-preset-genvägen måste matcha ⌥ + event.code (Digit1–4)"
    )
    assert "DEVICE_PRESET_OPTIONS[parseInt(event.code.slice(5), 10) - 1]" in content, (
        "⌥1–⌥4 måste mappa till DEVICE_PRESET_OPTIONS-index"
    )
    assert "title={`Genväg ${shortcut}`}" in content, (
        "Device-preset-knapparna måste exponera genvägen via title"
    )


def test_wizard_foundation_copy_avoids_dev_jargon() -> None:
    """Wave 3 (Steg 7): kundvända hjälptexter i foundation- och
    site-type-stegen exponerade dev-jargong ('scaffold', 'Next.js-mall
    backend bygger på', 'Discovery Taxonomy', 'Backendens resolver',
    'runtime-aktiv'). Lås bort de tydligaste på de kundvända ytorna.
    """
    foundation = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "steps" / "foundation-step.tsx"
    ).read_text(encoding="utf-8")
    site_type = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "steps" / "site-type-step.tsx"
    ).read_text(encoding="utf-8")

    assert "vilken Next.js-mall backend bygger på" not in foundation, (
        "Foundation-hjälptexten ska inte exponera 'Next.js-mall backend'-jargong"
    )
    assert 'subtitle="Scaffold, vibe, typografi, branch' not in foundation, (
        "MetadataPanel-subtitle ska inte lista 'Scaffold/branch'-jargong"
    )
    # Endast den kundvända HelperText-meningen ska bort — kod-kommentaren som
    # dokumenterar att listan kommer från Discovery Taxonomy får stå kvar.
    assert "Listan följer Discovery Taxonomy." not in site_type, (
        "Den kundvända HelperText-meningen om 'Discovery Taxonomy' ska bort"
    )
    assert "Visar lokal UI-cache tills governance-listan laddats." not in site_type, (
        "Den kundvända UI-cache-jargongen ska bort från HelperText"
    )
    assert "Backendens resolver avgör slutlig scaffold" not in site_type, (
        "Support-notisen ska inte exponera 'Backendens resolver/scaffold'-jargong"
    )
    assert "är runtime-aktiv" not in site_type, (
        "'runtime-aktiv' ska ersättas med kundvänligt 'tillgänglig'"
    )


def test_wizard_seed_handoff_carries_hints_only() -> None:
    """Starters-banan: seed-handoffen får bara bära lätta hints
    (prompt + businessFamily + siteType) — inga fullständiga build-beslut
    och absolut inget starterId (samma invariant som /api/prompt).
    """
    handoff = (VIEWSER_DIR / "lib" / "init-prompt-handoff.ts").read_text(encoding="utf-8")
    assert "setWizardSeed" in handoff and "consumeWizardSeed" in handoff, (
        "init-prompt-handoff ska exponera set/consumeWizardSeed"
    )
    assert "businessFamily" in handoff and "siteType" in handoff, (
        "WizardSeed ska bära familj + kategori-hints"
    )
    assert "starterId" not in handoff, (
        "WizardSeed får inte bära starterId (backend äger scaffold-valet)"
    )


@pytest.mark.tooling
def test_wizard_tab_strip_is_keyboard_navigable() -> None:
    """S4: wizard-stegstripen ska följa WAI-ARIA tabs-mönstret — roving
    tabindex, pil/Home/End-navigering och tabpanel-koppling.
    """
    text = (VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx").read_text(
        encoding="utf-8"
    )
    assert "tabIndex={isActive ? 0 : -1}" in text, (
        "Stegstripen ska använda roving tabindex (bara aktiv flik i tab-ordningen)."
    )
    assert '"ArrowRight"' in text and '"Home"' in text and '"End"' in text, (
        "Stegstripen ska hantera pil/Home/End-navigering."
    )
    assert 'role="tabpanel"' in text and 'aria-controls="wizard-tabpanel"' in text, (
        "Flikarna ska peka på en tabpanel (aria-controls) och panelen ska ha role=tabpanel."
    )


@pytest.mark.tooling
def test_more_info_dialog_tab_strip_is_keyboard_navigable() -> None:
    """Scout-fynd (P1, 2026-06-05, två oberoende agenter): MoreInfoDialog-
    flikarna hade role=tab/aria-selected men SAKNADE pil/Home/End-tangentbord,
    roving tabindex och tabpanel-koppling — inne i Dialog-portalen gick de inte
    att nå med tangentbord (till skillnad från huvud-wizardens stegstrip).
    Lås att MoreInfoDialog nu följer samma WAI-ARIA tabs-mönster.
    """
    text = (VIEWSER_DIR / "components" / "discovery-wizard" / "more-info-dialog.tsx").read_text(
        encoding="utf-8"
    )
    assert "tabIndex={isActive ? 0 : -1}" in text, (
        "MoreInfoDialog-flikarna ska använda roving tabindex (bara aktiv flik i tab-ordningen)."
    )
    assert '"ArrowRight"' in text and '"Home"' in text and '"End"' in text, (
        "MoreInfoDialog-flikarna ska hantera pil/Home/End-navigering."
    )
    assert 'role="tabpanel"' in text and 'aria-controls="more-info-tabpanel"' in text, (
        "MoreInfoDialog-flikarna ska peka på en tabpanel (aria-controls) och "
        "panelen ska ha role=tabpanel + aria-labelledby."
    )


@pytest.mark.tooling
def test_discovery_wizard_gates_forward_jumps() -> None:
    """P1: tab-klick, pil-navigering och ⌥-siffra hoppade tidigare till valfritt
    steg utan validering → operatören kunde skippa ett halvfyllt foundation-
    steg. Source-lock att en resolveReachableStep-gate clamp:ar framåt-hopp
    mot maxReachableStep (bakåt fortsatt fritt)."""
    text = (VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx").read_text(
        encoding="utf-8"
    )
    assert "maxReachableStep" in text and "resolveReachableStep" in text, (
        "Wizarden ska beräkna maxReachableStep och routa hopp genom resolveReachableStep."
    )
    assert "resolveReachableStep(idx, current)" in text, (
        "Tab-klick ska gå genom resolveReachableStep, inte rå setStepIndex(idx)."
    )


@pytest.mark.tooling
def test_visual_step_revalidates_vibe_against_scaffold() -> None:
    """P1: vid family-byte av-/återmonteras VisualStep men auto-default-
    effekten early-returnade så snart vibeId var truthy → ett stale vibe-id
    från föregående family behölls (syntes ej markerat men låg kvar i
    payloaden). Source-lock att den nu validerar mot vibes-listan."""
    text = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "steps" / "visual-step.tsx"
    ).read_text(encoding="utf-8")
    assert (
        "currentVibeValid" in text and "vibes.some((v) => v.id === answers.vibe.vibeId)" in text
    ), (
        "VisualStep ska validera vald vibe mot scaffoldens vibe-lista och "
        "byta ut en stale vibe mot familjens default."
    )


@pytest.mark.tooling
def test_tokens_tab_clears_session_storage_on_commit() -> None:
    """P1: sessionStorage-overrides överlevde en commit och återuppväcktes vid
    reload — trots att färgerna redan bakats in i sajten — så tabben erbjöd
    om samma commit i oändlighet. Source-lock att handleCommit rensar storage
    och att en settle-effekt tömmer buffern efter bygget."""
    text = (VIEWSER_DIR / "components" / "builder" / "inspector" / "tokens-tab.tsx").read_text(
        encoding="utf-8"
    )
    commit_idx = text.find("const handleCommit = useCallback(")
    assert commit_idx != -1, "tokens-tab.tsx ska ha handleCommit."
    # clearStoredTokens måste anropas inom handleCommit (före onPrompt).
    window = text[commit_idx : commit_idx + 600]
    assert "clearStoredTokens();" in window, (
        "handleCommit ska rensa sessionStorage vid commit så overrides inte "
        "återuppväcks vid reload."
    )
    assert "committedPromptRef" in text, (
        "Tokens-tabben ska spåra den committade prompten och settle:a buffern "
        "efter att bygget konsumerat den."
    )


@pytest.mark.tooling
def test_focus_trap_hook_used_by_custom_dialogs() -> None:
    """P1: de custom overlay-dialogerna (AI-bildgenerator + wizardens
    kortkommando-overlay) saknade focus-trap trots role=dialog/aria-modal.
    Source-lock att useFocusTrap-hooken finns och används i båda."""
    hook = VIEWSER_DIR / "lib" / "use-focus-trap.ts"
    assert hook.exists(), "lib/use-focus-trap.ts ska finnas."
    hook_text = hook.read_text(encoding="utf-8")
    assert "export function useFocusTrap" in hook_text, (
        "use-focus-trap.ts ska exportera useFocusTrap."
    )
    ai_dialog = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "ai-image-generator-dialog.tsx"
    ).read_text(encoding="utf-8")
    wizard = (VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx").read_text(
        encoding="utf-8"
    )
    assert "useFocusTrap(dialogRef, open)" in ai_dialog, (
        "AI-bilddialogen ska fånga Tab inom dialogen via useFocusTrap."
    )
    assert "useFocusTrap(helpPanelRef, helpOpen)" in wizard, (
        "Wizardens kortkommando-overlay ska fånga Tab via useFocusTrap."
    )


@pytest.mark.tooling
def test_asset_dropzone_keeps_partial_uploads() -> None:
    """P2: vid fel på fil N i en multi-upload kastades de redan uppladdade
    filerna 1..N-1 bort (onUploaded kördes aldrig) → föräldralösa på servern.
    Source-lock att catch-grenen lyfter de lyckade uppladdningarna."""
    text = (VIEWSER_DIR / "components" / "discovery-wizard" / "asset-dropzone.tsx").read_text(
        encoding="utf-8"
    )
    assert "if (uploaded.length > 0) onUploaded(uploaded);" in text, (
        "Partiellt misslyckad batch ska ändå lyfta de redan uppladdade filerna."
    )


@pytest.mark.tooling
def test_review_summary_andra_links_are_wired_to_step_jump() -> None:
    """Ersätter den manuella klick-checken från #228 (operatörsbeslut
    2026-06-10: manuella checkar pensioneras, beteendet låses i test).
    Granska-radernas "Ändra"-länk ska hoppa till rätt wizard-steg
    (onJumpToStep) eller öppna rätt mer-info-tab (onOpenMoreInfo), och
    wizarden ska tråda in sina riktiga callbacks — annars är länken död
    och operatören fastnar på Bilder-steget."""
    summary = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "review-summary.tsx"
    ).read_text(encoding="utf-8")
    for wiring in (
        "onEdit: () => onJumpToStep(0)",
        "onEdit: () => onJumpToStep(1)",
        "onEdit: () => onJumpToStep(2)",
        'onEdit: () => onOpenMoreInfo("contact")',
        'onEdit: () => onOpenMoreInfo("about")',
    ):
        assert wiring in summary, (
            f"review-summary saknar Ändra-wiring {wiring!r} — länken vore död."
        )
    assert "onClick={item.onEdit}" in summary, (
        "Ändra-knappen måste anropa radens onEdit-callback."
    )
    wizard = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx"
    ).read_text(encoding="utf-8")
    assert "onJumpToStep={goToStep}" in wizard, (
        "Wizarden måste tråda goToStep in i ReviewSummary (annars hoppar "
        "Ändra-länken ingenstans)."
    )
    assert "onOpenMoreInfo={openMoreInfo}" in wizard, (
        "Wizarden måste tråda openMoreInfo in i ReviewSummary."
    )
