"""
Data models for intelligent multi-metric routing.

This module provides the core data structures for the routing system,
including chute metrics, scores, and routing decisions.
"""

import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class ChuteMetrics:
    """
    Metrics for a single chute.

    Attributes:
        chute_id: Unique identifier for the chute
        model: Model name (e.g., "kimi-k2.5-tee")
        tps: Tokens per second (throughput)
        ttft: Time to first token in seconds (latency)
        utilization: Current utilization (0.0 - 1.0)
        total_invocations: Total number of invocations (used as quality proxy)
        fetched_at: Timestamp when metrics were fetched
    """

    chute_id: str
    model: str = ""

    # Performance metrics from /invocations/stats/llm
    tps: Optional[float] = None  # tokens per second
    ttft: Optional[float] = None  # time to first token (seconds)

    # Reliability/quality proxy from /chutes/utilization
    utilization: Optional[float] = None  # 0.0 - 1.0 (lower is better)
    total_invocations: Optional[int] = None  # reliability proxy (higher is better)

    # Metadata
    fetched_at: float = field(default_factory=time.time)

    def is_complete(self) -> bool:
        """Check if core performance metrics are available."""
        return self.tps is not None and self.ttft is not None

    def has_utilization(self) -> bool:
        """Check if utilization data is available."""
        return self.utilization is not None

    def has_any_metrics(self) -> bool:
        """Check if any metrics are available."""
        return (
            self.tps is not None
            or self.ttft is not None
            or self.utilization is not None
            or self.total_invocations is not None
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "chute_id": self.chute_id,
            "model": self.model,
            "tps": self.tps,
            "ttft": self.ttft,
            "utilization": self.utilization,
            "total_invocations": self.total_invocations,
            "fetched_at": self.fetched_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChuteMetrics":
        """Create instance from dictionary."""
        return cls(
            chute_id=data.get("chute_id", ""),
            model=data.get("model", ""),
            tps=data.get("tps"),
            ttft=data.get("ttft"),
            utilization=data.get("utilization"),
            total_invocations=data.get("total_invocations"),
            fetched_at=data.get("fetched_at", time.time()),
        )


@dataclass
class ChuteScore:
    """
    Score breakdown for a chute after normalization and weighting.

    Attributes:
        chute_id: Unique identifier for the chute
        tps_normalized: Normalized TPS score (0.0 - 1.0)
        ttft_normalized: Normalized TTFT score (0.0 - 1.0, inverted so higher is better)
        quality_normalized: Normalized quality score (0.0 - 1.0)
        utilization_normalized: Normalized utilization score (0.0 - 1.0, inverted)
        total_score: Weighted sum of all normalized scores
        raw_tps: Raw TPS value for debugging
        raw_ttft: Raw TTFT value for debugging
        raw_quality: Raw quality value for debugging
        raw_utilization: Raw utilization value for debugging
    """

    chute_id: str

    # Normalized scores (0.0 - 1.0)
    tps_normalized: float = 0.0
    ttft_normalized: float = 0.0
    quality_normalized: float = 0.0  # derived from total_invocations
    utilization_normalized: float = 0.0

    # Weighted total
    total_score: float = 0.0

    # Raw values for debugging
    raw_tps: Optional[float] = None
    raw_ttft: Optional[float] = None
    raw_quality: Optional[float] = None
    raw_utilization: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "chute_id": self.chute_id,
            "tps_normalized": round(self.tps_normalized, 4),
            "ttft_normalized": round(self.ttft_normalized, 4),
            "quality_normalized": round(self.quality_normalized, 4),
            "utilization_normalized": round(self.utilization_normalized, 4),
            "total_score": round(self.total_score, 4),
            "raw_tps": self.raw_tps,
            "raw_ttft": self.raw_ttft,
            "raw_quality": self.raw_quality,
            "raw_utilization": self.raw_utilization,
        }


@dataclass
class RoutingDecision:
    """
    Result of a routing decision.

    Attributes:
        selected_chute: The selected chute ID
        scores: Dictionary of chute_id to ChuteScore
        decision_reason: Human-readable explanation of the decision
        fallback_mode: Whether fallback mode was used
        cache_hit: Whether the decision used cached metrics
        api_calls_made: Number of API calls made for this decision
        warning: Optional warning message
    """

    selected_chute: str
    scores: Dict[str, ChuteScore] = field(default_factory=dict)
    decision_reason: str = ""
    fallback_mode: bool = False
    cache_hit: bool = False
    api_calls_made: int = 0
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "selected_chute": self.selected_chute,
            "scores": {k: v.to_dict() for k, v in self.scores.items()},
            "decision_reason": self.decision_reason,
            "fallback_mode": self.fallback_mode,
            "cache_hit": self.cache_hit,
            "api_calls_made": self.api_calls_made,
            "warning": self.warning,
        }
