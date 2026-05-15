"""Phase 8.7 — 사용자별 처리시간 baseline EMA (순수 함수, openpyxl/IO 무관)."""

from __future__ import annotations


def next_baseline(
    prior: float | None,
    sample_s_per_tx: float,
    *,
    alpha: float,
) -> float:
    """다음 baseline(거래당 초). prior=None 이면 시드(sample 그대로), 아니면 EMA.

    EMA: alpha*sample + (1-alpha)*prior. alpha 클수록 최근값 가중.
    """
    if prior is None:
        return sample_s_per_tx
    return alpha * sample_s_per_tx + (1.0 - alpha) * prior
