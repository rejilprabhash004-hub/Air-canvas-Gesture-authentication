"""Synthetic tests validate model pipeline behavior, not model performance."""
import numpy as np
import pytest

from gesture.model_evaluation import ModelEvaluationError, compare_models


def synthetic_session_data():
    features = []
    labels = []
    sessions = []
    for class_index, label in enumerate(("FIST", "OPEN_PALM", "VICTORY")):
        for session_index in range(8):
            session_shift = session_index * 0.001
            for repeat in range(3):
                features.append([
                    float(class_index * 3) + session_shift,
                    float(class_index == 1) + repeat * 0.001,
                    float(class_index == 2) - session_shift,
                    float(repeat) * 0.01,
                ])
                labels.append(label)
                sessions.append(f"{label}-session-{session_index}")
    return features, labels, sessions


def test_compares_classifiers_using_disjoint_sessions_and_expected_metrics():
    features, labels, sessions = synthetic_session_data()
    results = compare_models(features, labels, sessions, test_size=0.25, random_state=7)
    assert set(results) == {"random_forest", "svm"}
    for result in results.values():
        metrics = result["metrics"]
        assert 0.0 <= metrics["accuracy"] <= 1.0
        assert 0.0 <= metrics["precision_macro"] <= 1.0
        assert 0.0 <= metrics["recall_macro"] <= 1.0
        assert 0.0 <= metrics["f1_macro"] <= 1.0
        assert len(metrics["confusion_matrix"]) == 3
        assert metrics["class_labels"] == ["FIST", "OPEN_PALM", "VICTORY"]
        assert set(metrics["train_session_ids"]).isdisjoint(metrics["test_session_ids"])
        assert len(metrics["test_session_ids"]) > 0


def test_rejects_nonfinite_features_and_misaligned_rows():
    features, labels, sessions = synthetic_session_data()
    features[0][0] = float("nan")
    with pytest.raises(ModelEvaluationError, match="finite"):
        compare_models(features, labels, sessions)

    features, labels, sessions = synthetic_session_data()
    with pytest.raises(ModelEvaluationError, match="equal lengths"):
        compare_models(features, labels[:-1], sessions)


def test_rejects_too_few_sessions_for_class_complete_split():
    features = [[0.0], [0.1], [1.0], [1.1]]
    labels = ["A", "A", "B", "B"]
    sessions = ["a1", "a2", "b1", "b2"]
    with pytest.raises(ModelEvaluationError, match="session-disjoint split"):
        compare_models(features, labels, sessions, test_size=0.5)


def test_rejects_invalid_matrix_shape_and_test_size():
    with pytest.raises(ModelEvaluationError, match="at least 4 rows"):
        compare_models([[0.0], [1.0]], ["A", "B"], ["s1", "s2"])
    features, labels, sessions = synthetic_session_data()
    with pytest.raises(ModelEvaluationError, match="test_size"):
        compare_models(features, labels, sessions, test_size=1.0)


def test_metrics_are_finite_and_confusion_counts_match_test_rows():
    features, labels, sessions = synthetic_session_data()
    results = compare_models(features, labels, sessions, random_state=19)
    for result in results.values():
        metrics = result["metrics"]
        assert all(np.isfinite(metrics[key]) for key in (
            "accuracy", "precision_macro", "recall_macro", "f1_macro"
        ))
        assert sum(map(sum, metrics["confusion_matrix"])) == metrics["test_sample_count"]
