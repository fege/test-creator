"""Regression contracts for the deterministic Scope Fidelity and Actionability evidence gate."""

import pytest

from scripts.utils.schemas import TEMPLATE_HEADINGS
from scripts.validate_quality_evidence import (
    _logical_entries,
    _unresolved_tbd_fields,
    validate_actionability,
    validate_scope_coverage,
)
from tests.consts.validation_constants import (
    ACTIONABILITY_ADVISORY_GAPS_PLAN,
    ACTIONABILITY_ARBITRARY_BACKTICK_TOKEN_PLAN,
    ACTIONABILITY_ARTIFACT_LIKE_PLAN,
    ACTIONABILITY_ARTIFACT_LIKE_VERSION_DATA_PLAN,
    ACTIONABILITY_ARTIFACT_LIKE_OPENSHIFT_BARE_TBD_PLAN,
    ACTIONABILITY_ARTIFACT_LIKE_RHOAI_BARE_TBD_PLAN,
    ACTIONABILITY_ARTIFACT_LIKE_RHOAI_EXACT_BUILD_RESOLVED_TBD_PLAN,
    ACTIONABILITY_BROAD_RBAC_TABLE_PLANS,
    ACTIONABILITY_BARE_TBD_VISIBILITY_PLAN,
    ACTIONABILITY_CONCRETE_DATA_WITH_BARE_TBD_PLAN,
    ACTIONABILITY_CONCRETE_DATA_WITH_RESOLVED_TBD_PLAN,
    ACTIONABILITY_CONCRETE_PROSE_RBAC_PLAN,
    ACTIONABILITY_CONCRETE_VERSION_LABELS_PLAN,
    ACTIONABILITY_DELIMITED_DATA_PLACEHOLDER_PLAN,
    ACTIONABILITY_EG_CONCRETE_VALUE_PLAN,
    ACTIONABILITY_FOR_EXAMPLE_CONCRETE_VALUE_PLAN,
    ACTIONABILITY_FORMATTED_RBAC_TABLE_PLANS,
    ACTIONABILITY_GENERIC_EXAMPLE_PLANS,
    ACTIONABILITY_GENERIC_TBD_CONFIGURATION_PLAN,
    ACTIONABILITY_GENERIC_PROSE_RBAC_PLAN,
    ACTIONABILITY_JUSTIFIED_TBD_PLAN,
    ACTIONABILITY_JUSTIFIED_TBD_RESOLUTION,
    ACTIONABILITY_MISSING_VERSION_DATA_PLAN,
    ACTIONABILITY_NON_SUBSTANTIVE_INFRASTRUCTURE_PLAN,
    ACTIONABILITY_PROSE_RBAC_PLAN,
    ACTIONABILITY_RBAC_TBD_PROSE_PLAN,
    ACTIONABILITY_RBAC_UNRESOLVED_TBD_PROSE_PLAN,
    ACTIONABILITY_RBAC_WITHOUT_RESOURCE_PLAN,
    ACTIONABILITY_RESOLVED_TBD_DATA_AND_RBAC_PLAN,
    ACTIONABILITY_RESOLVED_TBD_VISIBILITY_LABELS,
    ACTIONABILITY_RESOLVED_TBD_VISIBILITY_PLAN,
    ACTIONABILITY_RESOLUTION_TARGET_BOUNDARY_CASES,
    ACTIONABILITY_TBD_DATA_PLAN,
    ACTIONABILITY_TBD_UNKNOWN_PLAN,
    ACTIONABILITY_UNRESOLVED_TBD_VISIBILITY_PLAN,
    ACTIONABILITY_YAML_EXAMPLE_VALUE_PLAN,
    ACTIONABILITY_WRAPPED_GENERIC_RBAC_RESOLUTION_PLAN,
    ACTIONABILITY_WRAPPED_PLURAL_OWNER_RBAC_RESOLUTION_PLAN,
    ACTIONABILITY_WRAPPED_RBAC_RESOLUTION_PLAN,
    FULLY_MAPPED_SCOPE_PLAN,
    LOGICAL_MARKDOWN_ENTRY_CASES,
    NOT_APPLICABLE_NFR_CASES,
    NOT_APPLICABLE_NFR_SECTIONS,
    OCCURRENCE_LEVEL_TBD_CASES,
    QUALITY_EVIDENCE_OBJECTIVES_SECTION,
    QUALITY_EVIDENCE_STRATEGY,
    UNMAPPED_SCOPE_CASES,
)


