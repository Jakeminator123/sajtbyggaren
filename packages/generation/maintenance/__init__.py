"""Maintenance helpers for Sajtbyggaren.

Modules live here when their job is to keep the repo's data side
clean - retention caps on ``data/runs/``, ``data/prompt-inputs/`` and
the external ``.generated/`` preview root. Not part of the Engine
Run itself; called by callers that start a new generation.
"""

from .auto_prune import (
    MAX_GENERATED_ENV_VAR,
    MAX_PROMPT_INPUTS_ENV_VAR,
    MAX_RUNS_ENV_VAR,
    AutoPruneReport,
    auto_prune_all,
    prune_generated,
    prune_prompt_inputs,
    prune_runs,
)

__all__ = [
    "AutoPruneReport",
    "MAX_GENERATED_ENV_VAR",
    "MAX_PROMPT_INPUTS_ENV_VAR",
    "MAX_RUNS_ENV_VAR",
    "auto_prune_all",
    "prune_generated",
    "prune_prompt_inputs",
    "prune_runs",
]
