"""Baseline classifiers (traditional ML) for comparison against the World Model."""

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler


def build_classifier(name: str):
    """Return a fresh classifier by name."""
    name = name.lower()
    if name == "logistic_regression" or name == "logreg":
        return LogisticRegression(max_iter=2000)
    if name == "random_forest":
        return RandomForestClassifier(n_estimators=200, random_state=42)
    if name == "gradient_boosting":
        return GradientBoostingClassifier(random_state=42)
    raise ValueError(f"Unknown baseline: {name}")


def train_and_evaluate_baseline(name: str, X_train, y_train, X_test, y_test):
    """
    Train a baseline on flattened per-window features and evaluate binary
    attack classification. Returns a dict of metrics (all computed, never
    fabricated).
    """
    clf = build_classifier(name)
    y_train = np.asarray(y_train)
    y_test = np.asarray(y_test)

    # scale features (LR benefits)
    if "logistic" in name.lower():
        sc = StandardScaler()
        X_train = sc.fit_transform(X_train)
        X_test = sc.transform(X_test)

    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)

    # AUC requires both classes present; guard against single-class test set
    auc = float("nan")
    if len(np.unique(y_test)) > 1 and hasattr(clf, "predict_proba"):
        try:
            auc = roc_auc_score(y_test, clf.predict_proba(X_test)[:, 1])
        except ValueError:
            auc = float("nan")

    return {
        "model": name,
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(auc),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
    }