def _visible_actionability_advisories(result):
    """Support the current advisory list and an explicitly named resolved-TBD equivalent."""
    return [*result.get("advisory_gaps", []), *result.get("resolved_tbd", [])]


class TestValidateScopeCoverage:
    @pytest.mark.parametrize(
        "section, section_content, expected_text",
        UNMAPPED_SCOPE_CASES,
        ids=("scope", "priorities", "disconnected", "upgrade", "performance", "rbac", "security", "risks"),
    )
    def test_rejects_scope_entries_without_explicit_objective_mapping(
        self, tmp_path, section, section_content, expected_text
    ):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(f"{QUALITY_EVIDENCE_OBJECTIVES_SECTION}\n\n{section_content}\n")

        result = validate_scope_coverage(str(plan), QUALITY_EVIDENCE_STRATEGY)

        assert result["valid"] is False
        assert {
            "section": section,
            "text": expected_text,
            "reason": "no Section 1.3 objective mapping",
        } in result["missing"]

    def test_accepts_explicit_scope_to_objective_to_strategy_mapping(self, tmp_path):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(FULLY_MAPPED_SCOPE_PLAN)

        result = validate_scope_coverage(str(plan), QUALITY_EVIDENCE_STRATEGY)

        assert result == {"valid": True, "missing": [], "unmapped_objectives": []}

    @pytest.mark.parametrize("section", ("1.2", "2.3", "7.1", "7.2", "7.3", "7.4", "7.5"))
    def test_rejects_unmarked_numbered_scope_entry_when_an_earlier_entry_is_marked(self, tmp_path, section):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(
            f"{QUALITY_EVIDENCE_OBJECTIVES_SECTION}\n\n"
            f"{TEMPLATE_HEADINGS[section]}\n\n"
            "1. First scope entry (Objective: #1)\n"
            "2. Second scope entry\n"
        )

        result = validate_scope_coverage(str(plan), QUALITY_EVIDENCE_STRATEGY)

        assert result["valid"] is False
        assert {
            "section": section,
            "text": "Second scope entry",
            "reason": "no Section 1.3 objective mapping",
        } in result["missing"]

    @pytest.mark.parametrize("section", ("1.2", "2.3", "7.1", "7.2", "7.3", "7.4", "7.5"))
    def test_accepts_fully_marked_numbered_scope_entries(self, tmp_path, section):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(
            f"{QUALITY_EVIDENCE_OBJECTIVES_SECTION}\n\n"
            f"{TEMPLATE_HEADINGS[section]}\n\n"
            "1. First scope entry (Objective: #1)\n"
            "2. Second scope entry (Objective: #1)\n"
        )

        result = validate_scope_coverage(str(plan), QUALITY_EVIDENCE_STRATEGY)

        assert result == {"valid": True, "missing": [], "unmapped_objectives": []}

    @pytest.mark.parametrize("section, section_content", NOT_APPLICABLE_NFR_CASES, ids=NOT_APPLICABLE_NFR_SECTIONS)
    def test_accepts_ungrounded_not_applicable_nfr_entry_without_objective_marker(
        self, tmp_path, section, section_content
    ):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(section_content)

        result = validate_scope_coverage(str(plan), QUALITY_EVIDENCE_STRATEGY)

        assert result == {"valid": True, "missing": [], "unmapped_objectives": []}

    @pytest.mark.parametrize("section", ("1.2", "2.3", "8"))
    def test_rejects_not_applicable_wording_outside_nfr_sections(self, tmp_path, section):
        """The exemption is specific to Section 7.1-7.5; it's not a blanket "Not Applicable" bypass."""
        plan = tmp_path / "TestPlan.md"
        section_body = (
            "| Risk | Impact | Probability | Mitigation |\n"
            "|------|--------|-------------|------------|\n"
            "| **Not Applicable** | Low | Low | No mitigation needed |"
            if section == "8"
            else "**Not Applicable** — this feature has no grounding for this category."
        )
        plan.write_text(f"{QUALITY_EVIDENCE_OBJECTIVES_SECTION}\n\n{TEMPLATE_HEADINGS[section]}\n\n{section_body}\n")

        result = validate_scope_coverage(str(plan), QUALITY_EVIDENCE_STRATEGY)

        assert result["valid"] is False


