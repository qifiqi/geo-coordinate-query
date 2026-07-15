"""Unified place-query service built from provider strategies."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from .map_services import amap_search_candidates, baidu_search_candidates
from .matching import address_similarity

ProviderName = Literal["amap", "baidu", "auto"]


@dataclass(frozen=True)
class PlaceCandidate:
    """A geocoding or POI candidate ranked for one input query."""

    provider: str
    score: float
    data: Mapping[str, Any]

    @property
    def label(self) -> str:
        return str(self.data.get("name") or self.data.get("address") or "未命名地点")

    def as_dict(self) -> dict[str, Any]:
        return {**self.data, "provider": self.provider, "similarity": self.score}


class CandidateProvider(Protocol):
    """Strategy interface for a map provider's place candidate lookup."""

    name: str

    def search(self, keyword: str, city: str) -> Sequence[Mapping[str, Any]]:
        """Return raw candidates for one query."""


@dataclass(frozen=True)
class AmapCandidateProvider:
    """High-level AMap lookup strategy."""

    name: str = "amap"

    def search(self, keyword: str, city: str) -> Sequence[Mapping[str, Any]]:
        return amap_search_candidates(keyword, city)


@dataclass(frozen=True)
class BaiduCandidateProvider:
    """High-level Baidu Maps lookup strategy."""

    name: str = "baidu"

    def search(self, keyword: str, city: str) -> Sequence[Mapping[str, Any]]:
        return baidu_search_candidates(keyword, city)


class PlaceQueryService:
    """Coordinate candidate lookup and ranking across map providers."""

    def __init__(self, providers: Sequence[CandidateProvider] | None = None) -> None:
        selected = providers or (AmapCandidateProvider(), BaiduCandidateProvider())
        self._providers = {provider.name: provider for provider in selected}

    def search(
        self,
        keyword: str,
        city: str = "",
        provider: ProviderName = "auto",
    ) -> list[PlaceCandidate]:
        """Return ranked candidates, optionally restricted to one provider."""
        if not keyword.strip():
            return []
        provider_names = tuple(self._providers) if provider == "auto" else (provider,)
        candidates: list[PlaceCandidate] = []
        for provider_name in provider_names:
            strategy = self._providers.get(provider_name)
            if strategy is None:
                raise ValueError(f"不支持的地图服务: {provider_name}")
            for data in strategy.search(keyword, city):
                candidates.append(
                    PlaceCandidate(
                        provider_name,
                        _candidate_score(keyword, city, data),
                        data,
                    )
                )
        return sorted(
            candidates,
            key=lambda candidate: (candidate.score, bool(candidate.data.get("accurate"))),
            reverse=True,
        )

    def resolve(
        self,
        keyword: str,
        city: str = "",
        provider: ProviderName = "auto",
    ) -> PlaceCandidate | None:
        """Return the top-ranked candidate, if the provider returns one."""
        candidates = self.search(keyword, city, provider)
        return candidates[0] if candidates else None


def _candidate_score(keyword: str, city: str, data: Mapping[str, Any]) -> float:
    score = address_similarity(keyword, data)
    name = str(data.get("name", ""))
    place_type = str(data.get("type", ""))
    if _is_area_query(keyword):
        if any(marker in name for marker in _ORGANIZATION_MARKERS):
            score -= 0.35
        if any(marker in place_type for marker in _LANDMARK_TYPE_MARKERS):
            score += 0.12

    if city:
        city_name = str(data.get("city", "")).replace("市", "")
        expected_city = city.replace("市", "")
        address = f"{data.get('address', '')}{name}"
        if city_name == expected_city or expected_city in address:
            score += 0.08
        elif city_name:
            score -= 0.2
    return round(max(0.0, min(1.0, score)), 2)


_AREA_SUFFIXES = ("区", "街区", "景区", "公园", "广场", "风貌区")
_ORGANIZATION_MARKERS = ("公司", "工作专班", "指挥部", "办事处", "管理处")
_LANDMARK_TYPE_MARKERS = ("风景名胜", "公园", "广场", "景点")


def _is_area_query(keyword: str) -> bool:
    return keyword.strip().endswith(_AREA_SUFFIXES)
