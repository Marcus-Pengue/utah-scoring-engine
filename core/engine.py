"""
Utah Pollinator Path - Core Engine
==================================
Shared base classes for both tools:
- Tool 1: Homeowner Competition (PollinatorPath)
- Tool 2: Municipal Opportunity Finder
"""

import math
import hashlib
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json
import os


class HabitatGrade(Enum):
    """Habitat quality grades"""
    A_PLUS = ("A+", "Premium Pollinator Site", 90)
    A = ("A", "Excellent Potential", 80)
    B = ("B", "Good Potential", 70)
    C = ("C", "Moderate Potential", 60)
    D = ("D", "Limited Potential", 50)
    F = ("F", "Challenging Site", 0)
    
    def __init__(self, letter: str, description: str, min_score: int):
        self.letter = letter
        self.description = description
        self.min_score = min_score
    
    @classmethod
    def from_score(cls, score: float) -> 'HabitatGrade':
        for grade in cls:
            if score >= grade.min_score:
                return grade
        return cls.F


@dataclass
class Location:
    """Geographic location with privacy-preserving grid hash."""
    lat: float
    lng: float
    name: str = ""
    address: str = ""
    grid_hash: str = field(default="", repr=False)
    
    def __post_init__(self):
        if not self.grid_hash:
            self.grid_hash = self._compute_grid_hash()
    
    def _compute_grid_hash(self, precision: int = 3) -> str:
        grid_lat = round(self.lat, precision)
        grid_lng = round(self.lng, precision)
        return f"{grid_lat}_{grid_lng}"
    
    def distance_to(self, other: 'Location') -> float:
        R = 6371000
        phi1 = math.radians(self.lat)
        phi2 = math.radians(other.lat)
        delta_phi = math.radians(other.lat - self.lat)
        delta_lambda = math.radians(other.lng - self.lng)
        a = (math.sin(delta_phi/2)**2 + 
             math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
    
    def to_dict(self) -> Dict:
        return {"lat": self.lat, "lng": self.lng, "name": self.name, "grid_hash": self.grid_hash}


@dataclass
class FactorResult:
    """Result from a single scoring factor"""
    name: str
    raw_value: Any
    normalized_score: float
    weight: float = 0.0
    weighted_score: float = 0.0
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name, "raw_value": self.raw_value,
            "normalized_score": round(self.normalized_score, 3),
            "weight": round(self.weight, 3),
            "weighted_score": round(self.weighted_score, 3),
            "metadata": self.metadata
        }


@dataclass
class Recommendation:
    """Actionable recommendation for habitat improvement"""
    priority: str
    action: str
    reason: str
    impact: str = ""
    species: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {"priority": self.priority, "action": self.action, 
                "reason": self.reason, "impact": self.impact, "species": self.species}


@dataclass
class ScoringResult:
    """Complete scoring result for a location"""
    location: Location
    total_score: float
    max_possible: float
    percentage: float
    grade: HabitatGrade
    factors: List[FactorResult]
    recommendations: List[Recommendation]
    algorithm: str
    tool: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "location": self.location.to_dict(),
            "total_score": round(self.total_score, 2),
            "max_possible": round(self.max_possible, 2),
            "percentage": round(self.percentage, 1),
            "grade": self.grade.letter,
            "grade_description": self.grade.description,
            "factors": [f.to_dict() for f in self.factors],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "algorithm": self.algorithm, "tool": self.tool,
            "timestamp": self.timestamp, "metadata": self.metadata
        }


