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
VIEWER_PANEL = REPO_ROOT / "apps" / "viewser" / "components" / "viewer-panel.tsx"


def _load_config_source() -> str:
    assert NEXT_CONFIG.exists(), (
        f"Expected {NEXT_CONFIG} to exist; if it was renamed, update this test."
    )
    return NEXT_CONFIG.read_text(encoding="utf-8")


def _load_viewer_panel_source() -> str:
    assert VIEWER_PANEL.exists(), (
        f"Expected {VIEWER_PANEL} to exist; if it was renamed, update this test."
    )
    return VIEWER_PANEL.read_text(encoding="utf-8")


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


# --------------------------------------------------------------------------
# Source-locks for the iframe-credentialless attribute injection (B124).
#
# Parent COEP `credentialless` is necessary but not sufficient: each
# embedded iframe additionally needs either its own COEP response header
# (which StackBlitz's embed does not send) or the `credentialless` HTML
# attribute on the <iframe> element. Without it Chrome refuses to load
# the embed and shows "Specify a Cross-Origin Embedder Policy to prevent
# this frame from being blocked" in DevTools.
#
# ViewerPanel patches document.createElement around sdk.embedProject so
# the iframe StackBlitz creates internally is tagged before insertion.
# These tests lock that mechanism in place.
# --------------------------------------------------------------------------


def test_viewer_panel_patches_create_element_for_credentialless_iframe() -> None:
    """ViewerPanel must intercept iframe creation and tag it credentialless."""
    source = _load_viewer_panel_source()
    assert "document.createElement" in source, (
        "viewer-panel.tsx must reference document.createElement somewhere — "
        "either to create the mount target or to patch the SDK's iframe "
        "creation. Removing all references is a regression."
    )
    assert 'setAttribute("credentialless"' in source, (
        "viewer-panel.tsx must call setAttribute('credentialless', ...) on "
        "the StackBlitz iframe. Without it Chrome blocks the embed under our "
        "host's Cross-Origin-Embedder-Policy: credentialless. See "
        "https://developer.chrome.com/blog/iframe-credentialless"
    )


def test_viewer_panel_restores_create_element_in_finally() -> None:
    """The createElement patch must be reverted so we never leak the override."""
    source = _load_viewer_panel_source()
    assert "originalCreateElement" in source, (
        "viewer-panel.tsx must hold a reference to the original "
        "document.createElement so it can be restored after embedProject."
    )
    assert "} finally {" in source and "document.createElement = originalCreateElement" in source, (
        "viewer-panel.tsx must restore document.createElement in a finally "
        "block — leaving the patch in place would mean every future iframe "
        "created elsewhere on the page also gets the credentialless "
        "attribute, which has surprising security implications."
    )


def test_viewer_panel_only_tags_iframe_elements() -> None:
    """The patch must scope to <iframe> only, not every createElement call."""
    source = _load_viewer_panel_source()
    assert 'tagName.toLowerCase() === "iframe"' in source, (
        "The createElement patch must guard on tagName.toLowerCase() === "
        "'iframe' so only the StackBlitz iframe gets the credentialless "
        "attribute. Tagging arbitrary elements is incorrect (the attribute "
        "is iframe-specific) and obscures the intent of the patch."
    )