class TestActionabilityMarkdownEntryParsing:
    @pytest.mark.parametrize(
        "section_text, expected_entries",
        LOGICAL_MARKDOWN_ENTRY_CASES,
        ids=("wrapped-bullet", "paragraph-and-numbered-entry"),
    )
    def test_joins_wrapped_markdown_lines_into_logical_entries(self, section_text, expected_entries):
        assert _logical_entries(section_text) == expected_entries

    @pytest.mark.parametrize(
        "section_text, expected_unresolved",
        OCCURRENCE_LEVEL_TBD_CASES,
        ids=("wrapped-resolution-does-not-leak", "later-resolution-does-not-rescue-earlier", "two-bare-values"),
    )
    def test_classifies_each_tbd_occurrence_independently(self, section_text, expected_unresolved):
        assert _unresolved_tbd_fields(section_text) == expected_unresolved


class TestValidateActionability:
    @pytest.mark.parametrize(
        "plan_content",
        (
            pytest.param(
                ACTIONABILITY_ARTIFACT_LIKE_VERSION_DATA_PLAN,
                id="artifact-like-labels-and-wrapped-values",
            ),
            pytest.param(ACTIONABILITY_CONCRETE_VERSION_LABELS_PLAN, id="concrete-equivalent-labels-and-values"),
        ),
    )
    def test_recognizes_equivalent_version_labels_wrapped_values_and_hf_test_data(self, tmp_path, plan_content):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(plan_content)

        result = validate_actionability(str(plan))

        assert result["valid"] is True
        assert result["bare_tbd"] == []
        assert result["missing_details"] == []
        assert "test data formats and examples" not in result["advisory_gaps"]

    def test_recognizes_artifact_like_plural_test_users_as_concrete_rbac_evidence(self, tmp_path):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(ACTIONABILITY_ARTIFACT_LIKE_PLAN)

        result = validate_actionability(str(plan))

        assert result["valid"] is True
        assert result["bare_tbd"] == []
        assert result["missing_details"] == []

    def test_artifact_like_open_shift_bare_tbd_remains_blocking_without_masking_resolved_rhoai(self, tmp_path):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(ACTIONABILITY_ARTIFACT_LIKE_OPENSHIFT_BARE_TBD_PLAN)

        result = validate_actionability(str(plan))

        assert result["valid"] is False
        assert result["bare_tbd"] == ["OpenShift version"]
        assert result["advisory_gaps"] == ["RHOAI version"]

    def test_artifact_like_resolved_rhoai_exact_build_tbd_is_non_blocking_and_canonical(self, tmp_path):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(ACTIONABILITY_ARTIFACT_LIKE_RHOAI_EXACT_BUILD_RESOLVED_TBD_PLAN)

        result = validate_actionability(str(plan))

        assert result["valid"] is True
        assert result["bare_tbd"] == []
        assert result["missing_details"] == []
        assert result["advisory_gaps"] == ["RHOAI version"]

    @pytest.mark.parametrize(
        "plan_content, expected_valid, expected_missing_details",
        (
            pytest.param(
                ACTIONABILITY_NON_SUBSTANTIVE_INFRASTRUCTURE_PLAN,
                False,
                ["environment versions and configuration"],
                id="non-substantive-environment-details-are-blocking",
            ),
            pytest.param(
                ACTIONABILITY_CONCRETE_VERSION_LABELS_PLAN,
                True,
                [],
                id="meaningful-environment-evidence-passes",
            ),
        ),
    )
    def test_requires_substantive_section_3_1_environment_configuration_evidence(
        self, tmp_path, plan_content, expected_valid, expected_missing_details
    ):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(plan_content)

        result = validate_actionability(str(plan))

        assert result["valid"] is expected_valid
        assert result["missing_details"] == expected_missing_details

    @pytest.mark.parametrize(
        "plan_content, expected_bare_tbd, expected_advisory",
        (
            pytest.param(
                ACTIONABILITY_ARTIFACT_LIKE_OPENSHIFT_BARE_TBD_PLAN,
                "OpenShift version",
                "RHOAI version",
                id="wrapped-openshift-boundary-does-not-mask-rhoai",
            ),
            pytest.param(
                ACTIONABILITY_ARTIFACT_LIKE_RHOAI_BARE_TBD_PLAN,
                "RHOAI version",
                "OpenShift version",
                id="wrapped-rhoai-boundary-does-not-mask-openshift",
            ),
        ),
    )
    def test_wrapped_artifact_like_version_fields_are_classified_independently(
        self, tmp_path, plan_content, expected_bare_tbd, expected_advisory
    ):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(plan_content)

        result = validate_actionability(str(plan))

        assert result["valid"] is False
        assert result["bare_tbd"] == [expected_bare_tbd]
        assert result["advisory_gaps"] == [expected_advisory]

    @pytest.mark.parametrize(
        "plan_content",
        (
            pytest.param(ACTIONABILITY_ADVISORY_GAPS_PLAN, id="vague-version-and-data-details"),
            pytest.param(ACTIONABILITY_MISSING_VERSION_DATA_PLAN, id="missing-version-and-data-details"),
        ),
    )
    def test_reports_missing_or_vague_versions_and_test_data_as_advisory_gaps(self, tmp_path, plan_content):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(plan_content)

        result = validate_actionability(str(plan))

        assert result["valid"] is True
        assert result["bare_tbd"] == []
        assert result["missing_details"] == []
        assert {
            "OpenShift version",
            "RHOAI version",
            "test data formats and examples",
        } <= set(result["advisory_gaps"])

    @pytest.mark.parametrize(
        "plan_content, expected_bare_tbd, expected_missing_detail",
        [
            pytest.param(
                ACTIONABILITY_TBD_UNKNOWN_PLAN,
                "OpenShift version",
                None,
                id="unknown-is-not-a-tbd-resolution-path",
            ),
            pytest.param(
                ACTIONABILITY_TBD_DATA_PLAN,
                None,
                "test data formats and examples",
                id="tbd-format-and-example-are-not-test-data-evidence",
            ),
            pytest.param(
                ACTIONABILITY_PROSE_RBAC_PLAN,
                None,
                "RBAC roles and permissions",
                id="rbac-keywords-without-a-permission-grant-are-insufficient",
            ),
        ],
    )
    def test_rejects_weak_operational_evidence(
        self, tmp_path, plan_content, expected_bare_tbd, expected_missing_detail
    ):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(plan_content)

        result = validate_actionability(str(plan))

        assert result["valid"] is False
        assert result["advisory_gaps"] == []
        if expected_bare_tbd:
            assert expected_bare_tbd in result["bare_tbd"]
        if expected_missing_detail:
            assert expected_missing_detail in result["missing_details"]

    def test_preserves_tbd_with_an_explicit_resolution_path(self, tmp_path):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(ACTIONABILITY_JUSTIFIED_TBD_PLAN)

        result = validate_actionability(str(plan))

        assert result["valid"] is True
        assert result["bare_tbd"] == []
        assert result["missing_details"] == []
        assert any("OpenShift version" in advisory for advisory in _visible_actionability_advisories(result))

    def test_rejects_tbd_resolution_without_the_required_label(self, tmp_path):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(ACTIONABILITY_JUSTIFIED_TBD_PLAN.replace("TBD — Resolution: ", "TBD — "))

        result = validate_actionability(str(plan))

        assert result["valid"] is False
        assert "OpenShift version" in result["bare_tbd"]
        assert result["advisory_gaps"] == []

    @pytest.mark.parametrize(
        "resolution",
        (
            "before environment setup",
            "from platform engineering",
            "from the supported-platform matrix",
        ),
        ids=(
            "actionless-concrete-timing-is-rejected",
            "actionless-named-owner-is-rejected",
            "actionless-named-source-is-rejected",
        ),
    )
    def test_tbd_resolution_requires_a_concrete_action_even_with_substantive_infrastructure(self, tmp_path, resolution):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(ACTIONABILITY_JUSTIFIED_TBD_PLAN.replace(ACTIONABILITY_JUSTIFIED_TBD_RESOLUTION, resolution))

        result = validate_actionability(str(plan))

        assert result == {
            "valid": False,
            "bare_tbd": ["OpenShift version"],
            "missing_details": [],
            "advisory_gaps": [],
        }

    @pytest.mark.parametrize(
        "resolution, expected_valid",
        ACTIONABILITY_RESOLUTION_TARGET_BOUNDARY_CASES,
        ids=(
            "generic-unnamed-owner-is-rejected",
            "generic-test-team-target-is-rejected",
            "generic-bare-team-target-is-rejected",
            "generic-owner-target-is-rejected",
            "generic-engineering-target-is-rejected",
            "generic-engineering-team-target-is-rejected",
            "generic-test-engineering-team-target-is-rejected",
            "wrapped-target-is-not-rescued-by-indented-owner-field",
            "named-owner-is-accepted",
            "concrete-timing-is-accepted",
            "concrete-decision-timing-is-accepted",
            "named-issue-source-is-accepted",
            "generic-bare-plural-teams-target-is-rejected",
            "generic-plural-test-teams-target-is-rejected",
            "generic-plural-owners-target-is-rejected",
            "generic-plural-engineering-teams-target-is-rejected",
            "named-plural-teams-owner-is-accepted",
            "named-plural-maintainers-owner-is-accepted",
        ),
    )
    def test_resolution_target_boundary_rejects_generic_targets_even_with_substantive_infrastructure(
        self, tmp_path, resolution, expected_valid
    ):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(ACTIONABILITY_JUSTIFIED_TBD_PLAN.replace(ACTIONABILITY_JUSTIFIED_TBD_RESOLUTION, resolution))

        result = validate_actionability(str(plan))

        assert result["valid"] is expected_valid
        assert result["bare_tbd"] == ([] if expected_valid else ["OpenShift version"])
        assert result["missing_details"] == []
        if expected_valid:
            assert any("OpenShift version" in advisory for advisory in _visible_actionability_advisories(result))
        else:
            assert result["advisory_gaps"] == []

    @pytest.mark.parametrize(
        "plan_content, expected_valid",
        (
            pytest.param(
                ACTIONABILITY_WRAPPED_RBAC_RESOLUTION_PLAN,
                True,
                id="wrapped-platform-owner-is-resolved-and-visible",
            ),
            pytest.param(
                ACTIONABILITY_WRAPPED_PLURAL_OWNER_RBAC_RESOLUTION_PLAN,
                True,
                id="wrapped-plural-platform-teams-owner-is-resolved-and-visible",
            ),
            pytest.param(
                ACTIONABILITY_WRAPPED_GENERIC_RBAC_RESOLUTION_PLAN,
                False,
                id="wrapped-generic-owner-remains-blocking",
            ),
        ),
    )
    def test_wrapped_rbac_resolution_accepts_named_platform_owner_but_rejects_generic_owner(
        self, tmp_path, plan_content, expected_valid
    ):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(plan_content)

        result = validate_actionability(str(plan))

        assert result["valid"] is expected_valid
        if expected_valid:
            assert result["bare_tbd"] == []
            assert result["missing_details"] == []
            assert "RBAC roles and permissions" in result["advisory_gaps"]
        else:
            assert "RBAC roles and permissions" in result["missing_details"]

    def test_rejects_rbac_table_permissions_without_a_concrete_resource(self, tmp_path):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(ACTIONABILITY_RBAC_WITHOUT_RESOURCE_PLAN)

        result = validate_actionability(str(plan))

        assert result["valid"] is False
        assert "RBAC roles and permissions" in result["missing_details"]
        assert result["advisory_gaps"] == []

    @pytest.mark.parametrize(
        "plan_content",
        ACTIONABILITY_FORMATTED_RBAC_TABLE_PLANS,
        ids=("bold-resource-cell", "backticked-resource-cell"),
    )
    def test_accepts_markdown_formatted_rbac_table_resource_cells(self, tmp_path, plan_content):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(plan_content)

        result = validate_actionability(str(plan))

        assert result["valid"] is True
        assert result["missing_details"] == []

    @pytest.mark.parametrize(
        "plan_content",
        ACTIONABILITY_BROAD_RBAC_TABLE_PLANS,
        ids=(
            "all-namespaces",
            "all-projects",
            "any-resources",
            "all-vector-store-resources",
            "every-service-account",
            "table-literal-resource-wildcard-is-rejected",
            "bold-wrapped-table-resource-wildcard-is-rejected",
            "backticked-table-resource-wildcard-is-rejected",
        ),
    )
    def test_rejects_broad_rbac_table_resource_collections(self, tmp_path, plan_content):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(plan_content)

        result = validate_actionability(str(plan))

        assert result["valid"] is False
        assert result["missing_details"] == ["RBAC roles and permissions"]
        assert result["advisory_gaps"] == []

    @pytest.mark.parametrize(
        "plan_content, expected_valid",
        (
            pytest.param(
                ACTIONABILITY_GENERIC_PROSE_RBAC_PLAN,
                False,
                id="generic-resource-prose-is-insufficient",
            ),
            pytest.param(
                ACTIONABILITY_GENERIC_PROSE_RBAC_PLAN.replace("all resources", "all namespaces"),
                False,
                id="broad-namespaces-prose-is-insufficient",
            ),
            pytest.param(
                ACTIONABILITY_CONCRETE_PROSE_RBAC_PLAN.replace("vector-store resources", "all vector-store resources"),
                False,
                id="broad-named-resource-prose-is-insufficient",
            ),
            pytest.param(
                ACTIONABILITY_CONCRETE_PROSE_RBAC_PLAN,
                True,
                id="concrete-resource-prose-is-accepted",
            ),
            pytest.param(
                ACTIONABILITY_CONCRETE_PROSE_RBAC_PLAN.replace(
                    "The qe-test-user can create, get, and delete vector-store resources.",
                    "**The qe-test-user can create, get, and delete vector-store resources.**",
                ),
                True,
                id="bold-concrete-prose-is-accepted",
            ),
            pytest.param(
                ACTIONABILITY_CONCRETE_PROSE_RBAC_PLAN.replace(
                    "vector-store resources.", "**vector-store resources**."
                ),
                True,
                id="bold-concrete-resource-name-is-accepted",
            ),
            pytest.param(
                ACTIONABILITY_CONCRETE_PROSE_RBAC_PLAN.replace("vector-store resources.", "`vector-store resources`."),
                True,
                id="backticked-concrete-resource-name-is-accepted",
            ),
            pytest.param(
                ACTIONABILITY_CONCRETE_PROSE_RBAC_PLAN.replace(
                    "The qe-test-user can create, get, and delete vector-store resources.",
                    "* The qe-test-user can create, get, and delete vector-store resources.",
                ),
                True,
                id="star-bullet-concrete-prose-is-accepted",
            ),
            pytest.param(
                ACTIONABILITY_CONCRETE_PROSE_RBAC_PLAN.replace(
                    "The qe-test-user can create, get, and delete vector-store resources.",
                    "The qe-test-user has permissions to create, get, and delete vector-store resources.",
                ),
                True,
                id="plural-permissions-without-singular-alternative-is-accepted",
            ),
            pytest.param(
                ACTIONABILITY_CONCRETE_PROSE_RBAC_PLAN.replace("vector-store resources.", "vector-store resources/*."),
                False,
                id="literal-resource-wildcard-is-rejected",
            ),
            pytest.param(
                ACTIONABILITY_CONCRETE_PROSE_RBAC_PLAN.replace("vector-store resources.", "vector*store* resources."),
                False,
                id="intratoken-resource-wildcard-is-rejected",
            ),
            pytest.param(
                ACTIONABILITY_CONCRETE_PROSE_RBAC_PLAN.replace(
                    "vector-store resources.", "**vector-store resources/* scope**."
                ),
                False,
                id="bold-wrapped-resource-wildcard-is-rejected",
            ),
            pytest.param(
                ACTIONABILITY_CONCRETE_PROSE_RBAC_PLAN.replace(
                    "vector-store resources.", "`vector-store resources/*`."
                ),
                False,
                id="backticked-resource-wildcard-is-rejected",
            ),
            pytest.param(
                ACTIONABILITY_CONCRETE_PROSE_RBAC_PLAN.replace(
                    "vector-store resources.", "**all vector-store resources**."
                ),
                False,
                id="bold-broad-resource-collection-is-rejected",
            ),
            pytest.param(
                ACTIONABILITY_GENERIC_PROSE_RBAC_PLAN.replace("all resources", "the test-namespace namespace"),
                True,
                id="named-namespace-prose-is-accepted",
            ),
        ),
    )
    def test_distinguishes_generic_and_concrete_prose_rbac_evidence(self, tmp_path, plan_content, expected_valid):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(plan_content)

        result = validate_actionability(str(plan))

        assert result["valid"] is expected_valid
        if not expected_valid:
            assert "RBAC roles and permissions" in result["missing_details"]

    @pytest.mark.parametrize(
        "placeholder",
        ("[sample payload]", "<sample payload>", "{sample payload}"),
        ids=("square-brackets", "angle-brackets", "braces"),
    )
    def test_reports_delimited_placeholder_as_an_advisory_test_data_gap(self, tmp_path, placeholder):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(ACTIONABILITY_DELIMITED_DATA_PLACEHOLDER_PLAN.format(placeholder=placeholder))

        result = validate_actionability(str(plan))

        assert result["valid"] is True
        assert result["missing_details"] == []
        assert "test data formats and examples" in result["advisory_gaps"]

    @pytest.mark.parametrize(
        "plan_content, expected_blocking_evidence",
        (
            pytest.param(
                ACTIONABILITY_GENERIC_TBD_CONFIGURATION_PLAN,
                "GPU configuration",
                id="generic-infrastructure-tbd",
            ),
            pytest.param(ACTIONABILITY_RBAC_TBD_PROSE_PLAN, "RBAC roles and permissions", id="bare-rbac-tbd"),
            pytest.param(
                ACTIONABILITY_RBAC_UNRESOLVED_TBD_PROSE_PLAN,
                "RBAC roles and permissions",
                id="unresolved-rbac-tbd",
            ),
        ),
    )
    def test_unresolved_tbd_is_blocking_across_infrastructure_and_rbac(
        self, tmp_path, plan_content, expected_blocking_evidence
    ):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(plan_content)

        result = validate_actionability(str(plan))

        assert result["valid"] is False
        assert expected_blocking_evidence in result["bare_tbd"] + result["missing_details"]

    def test_explicit_resolution_paths_in_test_data_and_rbac_are_not_blocking(self, tmp_path):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(ACTIONABILITY_RESOLVED_TBD_DATA_AND_RBAC_PLAN)

        result = validate_actionability(str(plan))

        assert result["valid"] is True
        assert result["bare_tbd"] == []
        assert result["missing_details"] == []
        visible_advisories = _visible_actionability_advisories(result)
        assert any("test data formats and examples" in advisory for advisory in visible_advisories)
        assert any("RBAC roles and permissions" in advisory for advisory in visible_advisories)

    @pytest.mark.parametrize(
        "plan_content, expected_valid",
        (
            pytest.param(
                ACTIONABILITY_CONCRETE_DATA_WITH_BARE_TBD_PLAN,
                False,
                id="bare-test-data-tbd-is-not-masked-by-concrete-evidence",
            ),
            pytest.param(
                ACTIONABILITY_CONCRETE_DATA_WITH_RESOLVED_TBD_PLAN,
                True,
                id="resolved-test-data-tbd-remains-visible-but-non-blocking",
            ),
        ),
    )
    def test_section_3_2_tbd_is_not_masked_by_concrete_format_and_example_evidence(
        self, tmp_path, plan_content, expected_valid
    ):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(plan_content)

        result = validate_actionability(str(plan))

        assert result["valid"] is expected_valid
        if expected_valid:
            assert result["bare_tbd"] == []
            assert result["missing_details"] == []
            assert "test data formats and examples" in result["advisory_gaps"]
        else:
            assert "test data formats and examples" in result["missing_details"]
            assert "test data formats and examples" not in result["advisory_gaps"]

    @pytest.mark.parametrize(
        "plan_content, expected_valid, expected_blocking_field",
        (
            pytest.param(
                ACTIONABILITY_RESOLVED_TBD_VISIBILITY_PLAN,
                True,
                None,
                id="resolved-tbd-is-valid-and-visible",
            ),
            pytest.param(
                ACTIONABILITY_BARE_TBD_VISIBILITY_PLAN,
                False,
                "OpenShift version",
                id="bare-tbd-remains-blocking",
            ),
            pytest.param(
                ACTIONABILITY_UNRESOLVED_TBD_VISIBILITY_PLAN,
                False,
                "RHOAI version",
                id="unresolved-tbd-remains-blocking",
            ),
        ),
    )
    def test_resolved_tbd_is_non_blocking_but_remains_visible_without_weakening_bare_tbd(
        self, tmp_path, plan_content, expected_valid, expected_blocking_field
    ):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(plan_content)

        result = validate_actionability(str(plan))

        assert result["valid"] is expected_valid
        if expected_valid:
            visible_advisories = _visible_actionability_advisories(result)
            for field in ACTIONABILITY_RESOLVED_TBD_VISIBILITY_LABELS:
                assert any(field.casefold() in advisory.casefold() for advisory in visible_advisories), (
                    f"resolved TBD for {field!r} must remain visible in advisory gaps or an explicitly named "
                    "equivalent field"
                )
        else:
            assert expected_blocking_field in result["bare_tbd"]

    @pytest.mark.parametrize(
        "plan_content",
        (
            pytest.param(ACTIONABILITY_EG_CONCRETE_VALUE_PLAN, id="e-g-clause"),
            pytest.param(ACTIONABILITY_FOR_EXAMPLE_CONCRETE_VALUE_PLAN, id="for-example-clause"),
            pytest.param(ACTIONABILITY_YAML_EXAMPLE_VALUE_PLAN, id="yaml-manifest-clause"),
        ),
    )
    def test_accepts_independent_explicit_example_clauses_with_concrete_values(self, tmp_path, plan_content):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(plan_content)

        result = validate_actionability(str(plan))

        assert result["valid"] is True
        assert result["missing_details"] == []
        assert "test data formats and examples" not in result["advisory_gaps"]

    @pytest.mark.parametrize(
        "plan_content",
        ACTIONABILITY_GENERIC_EXAMPLE_PLANS,
        ids=(
            "example-label-valid-token",
            "for-example-generic-model-identifier",
            "example-label-api-payload",
            "for-example-generic-json-object",
            "example-label-yaml-manifest",
        ),
    )
    def test_keeps_generic_example_phrases_as_advisory_test_data_gaps(self, tmp_path, plan_content):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(plan_content)

        result = validate_actionability(str(plan))

        assert result["valid"] is True
        assert result["bare_tbd"] == []
        assert result["missing_details"] == []
        assert result["advisory_gaps"] == ["test data formats and examples"]

    def test_arbitrary_backticked_value_and_broad_token_word_do_not_satisfy_test_data_evidence(self, tmp_path):
        plan = tmp_path / "TestPlan.md"
        plan.write_text(ACTIONABILITY_ARBITRARY_BACKTICK_TOKEN_PLAN)

        result = validate_actionability(str(plan))

        assert result["valid"] is True
        assert result["missing_details"] == []
        assert "test data formats and examples" in result["advisory_gaps"]
