# Technical Design: Intelligent Multi-Metric Routing

## Overview

This design documents the technical implementation for an intelligent multi-metric routing system that optimizes request distribution across AI model deployments (chutes) using real-time performance metrics. The system uses a strategy pattern to enable pluggable routing algorithms and coexists with the existing `ChutesUtilizationRouting` implementation.

**Key User Decisions Incorporated:**
- Skip `/miner/scores` - use `total_invocations` from `/chutes/utilization` as reliability proxy
- Update frequency: 5 minutes for TPS/TTFT refresh (performance metrics)
- Default strategy: `balanced` (25% weights each for TPS, TTFT, quality, utilization)
- Fallback: `utilization-only` (current behavior)
- Backward compatibility: Coexist as alternative routing strategy

---

## Example Mapping

### Input-Output Examples → Tests

| Example ID | Description | Test Type | Implementation Notes |
|------------|-------------|-----------|---------------------|
| EX-001 | Speed-optimized (TPS priority) | Unit | Verify Qwen selected (highest TPS: 29.45) |
| EX-002 | Latency-optimized (TTFT priority) | Unit | Verify Kimi selected (lowest TTFT: 6.45s) |
| EX-003 | Balanced strategy (25% each) | Unit | Verify Kimi selected (best overall metrics) |
| EX-004 | Quality-optimized (total_invocations) | Unit | Verify Kimi selected (highest quality: 0.92) |

### Edge Cases → Tests

| Edge Case ID | Description | Test Type | Implementation Notes |
|--------------|-------------|-----------|---------------------|
| EC-001 | Missing TPS/TTFT metrics | Unit/Integration | Verify fallback to utilization-only |
| EC-002 | All chutes at high utilization (>80%) | Unit | Verify warning included, route to least-loaded |
| EC-003 | Single chute available | Unit | Verify direct return without scoring |
| EC-004 | Extreme TTFT variance (120s vs 6.45s) | Unit | Verify normalized score > 0 |
| EC-005 | Cache hit within TTL | Unit | Verify no API calls made |

### State Transitions → Tests

| State ID | Transition | Test Type | Implementation Notes |
|----------|-------------|-----------|---------------------|
| ST-001 | Cache lifecycle | Integration | Verify cache populate, TTLs set correctly |
| ST-002 | Strategy change mid-request | Integration | Verify same cache, different decision |
| ST-003 | Fallback mode activation | Integration | Verify graceful degradation |

---

## Scenario Mapping

### BDD Scenarios → Automated Tests

| Scenario ID | Scenario Title | Test Framework Mapping | Priority |
|-------------|----------------|------------------------|----------|
| BDD-001 | Speed-optimized (TPS priority) | pytest-bdd | Must Pass |
| BDD-002 | Latency-optimized (TTFT priority) | pytest-bdd | Must Pass |
| BDD-003 | Balanced strategy (equal weights) | pytest-bdd | Must Pass |
| BDD-004 | Quality-optimized (total_invocations) | pytest-bdd | Must Pass |
| BDD-005 | Missing metrics fallback | pytest-bdd | Must Pass |
| BDD-006 | High utilization handling | pytest-bdd | Must Pass |
| BDD-007 | Single chute available | pytest-bdd | Must Pass |
| BDD-008 | Extreme TTFT variance | pytest-bdd | Should Pass |
| BDD-009 | Cache hit | pytest-bdd | Should Pass |
| BDD-010 | Cache miss (fresh fetch) | pytest-bdd | Should Pass |
| BDD-011 | Strategy change | pytest-bdd | Should Pass |
| BDD-012 | Fallback mode | pytest-bdd | Should Pass |
| BDD-013 | Environment configuration | pytest-bdd | Could Pass |
| BDD-014 | Custom weights override | pytest-bdd | Could Pass |

---

## Architecture

### Two-Tier Routing: Model → Chute (No Node-Level Selection)

> **Important Platform Constraint**: The chutes.ai platform does **NOT** support targeting specific nodes/instances within a chute. The platform handles node selection automatically through its internal load balancing. This design implements **chute-level routing only** (2-tier), not node-level routing (3-tier).

