"""Cross-policy consistency tests.

These tests guard against drift between policies that schema validation
alone cannot catch. They are the heart of "repot ska inte växa ifrån".
"""

from __future__ import annotations

import re

import pytest


@pytest.mark.governance
def test_default_scaffold_is_in_registry(scaffold_selection: dict, scaffold_contract: dict):
    """`scaffold-selection.v1.fallback.defaultScaffold` must point to a real scaffold."""
    default = scaffold_selection["fallback"]["defaultScaffold"]
    registry_ids = {s["id"] for s in scaffold_contract["primaryScaffoldRegistry"]}
    assert default in registry_ids, (
        f"defaultScaffold '{default}' not in primaryScaffoldRegistry: "
        f"{sorted(registry_ids)}"
    )


@pytest.mark.governance
def test_regression_scaffold_ids_are_real(scaffold_selection: dict, scaffold_contract: dict):
    """Every scaffold id used in regressionTests must be in the registry."""
    registry_ids = {s["id"] for s in scaffold_contract["primaryScaffoldRegistry"]}
    for case in scaffold_selection["regressionTests"]["exampleCases"]:
        expected = case["expectedScaffold"]
        assert expected in registry_ids, (
            f"regressionTests references unknown scaffold '{expected}'. "
            f"Known: {sorted(registry_ids)}"
        )
        for rejected in case.get("mustNotSelect", []):
            assert rejected in registry_ids, (
                f"mustNotSelect references unknown scaffold '{rejected}'."
            )


@pytest.mark.governance
def test_dossier_selection_references_real_scaffold(
    policies: dict[str, dict], scaffold_contract: dict
):
    dossier_selection = policies["dossier-selection.v1.json"]
    registry_ids = {s["id"] for s in scaffold_contract["primaryScaffoldRegistry"]}
    for case in dossier_selection["regressionTests"]["exampleCases"]:
        scaffold_id = case["scaffold"]
        assert scaffold_id in registry_ids, (
            f"dossier-selection regression case uses unknown scaffold "
            f"'{scaffold_id}'."
        )


@pytest.mark.governance
def test_naming_dictionary_aliases_dont_overlap(naming_dictionary: dict):
    """A term cannot have the same alias in both `aliasesAllowed` and `aliasesForbidden`."""
    for term in naming_dictionary["terms"]:
        allowed = set(term.get("aliasesAllowed") or [])
        forbidden = set(term.get("aliasesForbidden") or [])
        overlap = allowed & forbidden
        assert not overlap, (
            f"Term '{term['canonical']}' has overlapping aliasesAllowed and "
            f"aliasesForbidden: {sorted(overlap)}"
        )


@pytest.mark.governance
def test_canonical_terms_are_unique(naming_dictionary: dict):
    canonicals = [t["canonical"] for t in naming_dictionary["terms"]]
    duplicates = {c for c in canonicals if canonicals.count(c) > 1}
    assert not duplicates, f"Duplicate canonical terms: {sorted(duplicates)}"

    ids = [t["id"] for t in naming_dictionary["terms"]]
    duplicate_ids = {i for i in ids if ids.count(i) > 1}
    assert not duplicate_ids, f"Duplicate term ids: {sorted(duplicate_ids)}"


@pytest.mark.governance
def test_globally_forbidden_not_canonical(naming_dictionary: dict):
    """A term cannot be in globallyForbidden and also be a canonical name."""
    canonicals = {t["canonical"].lower() for t in naming_dictionary["terms"]}
    ids = {t["id"].lower() for t in naming_dictionary["terms"]}
    for forbidden in naming_dictionary.get("globallyForbidden", []):
        low = forbidden.lower()
        assert low not in canonicals, (
            f"'{forbidden}' is both canonical and globallyForbidden."
        )
        assert low not in ids, (
            f"'{forbidden}' matches a term id and is globallyForbidden."
        )


@pytest.mark.governance
def test_repo_boundaries_paths_are_unique(repo_boundaries: dict):
    paths = [o["path"] for o in repo_boundaries["ownership"]]
    duplicates = {p for p in paths if paths.count(p) > 1}
    assert not duplicates, f"Duplicate ownership paths: {sorted(duplicates)}"


