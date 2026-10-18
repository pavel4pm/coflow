"""The acceptance tests of increment I1 (spec §9.1) and where each one is checked.

Every I1 test ID maps to the test functions that check its scenario; this fitness test fails when an
ID has no test or a listed test is renamed or removed, so the inventory stays true. It reads the
test files with ``ast`` and imports nothing.
"""

from __future__ import annotations

import ast
from functools import cache
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent

I1: dict[str, tuple[str, ...]] = {
    "AT-K1": ("kernel/test_ids.py::test_at_k1_concurrent_issues_skip_foreign_and_burned",),
    "AT-K2": (
        "kernel/test_ids.py::test_at_k2_parse_render_round_trip",
        "kernel/test_ids.py::test_at_k2_round_trip_for_every_number",
        "kernel/test_ids.py::test_at_k2_unregistered_prefix_is_refused",
    ),
    "AT-K3": (
        "kernel/test_ids.py::test_at_k3_tolerant_forms",
        "kernel/test_ids.py::test_at_k3_output_is_always_canonical",
    ),
    "AT-K4": (
        "kernel/test_triggers.py::test_at_k4_append_only_set_once_and_erasure",
        "kernel/test_triggers.py::test_at_k4_through_the_unit_of_work",
        "kernel/test_triggers.py::test_at_k4_on_the_real_dec_checks",
    ),
    "AT-K5": (
        "kernel/test_unit.py::test_at_k5_fault_after_every_statement_leaves_all_or_nothing",
        "kernel/test_unit.py::test_at_k5_tx_and_recorded_at_come_from_the_store",
        "kernel/test_unit.py::test_at_k5_a_caller_supplied_stamp_is_refused",
    ),
    "AT-K6": (
        "kernel/test_events.py::test_at_k6_every_catalogue_event_holds_only_ids_entity_and_names",
        "kernel/test_events.py::test_at_k6_a_canary_in_a_record_never_reaches_the_event_tables",
        "integration/test_i1_flow.py::test_a_canary_in_imported_decisions_stays_in_the_decision_tables",
    ),
    "AT-K7": (
        "kernel/test_lock.py::test_at_k7_the_second_core_refuses",
        "kernel/test_lock.py::test_at_k7_an_ephemeral_core_runs_once_the_core_stops",
        "kernel/test_lock.py::test_at_k7_a_core_in_another_process_holds_the_lock",
        "interfaces/test_supervisor.py::test_the_cli_and_the_shim_go_through_the_running_core",
        "interfaces/test_supervisor.py::test_a_stale_endpoint_file_falls_back_to_an_ephemeral_core",
        "interfaces/test_core_dev.py::test_a_real_core",
        "interfaces/test_stdio_shim.py::test_the_shim_imports_nothing_that_can_find_an_instance",
        "integration/test_i1_flow.py::test_the_core_serves_the_cli_and_an_mcp_client_through_the_shim",
        "integration/test_core_process.py::test_a_stopped_core_process_cleans_up",
    ),
    "AT-K8": (
        "modules/dec/test_domain_cfj.py::test_cfj_is_byte_identical_to_the_pilot",
        "modules/dec/test_domain_cfj.py::test_pilot_seals_verify_with_unit_hash",
        "modules/dec/test_domain_cfj.py::test_a_float_in_a_basis_is_refused",
    ),
    "AT-K9": (
        "kernel/test_init_doctor.py::test_at_k9_init_refuses_a_validation_root_inside_a_working_tree",
        "kernel/test_init_doctor.py::test_at_k9_doctor_refuses_a_validation_root_inside_a_working_tree",
        "kernel/test_init_doctor.py::test_at_k9_snapshot_roles",
        "kernel/test_init_doctor.py::test_at_k9_end_to_end_import_into_dev",
        "modules/dec/test_import_snapshot.py::test_at_k9_a_dev_instance_refuses_a_real_snapshot",
    ),
    "AT-D1": (
        "modules/dec/test_domain_dates_due.py::test_dates_in",
        "modules/dec/test_domain_dates_due.py::test_a_date_equal_to_the_creation_day_is_not_due",
        "modules/dec/test_domain_dates_due.py::test_after_a_check_on_day_seven_the_next_text_date_counts",
        "modules/dec/test_domain_dates_due.py::test_by_date_beats_text_and_explicit_beats_both",
    ),
    "AT-D2": ("modules/dec/test_domain_dates_due.py::test_next_check_after",),
    "AT-D3": (
        "modules/dec/test_domain_health.py::test_named_vector",
        "modules/dec/test_health_oracle.py::test_the_oracle_reproduces_the_named_vectors",
        "modules/dec/test_health_oracle.py::test_the_module_agrees_on_the_named_vectors",
        "modules/dec/test_health_oracle.py::test_the_module_and_the_oracle_agree_on_the_whole_space",
    ),
    "AT-D4": (
        "modules/dec/test_domain_waiting.py::test_a_month_of_due_checks_across_six_decisions",
        "modules/dec/test_domain_waiting.py::test_order_critical_violation_first_then_oldest_due_then_number",
    ),
    "AT-S1": (
        "modules/dec/test_import_snapshot.py::test_at_s1_imports_the_eight_mirrors",
        "modules/dec/test_import_snapshot.py::test_at_s1_numbers_seals_and_events",
        "modules/dec/test_import_snapshot.py::test_at_s1_field_mapping",
    ),
    "AT-S2": ("modules/dec/test_import_snapshot.py::test_at_s2_the_same_file_twice_is_a_noop",),
    "AT-S3": ("modules/dec/test_import_snapshot.py::test_at_s3_reimport_with_changes",),
    "AT-S4": ("modules/dec/test_store.py::test_at_s4_every_write_on_a_v1_mirror_is_refused",),
    "AT-S5": (
        "modules/dec/test_shadow.py::test_at_s5_the_family_classifies_every_rule_and_nothing_unexpected",
        "modules/dec/test_shadow.py::test_at_s5_s1_alone",
        "modules/dec/test_shadow.py::test_an_injected_due_date_mismatch_is_unexpected",
        "modules/dec/test_shadow.py::test_an_injected_order_swap_is_unexpected",
        "modules/dec/test_shadow_v1_dates.py::test_a_dateless_v1_violation_matches_v2s_dated_one",
    ),
    "AT-S6": (
        "modules/dec/test_import_snapshot.py::test_at_s6_a_fault_in_one_unit_applies_nothing",
        "modules/dec/test_import_snapshot.py::test_at_s6_chunks_stay_partial_until_the_rerun_completes_them",
    ),
    "AT-S7": (
        "modules/dec/test_import_snapshot.py::test_at_s7_goal_changed_once_until_a_review_answers_it",
    ),
    "AT-S8": (
        "modules/dec/test_import_snapshot.py::test_at_s8_knowledge_time_is_the_source_record_time",
    ),
    "AT-M1": (
        "interfaces/test_at_m1.py::test_waiting_is_identical_over_mcp_the_cli_and_the_query",
        "interfaces/test_at_m1.py::test_context_is_identical_over_mcp_and_the_cli",
        "interfaces/test_at_m1.py::test_every_answer_states_the_role_and_the_mirror_authority",
        "interfaces/test_at_m1.py::test_tokens_hosts_and_the_read_only_list",
        "interfaces/test_at_m1.py::test_every_pull_is_a_usage_signal_by_channel",
        "interfaces/test_integration_dev.py::test_at_m1_on_a_dev_instance",
        "integration/test_i1_flow.py::test_the_core_serves_the_cli_and_an_mcp_client_through_the_shim",
    ),
}
"""Spec §9.1, increment I1: every row of the table, in its order."""

SPEC_I1 = (
    *(f"AT-K{n}" for n in range(1, 10)),
    *(f"AT-D{n}" for n in range(1, 5)),
    *(f"AT-S{n}" for n in range(1, 9)),
    "AT-M1",
)


@cache
def _functions(relative: str) -> frozenset[str]:
    tree = ast.parse((TESTS / relative).read_text(encoding="utf-8"))
    return frozenset(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test_")
    )


def test_every_i1_acceptance_test_is_listed() -> None:
    assert tuple(I1) == SPEC_I1


@pytest.mark.parametrize("at_id", SPEC_I1)
def test_each_i1_acceptance_test_has_its_tests(at_id: str) -> None:
    listed = I1[at_id]
    assert listed, f"{at_id} has no test"
    for node in listed:
        relative, _, name = node.partition("::")
        assert name in _functions(relative), f"{at_id}: {node} does not exist"