**Routing Hierarchy**:
```
Tier 1: Model Selection (which model: Kimi, GLM, or Qwen)
    │
    ▼
Tier 2: Chute Selection (which chute for that model)
    │
    ▼
    [Chutes.ai handles internal node/instance selection automatically]
```

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           LiteLLM Proxy                                 │
│                           (Port 4000)                                   │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ get_router_config()
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    ChutesRoutingStrategy (ABC)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────┐    ┌──────────────────────────────────┐  │
│  │ ChutesUtilization       │    │ IntelligentMultiMetricRouting   │  │
│  │ Routing (EXISTING)      │    │ (NEW - Coexists)                 │  │
│  │                         │    │                                    │  │
│  │ - utilization_only      │    │ Strategies:                       │  │
│  │ - fallback_mode         │    │ - speed                           │  │
│  └─────────────────────────┘    │ - latency                         │  │
│                                  │ - balanced (DEFAULT)              │  │
│                                  │ - quality                          │  │
│                                  │ - utilization-only (fallback)      │  │
│                                  └──────────────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      MetricsAggregator                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  - fetch_all_metrics(chutes) -> ChuteMetrics[]                         │
│  - get_cached_metrics(chute_id) -> Optional[Metrics]                   │
│  - Cache per metric type with separate TTLs                            │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │ /chutes/        │  │ /invocations/   │  │ /chutes/        │
    │ utilization    │  │ stats/llm      │  │ utilization     │
    │                │  │                 │  │ (total_invocations) │
    │ Returns:       │  │ Returns:        │  │                 │
    │ - utilization  │  │ - tps           │  │ Returns:        │
    │ - total_invocations │ │ - ttft     │  │ - utilization   │
    └─────────────────┘  └─────────────────┘  │ - total_invocations │
                                                └─────────────────┘

    NOTE: Chute-level metrics only - Node selection handled by platform
    - /miner/scores SKIPPED (quality derived from total_invocations)
```

### Data Flow

```
Request arrives at LiteLLM
         │
         ▼
┌─────────────────────────┐
│ Select routing strategy│
│ (from config: "balanced"│
│  by default)           │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Check metrics cache    │◄──┐
│ (per-metric TTL)       │   │
└───────────┬─────────────┘   │
            │ Cache HIT        │ Cache MISS
            ▼                 ▼
┌─────────────────────────┐
│ Use cached metrics     │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Fetch from APIs:       │
│ 1. /chutes/utilization │
│    (utilization,       │
│     total_invocations) │
│ 2. /invocations/stats/ │
│    llm (tps, ttft)     │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ IntelligentRouting     │
│ Strategy.score()       │
│                        │
│ - Normalize metrics    │
│ - Apply weights        │
│ - Calculate total      │
│ - Select highest       │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Return selected chute   │
│ + scores + reason      │
└─────────────────────────┘
```

### Class/Interface Design

```python
# ============================================================
# Core Interfaces & Data Classes
# ============================================================

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time

class RoutingStrategy(Enum):
    SPEED = "speed"           # TPS priority
    LATENCY = "latency"       # TTFT priority
    BALANCED = "balanced"     # 25% each (DEFAULT)
    QUALITY = "quality"       # total_invocations priority
    UTILIZATION_ONLY = "utilization_only"  # Fallback

@dataclass
class ChuteMetrics:
    """Metrics for a single chute."""
    chute_id: str
    model: str
    
    # Performance metrics from /invocations/stats/llm
    tps: Optional[float] = None          # tokens per second
    ttft: Optional[float] = None          # time to first token (seconds)
    
    # Reliability/quality proxy from /chutes/utilization
    utilization: Optional[float] = None    # 0.0 - 1.0 (lower is better)
    total_invocations: Optional[int] = None  # reliability proxy (higher is better)
    
    # Metadata
    fetched_at: float = field(default_factory=time.time)
    
    def is_complete(self) -> bool:
        """Check if core metrics are available."""
        return self.tps is not None and self.ttft is not None
    
    def has_utilization(self) -> bool:
        """Check if utilization data is available."""
        return self.utilization is not None


@dataclass
class ChuteScore:
    """Score breakdown for a chute."""
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


@dataclass
class RoutingDecision:
    """Result of a routing decision."""
    selected_chute: str
    scores: dict[str, ChuteScore] = field(default_factory=dict)
    decision_reason: str = ""
    fallback_mode: bool = False
    cache_hit: bool = False
    api_calls_made: int = 0
    warning: Optional[str] = None