@pytest.mark.governance
def test_naming_dictionary_owner_packages_align_with_repo_boundaries(
    naming_dictionary: dict, repo_boundaries: dict
):
    """Every term.ownerPackage should map to a repo-boundaries path or an exact root file.

    We accept the root file `backend.py` and the prefix paths in
    ownership[].path. Anything else is a likely typo or a term whose home
    has not been defined.
    """
    boundary_paths = {o["path"].rstrip("/") for o in repo_boundaries["ownership"]}
    boundary_paths.add("backend.py")

    unknown: list[str] = []
    for term in naming_dictionary["terms"]:
        owner = term.get("ownerPackage", "").rstrip("/")
        if not owner:
            unknown.append(f"{term['canonical']} (empty ownerPackage)")
            continue
        if owner in boundary_paths:
            continue
        if any(owner.startswith(p + "/") or owner.startswith(p) for p in boundary_paths if p):
            continue
        unknown.append(f"{term['canonical']} -> {owner}")

    assert not unknown, (
        "Terms have ownerPackage that does not match any repo-boundaries path: "
        + "; ".join(unknown)
    )


@pytest.mark.governance
def test_llm_flow_phase_owner_packages_are_real(llm_flow: dict, repo_boundaries: dict):
    boundary_paths = {o["path"].rstrip("/") for o in repo_boundaries["ownership"]}
    boundary_paths.add("backend.py")
    unknown = []
    for phase in llm_flow["phases"]:
        owner = phase.get("ownerPackage", "").rstrip("/")
        if any(owner.startswith(p) for p in boundary_paths if p):
            continue
        if owner in boundary_paths:
            continue
        unknown.append(f"{phase['canonicalName']} -> {owner}")
    assert not unknown, (
        "llm-flow phases reference unknown ownerPackages: " + "; ".join(unknown)
    )


@pytest.mark.governance
def test_llm_flow_canonical_flow_matches_phase_ids(llm_flow: dict):
    flow_ids = llm_flow["canonicalFlow"]
    phase_ids = [p["id"] for p in llm_flow["phases"]]
    missing = set(flow_ids) - set(phase_ids)
    extra = set(phase_ids) - set(flow_ids)
    assert not missing, (
        f"canonicalFlow references phase ids that don't exist: {sorted(missing)}"
    )
    assert not extra, (
        f"phases include ids not in canonicalFlow: {sorted(extra)}"
    )


@pytest.mark.governance
def test_llm_flow_phase_orders_match_canonical_flow(llm_flow: dict):
    flow_ids = llm_flow["canonicalFlow"]
    phases_by_id = {p["id"]: p for p in llm_flow["phases"]}
    ordered = sorted(flow_ids, key=lambda fid: phases_by_id[fid]["order"])
    assert ordered == flow_ids, (
        "phase.order does not match canonicalFlow ordering. "
        f"canonicalFlow: {flow_ids}, phases sorted by order: {ordered}"
    )


@pytest.mark.governance
def test_quality_target_thresholds_make_sense(page_quality: dict):
    qt = page_quality["qualityTarget"]
    assert qt["blockBelow"] <= qt["gateScore"] <= qt["targetScore"], (
        f"qualityTarget thresholds inconsistent: blockBelow={qt['blockBelow']}, "
        f"gateScore={qt['gateScore']}, targetScore={qt['targetScore']}"
    )


@pytest.mark.governance
def test_quality_traits_weights_sum_to_total(page_quality: dict):
    expected = page_quality["scoring"]["weightsTotal"]
    actual = sum(t["weight"] for t in page_quality["traits"])
    assert actual == expected, (
        f"Sum of trait weights ({actual}) does not equal weightsTotal ({expected})."
    )


@pytest.mark.governance
def test_preview_runtime_default_exists_in_runtimes(preview_runtime_policy: dict):
    default = preview_runtime_policy["default"]
    kinds = {r["kind"] for r in preview_runtime_policy["runtimes"]}
    assert default in kinds, (
        f"default Preview Runtime '{default}' not in runtimes list: {sorted(kinds)}"
    )


