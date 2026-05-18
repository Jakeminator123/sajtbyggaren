"""Source-lock for the cross-origin isolation headers in apps/viewser.

`apps/viewser/components/viewer-panel.tsx` embeds StackBlitz via
`sdk.embedProject(..., { template: "node" })`, which boots a WebContainer
inside the iframe. WebContainers require `SharedArrayBuffer`, which only
works on a cross-origin-isolated document. The host (this Next.js app)
must therefore send `Cross-Origin-Embedder-Policy` and
`Cross-Origin-Opener-Policy` headers — without them StackBlitz renders
"Unable to run Embedded Project" instead of the preview.

We use `credentialless` rather than `require-corp` for the embedder
policy because we embed third-party iframe resources (stackblitz.com)
whose `Cross-Origin-Resource-Policy` headers we cannot control.
StackBlitz documents `credentialless` as the correct mode for that
case in
https://developer.stackblitz.com/platform/webcontainers/browser-support#embedding

These tests lock the source so a future refactor cannot accidentally
revert the headers and re-break the preview, and so a future contributor
cannot quietly switch to `require-corp` without thinking about the
embed implications.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NEXT_CONFIG = REPO_ROOT / "apps" / "viewser" / "next.config.ts"


def _load_config_source() -> str:
    assert NEXT_CONFIG.exists(), (
        f"Expected {NEXT_CONFIG} to exist; if it was renamed, update this test."
    )
    return NEXT_CONFIG.read_text(encoding="utf-8")


def test_next_config_sets_cross_origin_embedder_policy() -> None:
    """The Next.js host must send COEP so StackBlitz embed can boot."""
    source = _load_config_source()
    assert "Cross-Origin-Embedder-Policy" in source, (
        "apps/viewser/next.config.ts must declare Cross-Origin-Embedder-Policy. "
        "Removing it re-breaks the StackBlitz preview ('Unable to run Embedded Project')."
    )


def test_next_config_uses_credentialless_for_embed_case() -> None:
    """`credentialless` is the embedder mode that supports embedding stackblitz.com."""
    source = _load_config_source()
    assert "credentialless" in source, (
        "Cross-Origin-Embedder-Policy must be 'credentialless', not 'require-corp'. "
        "We embed stackblitz.com iframe whose resources we cannot tag with CORP "
        "headers, so require-corp would block the embed. See StackBlitz browser-"
        "support docs (#embedding section) for rationale."
    )


def test_next_config_sets_cross_origin_opener_policy_same_origin() -> None:
    """COOP: same-origin is required alongside COEP for cross-origin isolation."""
    source = _load_config_source()
    assert "Cross-Origin-Opener-Policy" in source, (
        "apps/viewser/next.config.ts must declare Cross-Origin-Opener-Policy."
    )
    assert "same-origin" in source, (
        "Cross-Origin-Opener-Policy must be 'same-origin' so the document is "
        "considered cross-origin isolated. Without it, SharedArrayBuffer is "
        "unavailable and the StackBlitz embed will not boot."
    )


def test_next_config_headers_apply_to_all_routes() -> None:
    """Headers must cover the route that hosts <ViewerPanel>, i.e. all routes."""
    source = _load_config_source()
    assert '"/:path*"' in source or "'/:path*'" in source, (
        "next.config.ts headers() must use source: '/:path*' so the isolation "
        "headers apply to the page rendering ViewerPanel (and to every preview "
        "and API route the embed touches)."
    )