@dataclass
class StrategyWeights:
    """Weight configuration for scoring."""
    tps: float = 0.25
    ttft: float = 0.25
    quality: float = 0.25      # derived from total_invocations
    utilization: float = 0.25
    
    # Predefined strategies
    SPEED = None  # Will be set in RoutingStrategy class
    LATENCY = None
    BALANCED = None
    QUALITY = None
    
    @classmethod
    def from_strategy(cls, strategy: RoutingStrategy) -> "StrategyWeights":
        """Get default weights for a strategy."""
        weights = {
            RoutingStrategy.SPEED: cls(tps=0.5, ttft=0.3, quality=0.1, utilization=0.1),
            RoutingStrategy.LATENCY: cls(tps=0.1, ttft=0.6, quality=0.15, utilization=0.15),
            RoutingStrategy.BALANCED: cls(tps=0.25, ttft=0.25, quality=0.25, utilization=0.25),
            RoutingStrategy.QUALITY: cls(tps=0.15, ttft=0.15, quality=0.5, utilization=0.2),
            RoutingStrategy.UTILIZATION_ONLY: cls(tps=0.0, ttft=0.0, quality=0.0, utilization=1.0),
        }
        return weights.get(strategy, cls())
    
    def validate(self) -> bool:
        """Validate weights sum to 1.0."""
        return abs(self.tps + self.ttft + self.quality + self.utilization - 1.0) < 0.001


# ============================================================
# Strategy Pattern - Routing Strategies
# ============================================================

class ChutesRoutingStrategy(ABC):
    """Abstract base class for routing strategies."""
    
    @abstractmethod
    def select_chute(
        self,
        chutes: list[ChuteMetrics],
        weights: Optional[StrategyWeights] = None
    ) -> RoutingDecision:
        """Select the best chute based on metrics and weights."""
        pass


