from app.assembly.service import summarize_assembly_coverage


def test_failed_pair_prevents_complete_coverage():
    result = {"relations": [
        {"status": "evaluated", "intersection_status": "empty", "contact_kind": "positive_gap"},
        {"status": "failed", "diagnostic": "distance unavailable"},
        {"status": "evaluated", "intersection_status": "boolean_failed", "contact_kind": "unknown"},
    ], "excluded_pair_count": 4, "evaluated_pair_count": 3}
    coverage = summarize_assembly_coverage(result)
    assert coverage["status"] == "partial"
    assert coverage["successful_pair_count"] == 1
    assert coverage["failed_pair_count"] == 2
    assert coverage["candidate_pair_count"] == 3
    assert coverage["excluded_pair_count"] == 4


def test_unknown_contact_is_not_claimed_successful():
    result = {"relations": [{"status": "evaluated", "intersection_status": "indeterminate_zero_distance",
                             "contact_kind": "indeterminate_zero_distance"}],
              "excluded_pair_count": 0, "evaluated_pair_count": 1}
    coverage = summarize_assembly_coverage(result)
    assert coverage["status"] == "partial"
    assert coverage["unknown_pair_count"] == 1