@pytest.mark.governance
def test_preview_runtime_forbidden_terms_are_in_globally_forbidden(
    preview_runtime_policy: dict, naming_dictionary: dict
):
    """forbidden terms in preview-runtime should be either:
    - globallyForbidden, or
    - listed as an aliasForbidden under previewRuntime/stackBlitzRuntime/...

    This stops a forbidden term in preview-runtime-policy from being
    accidentally re-introduced as a canonical somewhere else.
    """
    forbidden_in_policy = set(preview_runtime_policy.get("forbiddenTerms", []))
    globally = set(naming_dictionary.get("globallyForbidden", []))
    aliases_forbidden: set[str] = set()
    for term in naming_dictionary["terms"]:
        for alias in term.get("aliasesForbidden") or []:
            aliases_forbidden.add(alias)

    leaked = forbidden_in_policy - globally - aliases_forbidden
    assert not leaked, (
        "forbiddenTerms in preview-runtime-policy are not registered as forbidden "
        "in naming-dictionary: " + ", ".join(sorted(leaked))
    )


@pytest.mark.governance
def test_dossier_classes_are_well_known(dossier_contract: dict):
    classes = {c["class"] for c in dossier_contract["dossierClasses"]}
    assert classes == {"soft", "hybrid", "hard"}, (
        f"dossierClasses must be exactly soft/hybrid/hard, got {sorted(classes)}"
    )


@pytest.mark.governance
def test_scaffold_registry_ids_are_kebab_case(scaffold_contract: dict):
    pattern = re.compile(r"^[a-z][a-z0-9-]*$")
    bad = [s["id"] for s in scaffold_contract["primaryScaffoldRegistry"] if not pattern.match(s["id"])]
    assert not bad, f"Non-kebab-case scaffold ids: {bad}"


@pytest.mark.governance
def test_regression_minimum_count_matches_example_cases(
    scaffold_selection: dict, policies: dict[str, dict]
):
    """`minimumCount` must not exceed the actual `exampleCases` length."""
    dossier_selection = policies["dossier-selection.v1.json"]

    for label, policy in [
        ("scaffold-selection", scaffold_selection),
        ("dossier-selection", dossier_selection),
    ]:
        rt = policy["regressionTests"]
        actual = len(rt["exampleCases"])
        minimum = rt["minimumCount"]
        assert minimum <= actual, (
            f"{label}.regressionTests.minimumCount ({minimum}) exceeds "
            f"exampleCases length ({actual}). Either lower minimumCount "
            f"or add more cases."
        )


@pytest.mark.governance
def test_llm_flow_phase_owners_match_repo_boundaries(
    llm_flow: dict, repo_boundaries: dict
):
    """Every llm-flow phase ownerPackage must be a path that exists in repo-boundaries."""
    boundary_paths = {o["path"].rstrip("/") for o in repo_boundaries["ownership"]}
    boundary_paths.add("backend.py")

    bad = []
    for phase in llm_flow["phases"]:
        owner = phase.get("ownerPackage", "").rstrip("/")
        if not owner:
            bad.append(f"{phase['canonicalName']} has no ownerPackage")
            continue
        if owner not in boundary_paths and not any(
            owner.startswith(p + "/") or owner == p for p in boundary_paths if p
        ):
            bad.append(f"{phase['canonicalName']} -> {owner}")
    assert not bad, f"llm-flow phase owners not in repo-boundaries: {bad}"


@pytest.mark.governance
def test_phase_blocks_cover_all_phases(llm_flow: dict):
    """phaseBlocks must reference every phase id exactly once."""
    phase_ids = {p["id"] for p in llm_flow["phases"]}
    block_phase_ids: list[str] = []
    for block in llm_flow["phaseBlocks"]:
        block_phase_ids.extend(block["phaseIds"])

    missing = phase_ids - set(block_phase_ids)
    assert not missing, f"phaseBlocks miss phase ids: {sorted(missing)}"

    extra = set(block_phase_ids) - phase_ids
    assert not extra, f"phaseBlocks reference unknown phase ids: {sorted(extra)}"

    duplicates = [pid for pid in block_phase_ids if block_phase_ids.count(pid) > 1]
    assert not duplicates, f"Phase id appears in multiple blocks: {sorted(set(duplicates))}"