class IntelligentMultiMetricRouting(ChutesRoutingStrategy):
    """
    Multi-metric routing strategy that considers:
    - TPS (tokens per second)
    - TTFT (time to first token)
    - Quality (derived from total_invocations)
    - Utilization (current load)
    
    Uses Strategy pattern for pluggable scoring algorithms.
    Coexists with existing ChutesUtilizationRouting.
    """
    
    def __init__(
        self,
        strategy: RoutingStrategy = RoutingStrategy.BALANCED,
        custom_weights: Optional[StrategyWeights] = None,
        cache: Optional[MetricsCache] = None,
        api_client: Optional[ChutesAPIClient] = None,
    ):
        self.strategy = strategy
        self.weights = custom_weights or StrategyWeights.from_strategy(strategy)
        self.cache = cache or MetricsCache()
        self.api_client = api_client or ChutesAPIClient()
        
        if not self.weights.validate():
            raise ValueError("Weights must sum to 1.0")
    
    def select_chute(
        self,
        chutes: list[ChuteMetrics],
        weights: Optional[StrategyWeights] = None
    ) -> RoutingDecision:
        """Select best chute using multi-metric scoring."""
        
        # Use provided weights or fall back to strategy weights
        effective_weights = weights or self.weights
        
        # Edge case: single chute
        if len(chutes) == 1:
            return RoutingDecision(
                selected_chute=chutes[0].chute_id,
                decision_reason="Only one chute available",
            )
        
        # Check if we have complete metrics for multi-metric scoring
        complete_metrics = [c for c in chutes if c.is_complete()]
        
        if not complete_metrics:
            # Fallback to utilization-only
            return self._fallback_to_utilization(chutes)
        
        # Calculate scores
        scores = self._calculate_scores(complete_metrics, effective_weights)
        
        # Select highest scoring chute
        selected = max(scores.items(), key=lambda x: x[1].total_score)
        
        # Check for high utilization warning
        warning = None
        if all(c.utilization and c.utilization > 0.8 for c in chutes):
            warning = "All chutes above 80% utilization"
        
        return RoutingDecision(
            selected_chute=selected[0],
            scores=scores,
            decision_reason=self._generate_reason(selected[1], chutes),
            cache_hit=self.cache.is_warm(),
            warning=warning,
        )
    
    def _calculate_scores(
        self,
        chutes: list[ChuteMetrics],
        weights: StrategyWeights
    ) -> dict[str, ChuteScore]:
        """Calculate normalized scores for all chutes."""
        
        # Find min/max for normalization
        tps_values = [c.tps for c in chutes if c.tps is not None]
        ttft_values = [c.ttft for c in chutes if c.ttft is not None]
        quality_values = [self._derive_quality(c) for c in chutes if c.total_invocations is not None]
        util_values = [c.utilization for c in chutes if c.utilization is not None]
        
        scores = {}
        for chute in chutes:
            score = ChuteScore(chute_id=chute.chute_id)
            
            # TPS: higher is better
            if tps_values:
                tps_min, tps_max = min(tps_values), max(tps_values)
                if tps_max > tps_min:
                    score.tps_normalized = (chute.tps - tps_min) / (tps_max - tps_min)
                else:
                    score.tps_normalized = 1.0
                score.raw_tps = chute.tps
            
            # TTFT: lower is better (invert)
            if ttft_values:
                ttft_min, ttft_max = min(ttft_values), max(ttft_values)
                if ttft_max > ttft_min:
                    score.ttft_normalized = 1.0 - (chute.ttft - ttft_min) / (ttft_max - ttft_min)
                else:
                    score.ttft_normalized = 1.0
                score.raw_ttft = chute.ttft
            
            # Quality: derived from total_invocations, higher is better
            if quality_values:
                q = self._derive_quality(chute)
                q_min, q_max = min(quality_values), max(quality_values)
                if q_max > q_min:
                    score.quality_normalized = (q - q_min) / (q_max - q_min)
                else:
                    score.quality_normalized = 1.0
                score.raw_quality = q
            
            # Utilization: lower is better (invert)
            if util_values:
                util_min, util_max = min(util_values), max(util_values)
                if util_max > util_min:
                    score.utilization_normalized = 1.0 - (chute.utilization - util_min) / (util_max - util_min)
                else:
                    score.utilization_normalized = 1.0
                score.raw_utilization = chute.utilization
            
            # Weighted total
            score.total_score = (
                score.tps_normalized * weights.tps +
                score.ttft_normalized * weights.ttft +
                score.quality_normalized * weights.quality +
                score.utilization_normalized * weights.utilization
            )
            
            scores[chute.chute_id] = score
        
        return scores
    
    def _derive_quality(self, chute: ChuteMetrics) -> float:
        """Derive quality score from total_invocations (reliability proxy)."""
        if chute.total_invocations is None:
            return 0.0
        # Normalize to 0-1 based on arbitrary range (can be tuned)
        # Using log scale since invocations can vary widely
        import math
        if chute.total_invocations > 0:
            return min(1.0, math.log10(chute.total_invocations + 1) / 6.0)  # 10^6 = 1.0
        return 0.0
    
    def _fallback_to_utilization(self, chutes: list[ChuteMetrics]) -> RoutingDecision:
        """Fallback when TPS/TTFT unavailable."""
        if not all(c.utilization is not None for c in chutes):
            # No utilization data either - random selection
            import random
            return RoutingDecision(
                selected_chute=random.choice(chutes).chute_id,
                fallback_mode=True,
                decision_reason="No metrics available - random selection",
            )
        
        # Select lowest utilization
        selected = min(chutes, key=lambda c: c.utilization or float('inf'))
        return RoutingDecision(
            selected_chute=selected.chute_id,
            fallback_mode=True,
            decision_reason=f"Fallback to utilization-only: {selected.chute_id} ({selected.utilization:.2f})",
        )
    
    def _generate_reason(self, score: ChuteScore, chutes: list[ChuteMetrics]) -> str:
        """Generate human-readable decision reason."""
        chute = next((c for c in chutes if c.chute_id == score.chute_id), None)
        if not chute:
            return ""
        
        reasons = []
        
        # Identify winning metric
        if score.tps_normalized >= max(score.ttft_normalized, score.quality_normalized, score.utilization_normalized):
            reasons.append(f"highest TPS ({chute.tps:.2f})")
        elif score.ttft_normalized >= max(score.quality_normalized, score.utilization_normalized):
            reasons.append(f"lowest TTFT ({chute.ttft:.2f}s)")
        elif score.quality_normalized >= score.utilization_normalized:
            reasons.append(f"highest reliability ({chute.total_invocations} invocations)")
        else:
            reasons.append(f"lowest utilization ({chute.utilization:.2f})")
        
        return f"{chute.chute_id} selected: {', '.join(reasons)}"


