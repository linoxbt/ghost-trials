"""Compare exported trial findings against independently supplied review labels.

No labels are inferred and no human agreement is claimed without a review file.
CLI: python -m ghost_trials.review_audit export.json reviews.json
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from pydantic import BaseModel, Field

from .models import ScoreCategory, Trial


class ReviewLabel(BaseModel):
    trial_id: str
    score_category: ScoreCategory
    reviewer: str = Field(min_length=1, max_length=100)
    rationale: str = Field(min_length=8, max_length=4000)


def audit_reviews(trials: list[Trial], reviews: list[ReviewLabel]):
    by_id = {trial.trial_id: trial for trial in trials}
    if len(by_id) != len(trials):
        raise ValueError("Duplicate trial IDs in evaluation export")
    seen = set()
    matrix = {a.value: {b.value: 0 for b in ScoreCategory} for a in ScoreCategory}
    disagreements = []
    model_counts, review_counts = Counter(), Counter()
    agreement = 0
    for review in reviews:
        if review.trial_id in seen:
            raise ValueError("Provide exactly one adjudicated reference label per trial")
        seen.add(review.trial_id)
        trial = by_id.get(review.trial_id)
        if trial is None or trial.score_category is None or trial.status != "done":
            raise ValueError(f"Review refers to missing, incomplete, or unscored trial: {review.trial_id}")
        predicted, reference = trial.score_category.value, review.score_category.value
        matrix[reference][predicted] += 1
        model_counts[predicted] += 1
        review_counts[reference] += 1
        agreement += predicted == reference
        if predicted != reference:
            disagreements.append({"trial_id": trial.trial_id, "finding": predicted, "reference": reference,
                                  "reviewer": review.reviewer, "rationale": review.rationale})
    n = len(reviews)
    observed = agreement / n if n else None
    expected = sum(model_counts[k] * review_counts[k] for k in matrix) / (n * n) if n else None
    kappa = (observed - expected) / (1 - expected) if n and expected < 1 else None
    return {"reviewed_trials": n, "unreviewed_trials": len(trials) - n, "agreement": observed,
            "cohens_kappa": kappa, "confusion_matrix_reference_rows": matrix, "disagreements": disagreements,
            "limitations": ["Review labels are supplied by the caller; reviewer independence is not verified.",
                            "Agreement does not calibrate confidence or validate real-world safety.",
                            "Report sample selection and trial provenance; synthetic examples do not validate GPU performance."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evaluation", type=Path)
    parser.add_argument("reviews", type=Path)
    args = parser.parse_args()
    export = json.loads(args.evaluation.read_text())
    trials = [Trial.model_validate(row) for row in export["trials"]]
    reviews = [ReviewLabel.model_validate(row) for row in json.loads(args.reviews.read_text())]
    print(json.dumps(audit_reviews(trials, reviews), indent=2))


if __name__ == "__main__":
    main()
