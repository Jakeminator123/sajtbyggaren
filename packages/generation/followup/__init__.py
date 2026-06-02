"""Follow-up processing subpackage.

Houses the copyDirective subsystem (ADR 0034 väg A, nivå 1-3a) extracted from
``scripts/prompt_to_project_input.py`` in a behavior-preserving module
extraction (2026-06-02). ``text`` holds the shared low-level text helpers used
by both the copyDirective code and the intent classification / semantic patch
path that stays in ``scripts.prompt_to_project_input``; ``copy_directives``
holds the deterministic extractor, copyDirectiveModel extraction, editPlan
planner, validation, grounding guard and apply chain.

The follow-up orchestration (``merge_followup_project_input``) and the
intent-coupled ``_copy_directive_llm_eligible`` remain in
``scripts.prompt_to_project_input``.
"""
