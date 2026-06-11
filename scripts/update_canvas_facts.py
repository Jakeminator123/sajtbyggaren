"""Hall de delade canvasernas fakta-block i synk med vad som faktiskt finns pa main.

Tva canvases bar autogenererade fakta-block:

1. docs/canvases/begreppskarta-sajtbyggaren.canvas.tsx (REPO_FACTS):
   scaffolds/dossiers pa disk + kvalitetsmalen fran
   governance/policies/page-quality-traits.v1.json.
2. docs/canvases/roller-vs-agenter-modeller.canvas.tsx (MODEL_FACTS):
   llm-models-policyversionen, motorns distinkta modellstrangar och
   kod-fallbackarna for chatt/vision/discovery (regex-parsade ur kallfilerna
   sa kartan aldrig kan drifta fran koden igen - audit 2026-06-11).

Anvands av Steward (manuellt eller via steward-auto-bump-workflowet):
  python scripts/update_canvas_facts.py          # uppdatera blocken
  python scripts/update_canvas_facts.py --check  # exit 1 vid drift, skriver inget
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANVAS_PATH = REPO_ROOT / "docs" / "canvases" / "begreppskarta-sajtbyggaren.canvas.tsx"
ROLES_CANVAS_PATH = (
    REPO_ROOT / "docs" / "canvases" / "roller-vs-agenter-modeller.canvas.tsx"
)
SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
DOSSIERS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"
SCAFFOLD_CONTRACT = REPO_ROOT / "governance" / "policies" / "scaffold-contract.v1.json"
QUALITY_TRAITS = REPO_ROOT / "governance" / "policies" / "page-quality-traits.v1.json"
LLM_MODELS_POLICY = REPO_ROOT / "governance" / "policies" / "llm-models.v1.json"
VIEWSER_OPENAI_TS = REPO_ROOT / "apps" / "viewser" / "lib" / "openai.ts"
VIEWSER_VISION_TS = REPO_ROOT / "apps" / "viewser" / "lib" / "asset-store" / "vision.ts"
SCRAPE_SITE_PY = REPO_ROOT / "scripts" / "scrape_site.py"

BLOCK_START = "// AUTOGEN_REPO_FACTS_START"
BLOCK_END = "// AUTOGEN_REPO_FACTS_END"
BLOCK_RE = re.compile(
    re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END),
    flags=re.DOTALL,
)

MODEL_BLOCK_START = "// AUTOGEN_MODEL_FACTS_START"
MODEL_BLOCK_END = "// AUTOGEN_MODEL_FACTS_END"
MODEL_BLOCK_RE = re.compile(
    re.escape(MODEL_BLOCK_START) + r".*?" + re.escape(MODEL_BLOCK_END),
    flags=re.DOTALL,
)

EMBEDDING_ROLE_ID = "embeddingModel"


def count_scaffolds_on_disk() -> int:
    if not SCAFFOLDS_DIR.is_dir():
        return 0
    return sum(1 for p in SCAFFOLDS_DIR.iterdir() if (p / "scaffold.json").is_file())


def count_scaffolds_in_registry() -> int:
    contract = json.loads(SCAFFOLD_CONTRACT.read_text(encoding="utf-8"))
    registry = contract.get("primaryScaffoldRegistry", [])
    return len(registry)


def count_dossiers(class_name: str) -> int:
    class_dir = DOSSIERS_DIR / class_name
    if not class_dir.is_dir():
        return 0
    return sum(1 for p in class_dir.iterdir() if (p / "manifest.json").is_file())


def quality_target() -> dict[str, float]:
    traits = json.loads(QUALITY_TRAITS.read_text(encoding="utf-8"))
    target = traits.get("qualityTarget", {})
    return {
        "targetScore": float(target.get("targetScore", 0.0)),
        "gateScore": float(target.get("gateScore", 0.0)),
        "blockBelow": float(target.get("blockBelow", 0.0)),
    }


def format_number(value: float) -> str:
    """Skriv heltal utan decimal men behall en decimal for malvarden (9.0)."""

    if value == int(value):
        return f"{value:.1f}"
    return f"{value}"


def render_block(generated_at: str) -> str:
    quality = quality_target()
    lines = [
        BLOCK_START + " -- skrivs av scripts/update_canvas_facts.py, redigera inte for hand",
        "const REPO_FACTS = {",
        f'  generatedAt: "{generated_at}",',
        f"  scaffoldsOnDisk: {count_scaffolds_on_disk()},",
        f"  scaffoldsInRegistry: {count_scaffolds_in_registry()},",
        f"  softDossiers: {count_dossiers('soft')},",
        f"  hardDossiers: {count_dossiers('hard')},",
        f"  qualityTargetScore: {format_number(quality['targetScore'])},",
        f"  qualityGateScore: {format_number(quality['gateScore'])},",
        f"  qualityBlockBelow: {format_number(quality['blockBelow'])},",
        "} as const;",
        BLOCK_END,
    ]
    return "\n".join(lines)


def _llm_models_policy() -> dict:
    return json.loads(LLM_MODELS_POLICY.read_text(encoding="utf-8"))


def llm_models_version() -> int:
    version = _llm_models_policy().get("version")
    if not isinstance(version, int):
        raise ValueError(f"llm-models.v1.json saknar heltals-version ({version!r}).")
    return version


def engine_generation_models() -> list[str]:
    """Distinkta model-strangar for motorns roller (embedding undantagen)."""

    models: list[str] = []
    for role in _llm_models_policy().get("roles", []):
        if role.get("id") == EMBEDDING_ROLE_ID:
            continue
        model = role.get("model")
        if isinstance(model, str) and model and model not in models:
            models.append(model)
    if not models:
        raise ValueError("llm-models.v1.json deklarerar inga generation-roller.")
    return models


def embedding_model() -> str:
    for role in _llm_models_policy().get("roles", []):
        if role.get("id") == EMBEDDING_ROLE_ID:
            model = role.get("model")
            if isinstance(model, str) and model:
                return model
    raise ValueError("llm-models.v1.json saknar embeddingModel-rollen.")


def _parse_fallback(path: Path, pattern: str, label: str) -> str:
    """Regex-parsa kod-fallbacken ur en kallfil; hard fail vid monsterdrift."""

    if not path.is_file():
        raise ValueError(f"Hittar inte {path} - har {label}-kallan flyttats?")
    match = re.search(pattern, path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(
            f"Hittar inte {label}-fallbacken i {path.name} - har monstret andrats?"
        )
    return match.group(1)


def chat_fallback_model() -> str:
    return _parse_fallback(
        VIEWSER_OPENAI_TS,
        r'openaiEnv\("OPENAI_MODEL"\)\s*\?\?\s*"([^"]+)"',
        "OPENAI_MODEL",
    )


def vision_fallback_model() -> str:
    return _parse_fallback(
        VIEWSER_VISION_TS,
        r'openaiEnv\("OPENAI_VISION_MODEL"\)\s*\?\?\s*"([^"]+)"',
        "OPENAI_VISION_MODEL",
    )


def discovery_fallback_model() -> str:
    return _parse_fallback(
        SCRAPE_SITE_PY,
        r'os\.environ\.get\(\s*"SAJTBYGGAREN_DISCOVERY_MODEL",\s*"([^"]+)"',
        "SAJTBYGGAREN_DISCOVERY_MODEL",
    )


def render_model_block(generated_at: str) -> str:
    engine_ts = ", ".join(f'"{m}"' for m in engine_generation_models())
    lines = [
        MODEL_BLOCK_START
        + " -- skrivs av scripts/update_canvas_facts.py, redigera inte for hand",
        "const MODEL_FACTS = {",
        f'  generatedAt: "{generated_at}",',
        f"  llmModelsVersion: {llm_models_version()},",
        f"  engineModels: [{engine_ts}],",
        f'  embeddingModel: "{embedding_model()}",',
        f'  chatFallbackModel: "{chat_fallback_model()}",',
        f'  visionFallbackModel: "{vision_fallback_model()}",',
        f'  discoveryFallbackModel: "{discovery_fallback_model()}",',
        "} as const;",
        MODEL_BLOCK_END,
    ]
    return "\n".join(lines)


def extract_generated_at(text: str) -> str | None:
    match = re.search(r'generatedAt: "(\d{4}-\d{2}-\d{2})"', text)
    return match.group(1) if match else None


# (sokvag, block-regex, render-funktion, mansklig etikett)
TARGETS = [
    (CANVAS_PATH, BLOCK_RE, render_block, "begreppskartan"),
    (ROLES_CANVAS_PATH, MODEL_BLOCK_RE, render_model_block, "roll/modell-kartan"),
]


def process_target(
    path: Path,
    block_re: re.Pattern[str],
    render_fn,
    label: str,
    *,
    check: bool,
) -> tuple[int, bool]:
    """Returnerar (exit-kod, skrev-fil)."""

    if not path.is_file():
        print(f"Hittar inte {path} - har {label} flyttats?")
        return 1, False

    text = path.read_text(encoding="utf-8")
    block_match = block_re.search(text)
    if not block_match:
        print(f"Hittar inte fakta-blocket i {path.name}.")
        return 1, False

    current = block_match.group(0)
    # Behall befintligt datum vid jamforelse sa att enbart faktadrift flaggas;
    # datumet ensamt ska inte generera nya commits fran steward-auto-bump.
    existing_date = extract_generated_at(current) or "0000-00-00"
    expected = render_fn(existing_date)

    if check:
        if current != expected:
            print(f"Fakta-blocket i {label} matchar inte repot. Forvantat innehall:")
            print(expected)
            print("Kor: python scripts/update_canvas_facts.py")
            return 1, False
        print(f"Fakta-blocket i {label} ar i synk med repot.")
        return 0, False

    if current == expected:
        print(f"Fakta-blocket i {label} ar redan uppdaterat - inget skrevs.")
        return 0, False

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    new_text = block_re.sub(lambda _m: render_fn(today), text, count=1)
    path.write_text(new_text, encoding="utf-8", newline="\n")
    print(f"Fakta-blocket uppdaterat i {path.relative_to(REPO_ROOT)} (per {today}).")
    return 0, True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Skriv inget; exit 1 om nagot fakta-block inte matchar repots innehall.",
    )
    args = parser.parse_args(argv)

    exit_code = 0
    wrote_anything = False
    for path, block_re, render_fn, label in TARGETS:
        try:
            code, wrote = process_target(
                path, block_re, render_fn, label, check=args.check
            )
        except ValueError as exc:
            print(f"FEL ({label}): {exc}")
            code, wrote = 1, False
        if code != 0:
            exit_code = 1
        if wrote:
            wrote_anything = True

    if wrote_anything:
        print("Glom inte: python scripts/sync_canvases.py for att spegla till Cursor-mappen.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
