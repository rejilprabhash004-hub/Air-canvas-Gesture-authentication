"""Compare Random Forest and SVM with session-disjoint evaluation.

Callers must provide real labeled feature rows and a session ID per row. The
split holds out complete sessions to reduce within-session leakage. Synthetic
tests exercise pipeline behavior only; their scores are not model evidence.
"""
from __future__ import annotations

from collections.abc import Sequence
import math
from typing import Any, Hashable

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


class ModelEvaluationError(ValueError):
    """Raised when a labeled, session-aware evaluation dataset is invalid."""


def compare_models(
    features: Sequence[Sequence[float]],
    labels: Sequence[str],
    session_ids: Sequence[Hashable],
    *,
    test_size: float = 0.25,
    random_state: int = 42,
) -> dict[str, Any]:
    """Fit Random Forest and SVM on a group-held-out split and report metrics.

    Rows with a shared session ID are kept together in train or test, never
    split across both. The deterministic group split is selected only if every
    class occurs in both partitions. Raises if this cannot be achieved. Metrics
    are macro-averaged where applicable. ``estimators`` are fitted models; the
    function does not persist them or claim their scores generalize beyond the
    supplied data.
    """
    try:
        matrix = np.asarray(features, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ModelEvaluationError("features must be a rectangular numeric matrix.") from exc
    if matrix.ndim != 2 or matrix.shape[0] < 4 or matrix.shape[1] < 1:
        raise ModelEvaluationError("features must have at least 4 rows and 1 feature column.")
    if not np.isfinite(matrix).all():
        raise ModelEvaluationError("features must contain only finite values.")
    if len(labels) != matrix.shape[0] or len(session_ids) != matrix.shape[0]:
        raise ModelEvaluationError("features, labels, and session_ids must have equal lengths.")
    if any(not isinstance(label, str) or not label.strip() for label in labels):
        raise ModelEvaluationError("labels must be non-empty strings.")
    try:
        if any(session_id is None or not isinstance(session_id, Hashable) for session_id in session_ids):
            raise ModelEvaluationError("session_ids must be non-null hashable values.")
    except TypeError as exc:
        raise ModelEvaluationError("session_ids must be non-null hashable values.") from exc
    if len(set(labels)) < 2:
        raise ModelEvaluationError("at least two gesture classes are required.")
    if not isinstance(test_size, (int, float)) or isinstance(test_size, bool) or not 0 < test_size < 1:
        raise ModelEvaluationError("test_size must be a number strictly between 0 and 1.")
    if isinstance(random_state, bool) or not isinstance(random_state, int):
        raise ModelEvaluationError("random_state must be an integer.")

    target = np.asarray(labels, dtype=str)
    groups = np.asarray([str(value) for value in session_ids], dtype=str)
    class_names = sorted(set(labels))
    selected_split = None
    splitter = GroupShuffleSplit(n_splits=50, test_size=float(test_size), random_state=random_state)
    for train_indices, test_indices in splitter.split(matrix, target, groups):
        if set(target[train_indices]) == set(class_names) and set(target[test_indices]) == set(class_names):
            selected_split = (train_indices, test_indices)
            break
    if selected_split is None:
        raise ModelEvaluationError(
            "Could not create a session-disjoint split containing every class in both sets; "
            "provide more sessions per gesture or adjust test_size."
        )
    train_indices, test_indices = selected_split

    estimators = {
        "random_forest": RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=random_state,
        ),
        "svm": make_pipeline(
            StandardScaler(),
            SVC(kernel="rbf", class_weight="balanced"),
        ),
    }
    results: dict[str, Any] = {}
    for name, estimator in estimators.items():
        estimator.fit(matrix[train_indices], target[train_indices])
        predictions = estimator.predict(matrix[test_indices])
        results[name] = {
            "estimator": estimator,
            "metrics": {
                "accuracy": float(accuracy_score(target[test_indices], predictions)),
                "precision_macro": float(precision_score(
                    target[test_indices], predictions, labels=class_names,
                    average="macro", zero_division=0,
                )),
                "recall_macro": float(recall_score(
                    target[test_indices], predictions, labels=class_names,
                    average="macro", zero_division=0,
                )),
                "f1_macro": float(f1_score(
                    target[test_indices], predictions, labels=class_names,
                    average="macro", zero_division=0,
                )),
                "confusion_matrix": confusion_matrix(
                    target[test_indices], predictions, labels=class_names,
                ).tolist(),
                "class_labels": class_names,
                "train_sample_count": int(len(train_indices)),
                "test_sample_count": int(len(test_indices)),
                "train_session_ids": sorted(set(groups[train_indices].tolist())),
                "test_session_ids": sorted(set(groups[test_indices].tolist())),
            },
        }
    return results