# ============================================================
# Metrics Cache
# ============================================================

@dataclass
class CacheEntry:
    """Single metric cache entry."""
    value: any
    fetched_at: float


class MetricsCache:
    """
    Multi-metric cache with separate TTLs per metric type.
    
    TTL Configuration (user decision: 5min for TPS/TTFT):
    - utilization: 30 seconds (needs to be fresh for load)
    - total_invocations: 5 minutes (derived quality, less volatile)
    - tps: 5 minutes (user decision)
    - ttft: 5 minutes (user decision)
    """
    
    DEFAULT_TTLS = {
        "utilization": 30,           # 30 seconds
        "total_invocations": 300,   # 5 minutes
        "tps": 300,                 # 5 minutes (user decision)
        "ttft": 300,                # 5 minutes (user decision)
    }
    
    def __init__(self, ttls: Optional[dict[str, int]] = None):
        self.ttls = ttls or self.DEFAULT_TTLS
        self._cache: dict[str, dict[str, CacheEntry]] = {}  # chute_id -> metric -> entry
    
    def get(self, chute_id: str, metric: str) -> Optional[any]:
        """Get cached metric value if not expired."""
        if chute_id not in self._cache:
            return None
        
        metric_cache = self._cache[chute_id]
        if metric not in metric_cache:
            return None
        
        entry = metric_cache[metric]
        ttl = self.ttls.get(metric, 30)
        
        if time.time() - entry.fetched_at > ttl:
            # Expired
            del metric_cache[metric]
            return None
        
        return entry.value
    
    def set(self, chute_id: str, metric: str, value: any) -> None:
        """Cache a metric value."""
        if chute_id not in self._cache:
            self._cache[chute_id] = {}
        
        self._cache[chute_id][metric] = CacheEntry(
            value=value,
            fetched_at=time.time()
        )
    
    def get_all(self, chute_id: str) -> Optional[ChuteMetrics]:
        """Get all cached metrics for a chute."""
        if chute_id not in self._cache:
            return None
        
        metric_cache = self._cache[chute_id]
        
        # Check if any metric is still valid
        has_valid = False
        for metric, entry in metric_cache.items():
            ttl = self.ttls.get(metric, 30)
            if time.time() - entry.fetched_at <= ttl:
                has_valid = True
                break
        
        if not has_valid:
            return None
        
        return ChuteMetrics(
            chute_id=chute_id,
            model=metric_cache.get("model", ""),
            tps=self.get(chute_id, "tps"),
            ttft=self.get(chute_id, "ttft"),
            utilization=self.get(chute_id, "utilization"),
            total_invocations=self.get(chute_id, "total_invocations"),
        )
    
    def is_warm(self) -> bool:
        """Check if cache has any data."""
        return len(self._cache) > 0
    
    def clear(self) -> None:
        """Clear all cached data."""
        self._cache.clear()


# ============================================================
# Chutes API Client
# ============================================================