@pytest.mark.governance
def test_engine_run_modes_are_init_and_followup(engine_run_policy: dict):
    modes = engine_run_policy["modes"]
    assert set(modes.keys()) == {"init", "followup"}
    assert modes["init"]["writesProjectDna"] is True
    assert modes["init"]["readsProjectDna"] is False
    assert modes["followup"]["writesProjectDna"] is False
    assert modes["followup"]["readsProjectDna"] is True
    assert modes["followup"]["requiresProjectId"] is True


@pytest.mark.governance
def test_embedding_policy_owner_paths_exist(
    embedding_policy: dict, repo_boundaries: dict
):
    boundary_paths = {o["path"].rstrip("/") for o in repo_boundaries["ownership"]}
    bad = []
    for domain in embedding_policy["domains"]:
        owner = domain.get("ownerPackage", "").rstrip("/")
        if not any(owner.startswith(p) for p in boundary_paths if p):
            bad.append(f"{domain['id']} -> {owner}")
    assert not bad, f"embedding-policy domains owner paths not in repo-boundaries: {bad}"


@pytest.mark.governance
def test_embedding_policy_consumes_real_phases_and_roles(
    embedding_policy: dict, llm_flow: dict, llm_models: dict
):
    phase_ids = {p["id"] for p in llm_flow["phases"]}
    role_ids = {r["id"] for r in llm_models["roles"]}

    for domain in embedding_policy["domains"]:
        for phase in domain["consumedByPhases"]:
            assert phase in phase_ids, (
                f"embedding domain {domain['id']} references unknown phase '{phase}'"
            )
        for role in domain["consumedByRoles"]:
            assert role in role_ids, (
                f"embedding domain {domain['id']} references unknown model role '{role}'"
            )


@pytest.mark.governance
def test_fix_registry_llm_fixes_reference_real_model_roles(
    fix_registry: dict, llm_models: dict
):
    role_ids = {r["id"] for r in llm_models["roles"]}
    for fix in fix_registry["llmFixes"]:
        assert fix["modelRole"] in role_ids, (
            f"LLM fix {fix['id']} references unknown model role {fix['modelRole']}"
        )


@pytest.mark.governance
def test_fix_registry_stages_referenced_by_mechanical_fixes(fix_registry: dict):
    valid_stages = set(fix_registry["stages"])
    for fix in fix_registry["mechanicalFixes"]:
        assert fix["stage"] in valid_stages, (
            f"mechanical fix {fix['id']} uses unknown stage {fix['stage']}"
        )


@pytest.mark.governance
def test_shared_model_groups_cover_every_role(llm_models: dict):
    role_ids = {r["id"] for r in llm_models["roles"]}
    grouped: list[str] = []
    for group in llm_models["sharedModelGroups"]:
        grouped.extend(group["roles"])
    assert set(grouped) == role_ids, (
        "Every model role must belong to exactly one sharedModelGroup. "
        f"Difference: {role_ids.symmetric_difference(grouped)}"
    )


@pytest.mark.governance
def test_project_dna_intents_match_followup_intent_term(
    project_dna_policy: dict, naming_dictionary: dict
):
    """The followUpIntent term in naming-dictionary must list the same intents."""
    term = next(
        (t for t in naming_dictionary["terms"] if t["id"] == "followUpIntent"),
        None,
    )
    assert term is not None, "followUpIntent term missing from naming-dictionary"
    intents_in_dna = {i["id"] for i in project_dna_policy["followUpIntents"]}
    assert "redesign" in intents_in_dna and "clarify" in intents_in_dna
    # The term's definition should mention 'classification' so we know it is canonical.
    assert "klassificering" in term["definition"].lower() or "classification" in term["definition"].lower()
