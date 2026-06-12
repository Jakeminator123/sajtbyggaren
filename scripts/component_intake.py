"""Curated shadcn component intake CLI (Component Catalog lager 3, ADR 0054).

Productifies the shadcn-MCP lab reference (``övrigt/shadcn-mcp-lab/``). The CLI
spawns its OWN ``npx shadcn@latest mcp`` stdio server via the OpenAI Agents SDK
pattern (``agents.mcp.MCPServerStdio``), runs the deterministic tool flow
``search_items_in_registries -> view_items_in_registries ->
get_item_examples_from_registries`` and synthesises a pydantic-typed component
candidate. The candidate is written to ``data/component-candidates/<slug>/``:

- ``component.tsx``    - the candidate component source,
- ``intake-info.json`` - prompt, model, shadcnItemsUsed, contentHash, the
                         required npm deps and provenance,
- ``README.md``        - the operator review + curation instruction.

Hard separation rules (ADR 0054):

- The CLI NEVER reads ``.cursor/mcp.json`` - it owns its own server params.
- The CLI NEVER writes into ``data/starters/`` or
  ``packages/generation/orchestration/`` (dossiers/scaffolds). Promotion into a
  Starter is an operator decision, made via a reviewed PR.
- Without ``OPENAI_API_KEY`` the CLI fails honestly - there is NO mock fallback
  (a curated intake without a model would be a fabricated candidate).
- The CLI is an OPERATOR tool, not part of the build chain; the LLM call here is
  intake-time, never runtime.

CI parity: the tool flow is behind the ``ShadcnMcpSession`` seam and the model
call goes through an injectable client, so ``tests/test_component_intake.py``
exercises the whole orchestration with a mocked session + model - no network,
no ``npx``, no key required in CI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.brief.models import (  # noqa: E402
    OPENAI_API_KEY_ENV,
    has_openai_api_key,
)
from scripts.candidate_generation_metadata import (  # noqa: E402
    created_at,
    guard_candidate_output_dir,
    repo_or_output_relative,
)

STARTERS_DIR = REPO_ROOT / "data" / "starters"
ORCHESTRATION_DIR = REPO_ROOT / "packages" / "generation" / "orchestration"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "component-candidates"
DEFAULT_POLICY_PATH = REPO_ROOT / "governance" / "policies" / "llm-models.v1.json"
# Reuse the dossierModel policy entry for the intake's structured-output call:
# component intake is the same class of candidate-generation task and gets the
# same model-policy discipline without inventing a new role for this slice.
INTAKE_ROLE_ID = "dossierModel"
EXPECTED_PROVIDER = "openai"

# The shadcn MCP server the CLI spawns itself (stdio). NEVER .cursor/mcp.json.
SHADCN_MCP_COMMAND = "npx"
SHADCN_MCP_ARGS = ("shadcn@latest", "mcp")
DEFAULT_REGISTRY = "@shadcn"

# The three shadcn MCP tools the intake flow drives, in order.
TOOL_SEARCH = "search_items_in_registries"
TOOL_VIEW = "view_items_in_registries"
TOOL_EXAMPLES = "get_item_examples_from_registries"

SLUG_CLEAN = re.compile(r"[^a-z0-9-]+")
SLUG_DASHES = re.compile(r"-{2,}")
# Registry item tokens like "@shadcn/accordion" in tool output.
_ITEM_TOKEN_RE = re.compile(r"@[a-z0-9][\w-]*/[a-z0-9][\w-]*", re.IGNORECASE)
_MAX_ITEMS = 8

INTAKE_INFO_VERSION = 1


class ComponentIntakeError(RuntimeError):
    """Raised when a component candidate cannot be produced or written."""


class ComponentModelResolutionError(RuntimeError):
    """Raised when llm-models.v1.json has no usable intake model role."""


# ---------------------------------------------------------------------------
# Pydantic structured output (the model's candidate)
# ---------------------------------------------------------------------------


class ComponentCandidate(BaseModel):
    """Structured output for one curated component candidate."""

    model_config = ConfigDict(extra="forbid")

    componentName: str = Field(
        description="PascalCase React component / file base name, e.g. Accordion."
    )
    tsx: str = Field(
        description="Self-contained .tsx source for the candidate component."
    )
    requiredNpmDeps: list[str] = Field(
        default_factory=list,
        description=(
            "npm package names the candidate.tsx imports beyond react. Empty "
            "when the candidate is zero-dependency (native elements + cn)."
        ),
    )
    shadcnItemsUsed: list[str] = Field(
        default_factory=list,
        description="shadcn registry item identifiers the candidate is based on.",
    )
    notes: str = Field(
        default="",
        description="Short review note: tradeoffs, accessibility, dep rationale.",
    )


# ---------------------------------------------------------------------------
# Gathered shadcn material + result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ShadcnGathered:
    """Raw text gathered from the three shadcn MCP tool calls."""

    searchText: str
    viewText: str
    examplesText: str
    itemsUsed: list[str]


@dataclass(frozen=True)
class ComponentIntakeResult:
    """Metadata for one written component candidate."""

    candidate_dir: Path
    component_path: Path
    intake_info_path: Path
    readme_path: Path
    intake_info: dict[str, Any]
    model_used: str


# ---------------------------------------------------------------------------
# MCP session seam (mocked in CI)
# ---------------------------------------------------------------------------


@runtime_checkable
class ShadcnMcpSession(Protocol):
    """A live shadcn MCP session, used as a context manager.

    The three methods wrap the shadcn MCP tools and return their raw text. Tests
    inject a fake implementing this Protocol so no real server is spawned.
    """

    def __enter__(self) -> ShadcnMcpSession: ...

    def __exit__(self, *exc: object) -> None: ...

    def search_items_in_registries(self, query: str) -> str: ...

    def view_items_in_registries(self, items: list[str]) -> str: ...

    def get_item_examples_from_registries(self, query: str, items: list[str]) -> str: ...


class _AgentsSdkShadcnSession:
    """Real session: spawns ``npx shadcn@latest mcp`` over stdio.

    Uses the OpenAI Agents SDK ``MCPServerStdio`` (lazy-imported so the module
    loads without the SDK and CI never needs it). One event loop owns the
    server lifecycle for the whole intake; each tool method runs a single
    ``call_tool`` synchronously against the open connection.
    """

    def __init__(
        self,
        *,
        command: str = SHADCN_MCP_COMMAND,
        args: tuple[str, ...] = SHADCN_MCP_ARGS,
        registry: str = DEFAULT_REGISTRY,
    ) -> None:
        self._command = command
        self._args = list(args)
        self._registry = registry
        self._server: Any = None
        self._loop: Any = None

    def __enter__(self) -> _AgentsSdkShadcnSession:
        import asyncio

        try:
            from agents.mcp import MCPServerStdio
        except ImportError as exc:  # pragma: no cover - exercised outside venv
            raise ComponentIntakeError(
                "openai-agents is not installed. The component intake CLI needs "
                "the Agents SDK (agents.mcp.MCPServerStdio). Activate the venv "
                "and run `pip install -r requirements.txt`."
            ) from exc

        self._loop = asyncio.new_event_loop()
        self._server = MCPServerStdio(
            name="shadcn registry MCP (own stdio, never .cursor/mcp.json)",
            params={"command": self._command, "args": self._args},
            client_session_timeout_seconds=60,
        )
        self._loop.run_until_complete(self._server.connect())
        return self

    def __exit__(self, *exc: object) -> None:
        if self._server is not None and self._loop is not None:
            try:
                self._loop.run_until_complete(self._server.cleanup())
            finally:
                self._loop.close()
                self._server = None
                self._loop = None

    def _call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        if self._server is None or self._loop is None:  # pragma: no cover
            raise ComponentIntakeError("shadcn MCP session is not open")
        result = self._loop.run_until_complete(
            self._server.call_tool(tool_name, arguments)
        )
        return _result_text(result)

    def search_items_in_registries(self, query: str) -> str:
        return self._call(
            TOOL_SEARCH, {"registries": [self._registry], "query": query}
        )

    def view_items_in_registries(self, items: list[str]) -> str:
        return self._call(TOOL_VIEW, {"items": items})

    def get_item_examples_from_registries(self, query: str, items: list[str]) -> str:
        return self._call(
            TOOL_EXAMPLES, {"registries": [self._registry], "query": query}
        )


def _result_text(result: Any) -> str:
    """Extract concatenated text from an MCP ``CallToolResult`` (defensive)."""
    content = getattr(result, "content", None)
    if content is None and isinstance(result, dict):
        content = result.get("content")
    parts: list[str] = []
    for block in content or []:
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts).strip()


def default_session_factory() -> ShadcnMcpSession:
    """Return a real Agents-SDK stdio session (used when none is injected)."""
    return _AgentsSdkShadcnSession()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def slugify(text: str) -> str:
    """Return a filesystem/registry-safe slug from free text."""
    normalised = unicodedata.normalize("NFKD", text or "")
    ascii_text = "".join(c for c in normalised if not unicodedata.combining(c))
    cleaned = SLUG_DASHES.sub("-", SLUG_CLEAN.sub("-", ascii_text.lower()).strip("-"))
    if not cleaned:
        cleaned = "component"
    if cleaned[0].isdigit():
        cleaned = f"component-{cleaned}"
    return cleaned


def _extract_item_names(text: str, fallback_slug: str) -> list[str]:
    """Pull registry item identifiers from search output, deduped + bounded.

    Falls back to ``@shadcn/<slug>`` when the search text exposes no parseable
    item token, so the view/examples calls still have something to resolve.
    """
    seen: list[str] = []
    for match in _ITEM_TOKEN_RE.findall(text or ""):
        token = match
        if token not in seen:
            seen.append(token)
        if len(seen) >= _MAX_ITEMS:
            break
    if not seen:
        seen = [f"{DEFAULT_REGISTRY}/{fallback_slug}"]
    return seen


def normalize_tsx(text: str) -> str:
    """Return the component source exactly as written (trailing newline)."""
    return text if text.endswith("\n") else text + "\n"


def content_hash(text: str) -> str:
    """Return ``sha256:<digest>`` for the candidate component source.

    Always hashes the normalised (as-written) source so ``intake-info.json``'s
    contentHash matches ``component.tsx`` byte-for-byte.
    """
    return f"sha256:{hashlib.sha256(normalize_tsx(text).encode('utf-8')).hexdigest()}"


def resolve_intake_model(policy_path: Path | None = None) -> str:
    """Return the OpenAI model string for the intake (dossierModel policy)."""
    path = policy_path or DEFAULT_POLICY_PATH
    if not path.exists():
        raise ComponentModelResolutionError(f"llm-models.v1.json missing at {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ComponentModelResolutionError(
            f"llm-models.v1.json is not valid JSON: {exc}"
        ) from exc
    for role in data.get("roles", []):
        if role.get("id") != INTAKE_ROLE_ID:
            continue
        provider = role.get("provider")
        if provider != EXPECTED_PROVIDER:
            raise ComponentModelResolutionError(
                f"{INTAKE_ROLE_ID} provider must be {EXPECTED_PROVIDER!r}, "
                f"got {provider!r}"
            )
        model = role.get("model")
        if not isinstance(model, str) or not model.strip():
            raise ComponentModelResolutionError(
                f"{INTAKE_ROLE_ID} role is missing a non-empty model value"
            )
        return model
    raise ComponentModelResolutionError(
        f"{INTAKE_ROLE_ID} role missing from {path.name}"
    )


def _guard_component_output_dir(output_dir: Path) -> None:
    """Refuse any write into starters or the canonical orchestration tree."""
    guard_candidate_output_dir(
        output_dir,
        forbidden_roots=(STARTERS_DIR, ORCHESTRATION_DIR),
        error_cls=ComponentIntakeError,
        kind="Component",
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def gather_shadcn_material(prompt: str, slug: str, session: ShadcnMcpSession) -> ShadcnGathered:
    """Drive search -> view -> examples against an open MCP session."""
    with session as live:
        search_text = live.search_items_in_registries(prompt)
        items = _extract_item_names(search_text, slug)
        view_text = live.view_items_in_registries(items)
        examples_text = live.get_item_examples_from_registries(prompt, items)
    return ShadcnGathered(
        searchText=search_text,
        viewText=view_text,
        examplesText=examples_text,
        itemsUsed=items,
    )


def synthesize_candidate(
    *,
    prompt: str,
    slug: str,
    gathered: ShadcnGathered,
    model: str,
    openai_client: Any | None = None,
) -> ComponentCandidate:
    """Call the structured-output model to synthesise the candidate component."""
    if openai_client is None:
        from openai import OpenAI

        openai_client = OpenAI()

    payload = {
        "operatorPrompt": prompt,
        "requestedSlug": slug,
        "shadcnSearch": gathered.searchText,
        "shadcnView": gathered.viewText,
        "shadcnExamples": gathered.examplesText,
        "shadcnItemsConsidered": gathered.itemsUsed,
        "hardRules": [
            "Return ONE self-contained candidate component (.tsx) only.",
            "This is a candidate for manual review, not a canonical file.",
            "Prefer zero new dependencies: native elements + the cn helper "
            "(import { cn } from \"@/lib/utils\") when an accessible native "
            "pattern exists; only list a dependency in requiredNpmDeps when the "
            "component genuinely cannot work without it.",
            "List every npm import beyond react in requiredNpmDeps.",
            "List the shadcn registry items you based the component on in "
            "shadcnItemsUsed.",
            "Keep imports stable: components belong under @/components/ui and "
            "helpers under @/lib/utils.",
        ],
    }
    response = openai_client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You curate candidate-only shadcn-based React components for "
                    "Sajtbyggaren's Component Catalog intake. Respect the hard "
                    "rules; never invent dependencies."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, indent=2),
            },
        ],
        text_format=ComponentCandidate,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise ComponentIntakeError(f"{INTAKE_ROLE_ID} returned no structured output")
    return parsed


def _intake_info(
    *,
    prompt: str,
    slug: str,
    model: str,
    candidate: ComponentCandidate,
    gathered: ShadcnGathered,
) -> dict[str, Any]:
    return {
        "intakeInfoVersion": INTAKE_INFO_VERSION,
        "slug": slug,
        "prompt": prompt,
        "model": model,
        "registrySource": DEFAULT_REGISTRY,
        "componentName": candidate.componentName,
        "shadcnItemsUsed": candidate.shadcnItemsUsed or gathered.itemsUsed,
        "requiredNpmDeps": candidate.requiredNpmDeps,
        "contentHash": content_hash(candidate.tsx),
        "notes": candidate.notes,
        "createdAt": created_at(),
        "generatedBy": "scripts/component_intake.py",
    }


def _readme(slug: str, candidate: ComponentCandidate, info: dict[str, Any]) -> str:
    deps = candidate.requiredNpmDeps or ["(inga - zero-dep)"]
    return (
        f"# Komponentkandidat: {slug}\n\n"
        "Genererad av det **kurerade shadcn-intaget** "
        "(`scripts/component_intake.py`, ADR 0054). Detta är en KANDIDAT för "
        "granskning - inte en canonical fil.\n\n"
        "## Härkomst\n"
        f"- Prompt: `{info['prompt']}`\n"
        f"- Modell: `{info['model']}`\n"
        f"- shadcn-items: {', '.join(info['shadcnItemsUsed']) or '(inga)'}\n"
        f"- Innehållshash: `{info['contentHash']}`\n"
        f"- Krävda npm-deps: {', '.join(deps)}\n\n"
        "## Granskningsinstruktion (operatör)\n"
        "1. Läs `component.tsx`. Verifiera tillgänglighet, att inga fakta hittas "
        "på, och att importvägarna är `@/components/ui` + `@/lib/utils`.\n"
        "2. **Beroenden:** kandidaten får INTE dra in ett nytt npm-beroende i en "
        "Starter utan policy + operatörsgodkännande. Om `requiredNpmDeps` inte "
        "redan finns i mål-Startern: behåll det native mönstret i stället.\n"
        "3. Kurera in i en Starter via en EGEN PR: kopiera till "
        "`data/starters/<starterId>/components/ui/`, kör "
        "`python scripts/generate_component_manifests.py` och committa "
        "manifestet.\n"
        "4. Koppla ev. capability → komponent i "
        "`governance/policies/capability-map.v1.json` (`components`-nyckeln, "
        "ADR 0040) så korskontrollen i `scripts/governance_validate.py` blir "
        "grön.\n\n"
        "> Intaget skriver ALDRIG direkt i `data/starters/` eller "
        "`packages/generation/orchestration/`. Promotering är ett "
        "operatörsbeslut via granskad PR.\n"
    )


def write_candidate(
    *,
    output_dir: Path,
    slug: str,
    candidate: ComponentCandidate,
    intake_info: dict[str, Any],
) -> ComponentIntakeResult:
    """Write component.tsx + intake-info.json + README.md for one candidate."""
    candidate_dir = output_dir / slug
    candidate_dir.mkdir(parents=True, exist_ok=True)

    component_path = candidate_dir / "component.tsx"
    intake_info_path = candidate_dir / "intake-info.json"
    readme_path = candidate_dir / "README.md"

    component_path.write_text(normalize_tsx(candidate.tsx), encoding="utf-8")
    intake_info_path.write_text(
        json.dumps(intake_info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    readme_path.write_text(_readme(slug, candidate, intake_info), encoding="utf-8")

    return ComponentIntakeResult(
        candidate_dir=candidate_dir,
        component_path=component_path,
        intake_info_path=intake_info_path,
        readme_path=readme_path,
        intake_info=intake_info,
        model_used=intake_info["model"],
    )


def run_component_intake(
    prompt: str,
    slug: str | None = None,
    *,
    output_dir: Path | None = None,
    session: ShadcnMcpSession | None = None,
    openai_client: Any | None = None,
    model: str | None = None,
    policy_path: Path | None = None,
) -> ComponentIntakeResult:
    """Run the full curated intake and write a component candidate.

    ``session`` / ``openai_client`` are injectable for tests (a mocked MCP
    session + model client keeps CI offline). Without ``OPENAI_API_KEY`` this
    raises ``ComponentIntakeError`` - there is no mock fallback.
    """
    if not prompt or not prompt.strip():
        raise ComponentIntakeError("A non-empty --prompt is required for intake.")

    if not has_openai_api_key():
        raise ComponentIntakeError(
            "Component intake needs a model: set "
            f"{OPENAI_API_KEY_ENV}. There is NO mock fallback - a curated intake "
            "without a model would be a fabricated candidate (ADR 0054)."
        )

    resolved_slug = slugify(slug or prompt)
    resolved_dir = output_dir or DEFAULT_OUTPUT_DIR
    _guard_component_output_dir(resolved_dir)

    resolved_model = model or resolve_intake_model(policy_path)
    live_session = session or default_session_factory()

    gathered = gather_shadcn_material(prompt, resolved_slug, live_session)
    candidate = synthesize_candidate(
        prompt=prompt,
        slug=resolved_slug,
        gathered=gathered,
        model=resolved_model,
        openai_client=openai_client,
    )
    intake_info = _intake_info(
        prompt=prompt,
        slug=resolved_slug,
        model=resolved_model,
        candidate=candidate,
        gathered=gathered,
    )
    return write_candidate(
        output_dir=resolved_dir,
        slug=resolved_slug,
        candidate=candidate,
        intake_info=intake_info,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Curated shadcn component intake (ADR 0054). Spawns its own "
            "`npx shadcn@latest mcp` stdio server and writes a candidate under "
            "data/component-candidates/<slug>/."
        )
    )
    parser.add_argument("--prompt", required=True, help="What component to intake.")
    parser.add_argument("--slug", default=None, help="Candidate slug (default: from prompt).")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override output dir (default: data/component-candidates/).",
    )
    parser.add_argument("--model", default=None, help="Override the model string.")
    args = parser.parse_args(argv)

    try:
        result = run_component_intake(
            args.prompt,
            args.slug,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            model=args.model,
        )
    except ComponentIntakeError as exc:
        print(f"Intake failed: {exc}", file=sys.stderr)
        return 1

    rel = repo_or_output_relative(
        result.candidate_dir, repo_root=REPO_ROOT, output_dir=result.candidate_dir.parent
    )
    print(f"Wrote component candidate to {rel}/ (model={result.model_used})")
    print(f"  - {result.component_path.name}")
    print(f"  - {result.intake_info_path.name}")
    print(f"  - {result.readme_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