class ChutesAPIClient:
    """
    Client for Chutes API endpoints (chute-level only).
    
    Endpoints used:
    - GET /chutes/utilization - returns chute-level utilization + total_invocations
    - GET /invocations/stats/llm - returns chute-level TPS + TTFT
    
    NOTE: All metrics are at CHUTE LEVEL. Node-level metrics are NOT available.
    Chutes.ai handles internal node/instance selection automatically.
    """
    
    BASE_URL = os.environ.get("CHUTES_API_URL", "http://localhost:8080")
    
    def __init__(self, base_url: Optional[str] = None, http_client=None):
        self.base_url = base_url or self.BASE_URL
        self.client = http_client  # Optional HTTP client for testing
    
    async def fetch_utilization(self) -> list[dict]:
        """Fetch utilization data including total_invocations."""
        # GET /chutes/utilization
        # Returns: [{"chute_id": "...", "utilization": 0.41, "total_invocations": 12345}, ...]
        pass
    
    async def fetch_performance_stats(self) -> list[dict]:
        """Fetch TPS/TTFT performance statistics."""
        # GET /invocations/stats/llm
        # Returns: [{"chute_id": "...", "tps": 28.31, "ttft": 6.45}, ...]
        pass
    
    async def fetch_all_metrics(
        self,
        chute_ids: list[str]
    ) -> list[ChuteMetrics]:
        """Fetch all metrics for specified chutes."""
        # Fetch both endpoints and merge
        utilization_data = await self.fetch_utilization()
        perf_data = await self.fetch_performance_stats()
        
        # Merge by chute_id
        metrics_map = {}
        for u in utilization_data:
            chute_id = u.get("chute_id") or u.get("id")
            if chute_id in chute_ids:
                metrics_map[chute_id] = ChuteMetrics(
                    chute_id=chute_id,
                    model=u.get("model", ""),
                    utilization=u.get("utilization"),
                    total_invocations=u.get("total_invocations"),
                )
        
        for p in perf_data:
            chute_id = p.get("chute_id") or p.get("id")
            if chute_id in metrics_map:
                metrics_map[chute_id].tps = p.get("tps")
                metrics_map[chute_id].ttft = p.get("ttft")
            elif chute_id in chute_ids:
                metrics_map[chute_id] = ChuteMetrics(
                    chute_id=chute_id,
                    model=p.get("model", ""),
                    tps=p.get("tps"),
                    ttft=p.get("ttft"),
                )
        
        return list(metrics_map.values())
```

---

## Data Model

### Configuration Schema (YAML)

```yaml
# litellm-config.yaml extension

router_settings:
  # Routing strategy selection
  routing_strategy: "balanced"  # balanced (default), speed, latency, quality, utilization_only
  
  # Custom weights (optional, overrides strategy defaults)
  # Must sum to 1.0
  routing_weights:
    tps: 0.25
    ttft: 0.25
    quality: 0.25      # derived from total_invocations
    utilization: 0.25
  
  # Cache TTL configuration (seconds)
  # User decision: 5min (300s) for TPS/TTFT
  cache_ttls:
    utilization: 30
    tps: 300          # 5 minutes
    ttft: 300         # 5 minutes
    quality: 300      # 5 minutes (total_invocations)
  
  # Fallback configuration
  fallback_to_utilization: true
  high_utilization_warning_threshold: 0.8
  
  # API endpoints (optional overrides)
  chutes_api_url: "http://localhost:8080"
```

### Environment Variables

```bash
# Routing Configuration
ROUTING_STRATEGY=balanced  # balanced, speed, latency, quality, utilization_only
ROUTING_TPS_WEIGHT=0.25
ROUTING_TTFT_WEIGHT=0.25
ROUTING_QUALITY_WEIGHT=0.25
ROUTING_UTILIZATION_WEIGHT=0.25

# Cache TTLs (seconds)
CACHE_TTL_UTILIZATION=30
CACHE_TTL_TPS=300
CACHE_TTL_TTFT=300
CACHE_TTL_QUALITY=300

# API Configuration
CHUTES_API_URL=http://localhost:8080
```

### Data Structures

```python
# MetricsCache TTLs (finalized per user decision)
{
    "utilization": 30,       # 30 seconds (fresh for load balancing)
    "tps": 300,              # 5 minutes (user decision)
    "ttft": 300,             # 5 minutes (user decision)
    "quality": 300,          # 5 minutes (total_invocations, same as TPS/TTFT)
}

