"""Classification-specific metrics with explicit error and abstention denominators."""

from statistics import median, quantiles

from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from app.contracts import Label
from evals.contracts import Thresholds

LABELS = [label.value for label in Label]


def summarize(
    expected: list[str],
    predicted: list[str | None],
    *,
    elapsed_ms: list[float | None],
    costs: list[float | None],
) -> dict[str, object]:
    """Include every failed case and report missing cost without inventing zero."""
    count = len(expected)
    if not count or not (count == len(predicted) == len(elapsed_ms) == len(costs)):
        raise ValueError("Metrics require nonempty, equal-length case/result vectors")
    if any(value not in LABELS for value in expected):
        raise ValueError("Gold labels must match the exact label contract")
    observed = [value if value in LABELS else "__failure__" for value in predicted]
    precision, recall, f1, support = precision_recall_fscore_support(
        expected,
        observed,
        labels=LABELS,
        zero_division=0,
    )
    answered = [i for i, value in enumerate(observed) if value in LABELS[:2]]
    known_costs = [cost for cost in costs if cost is not None]
    known_latency = [elapsed for elapsed in elapsed_ms if elapsed is not None]
    return {
        "count": count,
        "accuracy": sum(a == b for a, b in zip(expected, observed, strict=True)) / count,
        "macro_f1": float(f1.mean()),
        "per_class": {
            label: {
                "precision": float(precision[i]),
                "recall": float(recall[i]),
                "f1": float(f1[i]),
                "support": int(support[i]),
            }
            for i, label in enumerate(LABELS)
        },
        "confusion_labels": LABELS + ["__failure__"],
        "confusion_matrix": confusion_matrix(
            expected,
            observed,
            labels=LABELS + ["__failure__"],
        ).tolist(),
        "unknown_rate": observed.count(Label.UNKNOWN.value) / count,
        "coverage": len(answered) / count,
        "answered_accuracy": (
            sum(expected[i] == observed[i] for i in answered) / len(answered) if answered else None
        ),
        "failure_rate": observed.count("__failure__") / count,
        "p50_ms": median(known_latency) if known_latency else None,
        "p95_ms": (
            quantiles(known_latency, n=100, method="inclusive")[94]
            if len(known_latency) > 1
            else (known_latency[0] if known_latency else None)
        ),
        "missing_latency_count": count - len(known_latency),
        "available_cost_usd": sum(known_costs) if known_costs else None,
        "missing_cost_count": count - len(known_costs),
    }


def passes(metrics: dict, thresholds: Thresholds) -> bool:
    """Require quality, coverage, class support and operational bars together."""
    return bool(
        metrics["coverage"] > 0
        and metrics["macro_f1"] >= thresholds.macro_f1
        and metrics["coverage"] >= thresholds.coverage
        and metrics["failure_rate"] <= thresholds.max_failure_rate
        and metrics["missing_latency_count"] == 0
        and metrics["p95_ms"] is not None
        and metrics["p95_ms"] <= thresholds.p95_ms
        and all(
            value["support"] > 0
            and value["precision"] >= thresholds.per_class_precision
            and value["recall"] >= thresholds.per_class_recall
            for value in metrics["per_class"].values()
        )
    )