class CacheManager:
    """In-memory cache with TTL for API responses."""
    
    def __init__(self, ttl_hours: int = 24, max_entries: int = 1000):
        self.ttl_hours = ttl_hours
        self.max_entries = max_entries
        self._cache: Dict[str, Dict] = {}
        self.stats = {"hits": 0, "misses": 0, "evictions": 0}
    
    def _make_key(self, source: str, grid_hash: str) -> str:
        return f"{source}:{grid_hash}"
    
    def get(self, source: str, location: Location) -> Optional[Dict]:
        key = self._make_key(source, location.grid_hash)
        if key in self._cache:
            entry = self._cache[key]
            age = datetime.utcnow() - entry["timestamp"]
            if age < timedelta(hours=self.ttl_hours):
                self.stats["hits"] += 1
                return entry["data"]
            else:
                del self._cache[key]
        self.stats["misses"] += 1
        return None
    
    def set(self, source: str, location: Location, data: Dict):
        if len(self._cache) >= self.max_entries:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]["timestamp"])
            del self._cache[oldest_key]
            self.stats["evictions"] += 1
        key = self._make_key(source, location.grid_hash)
        self._cache[key] = {"data": data, "timestamp": datetime.utcnow()}
    
    def clear(self):
        self._cache.clear()
    
    def get_stats(self) -> Dict:
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total * 100) if total > 0 else 0
        return {**self.stats, "entries": len(self._cache), "hit_rate_percent": round(hit_rate, 1)}


class DataSource(ABC):
    """Abstract base for data sources."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    async def fetch(self, location: Location, **kwargs) -> Dict[str, Any]:
        pass


class ScoringFactor(ABC):
    """Abstract base for scoring factors."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def max_points(self) -> float:
        pass
    
    @property
    def required_sources(self) -> List[str]:
        return []
    
    @abstractmethod
    def calculate(self, data: Dict[str, Any]) -> FactorResult:
        pass
    
    def get_recommendations(self, result: FactorResult) -> List[Recommendation]:
        return []


class ScoringAlgorithm(ABC):
    """Abstract base for scoring algorithms."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def tool(self) -> str:
        pass
    
    @abstractmethod
    def calculate(self, location: Location, data: Dict[str, Any]) -> ScoringResult:
        pass


class PollinatorEngine:
    """Main scoring engine - orchestrates sources, factors, and algorithms."""
    
    def __init__(self, cache_ttl_hours: int = 24):
        self._sources: Dict[str, DataSource] = {}
        self._algorithms: Dict[str, ScoringAlgorithm] = {}
        self._cache = CacheManager(ttl_hours=cache_ttl_hours)
    
    def register_source(self, source: DataSource):
        self._sources[source.name] = source
    
    def register_algorithm(self, algorithm: ScoringAlgorithm):
        self._algorithms[algorithm.name] = algorithm
    
    def list_sources(self) -> List[str]:
        return list(self._sources.keys())
    
    def list_algorithms(self) -> List[str]:
        return list(self._algorithms.keys())
    
    async def fetch_data(self, location: Location, sources: List[str] = None) -> Dict[str, Any]:
        sources = sources or list(self._sources.keys())
        data = {"_location": location}
        for source_name in sources:
            source = self._sources.get(source_name)
            if not source:
                continue
            cached = self._cache.get(source_name, location)
            if cached is not None:
                data[source_name] = cached
                continue
            try:
                result = await source.fetch(location)
                data[source_name] = result
                self._cache.set(source_name, location, result)
            except Exception as e:
                data[source_name] = {"error": str(e)}
        return data
    
    async def score(self, location: Location, algorithm: str = "homeowner_v1") -> ScoringResult:
        algo = self._algorithms.get(algorithm)
        if not algo:
            raise ValueError(f"Unknown algorithm: {algorithm}")
        data = await self.fetch_data(location)
        return algo.calculate(location, data)
    
    async def batch_score(self, locations: List[Location], algorithm: str = "homeowner_v1") -> List[ScoringResult]:
        results = []
        for loc in locations:
            result = await self.score(loc, algorithm)
            results.append(result)
        return results
    
    def get_cache_stats(self) -> Dict:
        return self._cache.get_stats()
    
    def clear_cache(self):
        self._cache.clear()
    
    def export_config(self) -> Dict:
        return {"sources": self.list_sources(), "algorithms": self.list_algorithms(), "cache_stats": self.get_cache_stats()}
