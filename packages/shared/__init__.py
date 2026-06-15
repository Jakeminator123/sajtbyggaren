"""Shared leaf utilities importable by any package (repo-boundaries: packages/shared).

Pure, dependency-light helpers (stdlib only, no upward import into
``packages/generation/**``) so several packages can share ONE source of truth
instead of duplicating logic. ``packages/shared`` is already declared as an
allowed import target across the package boundaries; this is its first module.
"""
