from __future__ import annotations

import math

from .models import KnowledgeGap, ReadinessAxes


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def calculate_readiness(gaps: list[KnowledgeGap]) -> ReadinessAxes:
    if not gaps:
        return ReadinessAxes(
            concept_mastery=0.6,
            deadline_pressure=0.2,
            retention_risk=0.2,
            problem_transfer=0.55,
            consistency=0.7,
        )

    open_gaps = [gap for gap in gaps if gap.status != "closed"]
    if not open_gaps:
        return ReadinessAxes(
            concept_mastery=0.9,
            deadline_pressure=0.2,
            retention_risk=0.2,
            problem_transfer=0.82,
            consistency=0.85,
        )

    severities = [gap.severity for gap in open_gaps]
    avg_severity = sum(severities) / len(severities)
    variance = sum((item - avg_severity) ** 2 for item in severities) / len(severities)
    stddev = math.sqrt(variance)

    deadline_pressure = clamp(max(gap.deadline_score for gap in open_gaps))
    concept_mastery = clamp(1.0 - avg_severity)
    retention_risk = clamp(0.3 + len(open_gaps) * 0.08)
    problem_transfer = clamp(concept_mastery - 0.12)
    consistency = clamp(1.0 - stddev)

    return ReadinessAxes(
        concept_mastery=concept_mastery,
        deadline_pressure=deadline_pressure,
        retention_risk=retention_risk,
        problem_transfer=problem_transfer,
        consistency=consistency,
    )