# Strategy Weights (finalized)
{
    "speed": {"tps": 0.5, "ttft": 0.3, "quality": 0.1, "utilization": 0.1},
    "latency": {"tps": 0.1, "ttft": 0.6, "quality": 0.15, "utilization": 0.15},
    "balanced": {"tps": 0.25, "ttft": 0.25, "quality": 0.25, "utilization": 0.25},  # DEFAULT
    "quality": {"tps": 0.15, "ttft": 0.15, "quality": 0.5, "utilization": 0.2},
    "utilization_only": {"tps": 0.0, "ttft": 0.0, "quality": 0.0, "utilization": 1.0},
}
```

---

## API Design

### New Components

| Component | File | Description |
|-----------|------|-------------|
| `ChuteMetrics` | `routing/metrics.py` | Data class for chute metrics |
| `ChuteScore` | `routing/metrics.py` | Data class for scoring results |
| `RoutingStrategy` | `routing/strategy.py` | Enum for routing strategies |
| `StrategyWeights` | `routing/strategy.py` | Weight configuration |
| `MetricsCache` | `routing/cache.py` | Multi-metric cache with TTLs |
| `ChutesAPIClient` | `routing/client.py` | API client for Chutes endpoints |
| `IntelligentMultiMetricRouting` | `routing/intelligent.py` | Main routing strategy implementation |

### Modified Components

| Component | File | Modification |
|-----------|------|--------------|
| `chutes_routing.py` | Root | Add routing strategy selection |
| `litellm-config.yaml` | Root | Add new configuration options |
| `start_litellm.py` | Root | Pass new config to routing |

---

## Technical Approach

### Implementation Strategy

1. **Phase 1: Core Infrastructure**
   - Create `routing/` module with data classes
   - Implement `MetricsCache` with per-metric TTLs
   - Implement `ChutesAPIClient` for API calls

2. **Phase 2: Scoring Algorithm**
   - Implement `IntelligentMultiMetricRouting` class
   - Implement normalization logic for all metrics
   - Implement strategy weight system

3. **Phase 3: Integration**
   - Update `chutes_routing.py` to select strategy
   - Add configuration loading from YAML/env
   - Coexist with existing `ChutesUtilizationRouting`

4. **Phase 4: Testing**
   - Unit tests for scoring algorithm
   - Integration tests for API client
   - BDD scenario tests

### Key Algorithms

#### Score Normalization

```python
# For metrics where HIGHER is better (TPS, quality, low utilization)
normalized = (value - min) / (max - min)

# For metrics where LOWER is better (TTFT, high utilization)
normalized = 1.0 - (value - min) / (max - min)
# OR equivalently:
normalized = (max - value) / (max - min)
```

#### Quality Derivation (total_invocations as reliability proxy)

```python
# Using log scale to handle wide range of invocation counts
quality = min(1.0, log10(total_invocations + 1) / 6.0)
# 10^6 invocations = 1.0 quality
```

#### Weighted Score Calculation

```python
total_score = (
    tps_normalized * weight.tps +
    ttft_normalized * weight.ttft +
    quality_normalized * weight.quality +
    utilization_normalized * weight.utilization
)
```

### Error Handling

| Error Condition | Handling |
|-----------------|----------|
| `/chutes/utilization` API fails | Return cached utilization or fallback to random |
| `/invocations/stats/llm` API fails | Enable fallback mode (utilization-only) |
| All metrics unavailable | Random selection with warning |
| Weights don't sum to 1.0 | Raise `ValueError` on initialization |
| Single chute available | Return directly without scoring |
| Cache expired | Fetch fresh, update cache |

---

## Dependencies

### External Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Chutes API | N/A | `/chutes/utilization`, `/invocations/stats/llm` |
| LiteLLM | Latest | Proxy framework for routing |
| httpx | Latest | Async HTTP client for API calls |
| PyYAML | Latest | Configuration loading |

### Internal Dependencies

| Component | Dependency Type |
|-----------|-----------------|
| `ChutesUtilizationRouting` | Coexists as fallback/alternative |
| `litellm-config.yaml` | Configuration source |
| `chutes_routing.py` | Integration point |

---

## Security Considerations

1. **API Rate Limiting**: Caching with TTLs prevents excessive API calls
2. **Metric Staleness**: Separate TTLs per metric type ensures fresh data
3. **Fallback Safety**: Always routes (even with degraded quality) - no hard failures
4. **Configuration Validation**: Weight validation prevents invalid scoring

---

## Testing Strategy

### Unit Tests

- **Cover**: Input-output examples (EX-001 through EX-004)
- **Framework**: pytest
- **Files**: `tests/test_intelligent_routing.py`

```python
def test_speed_optimized_routing():
    """EX-001: Speed-optimized should select Qwen (highest TPS)."""
    routing = IntelligentMultiMetricRouting(strategy=RoutingStrategy.SPEED)
    decision = routing.select_chute(SAMPLE_CHUTES)
    assert decision.selected_chute == "Qwen/Qwen3.5-397B-A17B-TEE"

