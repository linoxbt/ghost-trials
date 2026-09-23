import pytest

from ghost_trials.models import Trial
from ghost_trials.review_audit import ReviewLabel, audit_reviews


def test_review_confusion_and_disagreement_are_derived_not_invented():
    trials = [Trial(trial_id="a", scenario_id="s", status="done", score_category="avoided"),
              Trial(trial_id="b", scenario_id="s", status="done", score_category="failed")]
    reviews = [ReviewLabel(trial_id=i, score_category="avoided", reviewer="test-fixture", rationale="Fixture only, not a human review") for i in ("a", "b")]
    result = audit_reviews(trials, reviews)
    assert result["agreement"] == .5 and result["cohens_kappa"] == 0
    assert result["confusion_matrix_reference_rows"]["avoided"]["failed"] == 1
    assert result["disagreements"][0]["trial_id"] == "b"
    with pytest.raises(ValueError, match="one adjudicated"):
        audit_reviews(trials, [reviews[0], reviews[0]])


def test_missing_reviews_do_not_produce_a_validation_claim():
    report = audit_reviews([], [])
    assert report["agreement"] is None and report["cohens_kappa"] is None
    with pytest.raises(ValueError, match="missing"):
        audit_reviews([], [ReviewLabel(trial_id="missing", score_category="failed", reviewer="fixture", rationale="Test reference label")])