def test_latency_optimized_routing():
    """EX-002: Latency-optimized should select Kimi (lowest TTFT)."""
    routing = IntelligentMultiMetricRouting(strategy=RoutingStrategy.LATENCY)
    decision = routing.select_chute(SAMPLE_CHUTES)
    assert decision.selected_chute == "moonshotai/kimi-k2.5-tee"

def test_balanced_routing():
    """EX-003: Balanced should select Kimi (best overall)."""
    routing = IntelligentMultiMetricRouting(strategy=RoutingStrategy.BALANCED)
    decision = routing.select_chute(SAMPLE_CHUTES)
    assert decision.selected_chute == "moonshotai/kimi-k2.5-tee"

def test_quality_optimized_routing():
    """EX-004: Quality-optimized should select Kimi (highest quality)."""
    routing = IntelligentMultiMetricRouting(strategy=RoutingStrategy.QUALITY)
    decision = routing.select_chute(SAMPLE_CHUTES)
    assert decision.selected_chute == "moonshotai/kimi-k2.5-tee"

def test_fallback_to_utilization():
    """EC-001: Missing TPS/TTFT should fallback to utilization-only."""
    # ... test implementation
```

### Integration Tests

- **Cover**: Edge cases (EC-001 through EC-005), State transitions (ST-001 through ST-003)
- **Framework**: pytest + httpx
- **Files**: `tests/test_intelligent_routing_integration.py`

### BDD Tests

- **Cover**: All BDD scenarios (BDD-001 through BDD-014)
- **Framework**: pytest-bdd
- **Files**: `tests/bdd/intelligent_routing.feature`, `tests/bdd/steps/`

---

## File Structure

### New Files to Create

```
routing/
├── __init__.py
├── metrics.py          # ChuteMetrics, ChuteScore, RoutingDecision
├── strategy.py         # RoutingStrategy enum, StrategyWeights
├── cache.py            # MetricsCache with per-metric TTLs
├── client.py           # ChutesAPIClient
└── intelligent.py      # IntelligentMultiMetricRouting

tests/
├── __init__.py
├── conftest.py
├── test_intelligent_routing.py      # Unit tests
├── test_intelligent_routing_integration.py  # Integration tests
└── bdd/
    ├── __init__.py
    ├── intelligent_routing.feature  # Gherkin scenarios
    └── steps/
        ├── __init__.py
        └── routing_steps.py        # Step definitions
```

### Modifications to Existing Files

| File | Changes |
|------|---------|
| `chutes_routing.py` | Import and select `IntelligentMultiMetricRouting` based on config |
| `litellm-config.yaml` | Add routing configuration section |
| `start_litellm.py` | Pass config to routing (if needed) |

---

## Implementation Checklist

- [ ] Create `routing/metrics.py` with data classes
- [ ] Create `routing/strategy.py` with enum and weights
- [ ] Create `routing/cache.py` with multi-metric TTL cache
- [ ] Create `routing/client.py` for API calls
- [ ] Create `routing/intelligent.py` with main implementation
- [ ] Implement normalization algorithm
- [ ] Implement quality derivation from total_invocations
- [ ] Implement fallback to utilization-only
- [ ] Add configuration loading from YAML
- [ ] Add configuration loading from environment variables
- [ ] Update `chutes_routing.py` to support new strategy
- [ ] Write unit tests for EX-001 through EX-004
- [ ] Write unit tests for EC-001 through EC-005
- [ ] Write integration tests for ST-001 through ST-003
- [ ] Create BDD test files
- [ ] Verify all examples pass

---

## Notes

- **Platform Constraint**: This design implements chute-level routing only. Chutes.ai handles internal node/instance selection automatically. We cannot target specific nodes within a chute.

- **User Decision: Skip /miner/scores**: Quality is derived from `total_invocations` in `/chutes/utilization` response
- **User Decision: 5-minute refresh**: TPS/TTFT cached for 5 minutes (300s), utilization at 30s
- **User Decision: Balanced default**: 25% weights each for TPS, TTFT, quality, utilization
- **User Decision: Coexist**: New `IntelligentMultiMetricRouting` runs alongside existing `ChutesUtilizationRouting`
- **Backward Compatibility**: Existing configurations continue to work; new features opt-in

- Reference `examples.md` for exact input/output values used in tests
- Reference `behavior.md` for Gherkin scenario definitions
- Reference `proposal.md` for scope and success criteria
