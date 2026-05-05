"""
Technician-facing search service.

This module is the small interface for ASR-aware EAM search use cases. QueryEngine
remains the internal parser/ranker; tool and REST adapters should depend on this
service rather than rebuilding fallback and response behavior locally.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from models.schemas import WorkOrderStatus
from services.base_eam import BaseEAMService
from services.query_engine import QueryEngine, SearchIntent, SearchQuery

logger = logging.getLogger("maintenance-eye.search-service")


class SearchService:
    """Use-case interface for technician search workflows."""

    def __init__(self, engine: QueryEngine | None = None):
        self._engine = engine or QueryEngine()

    async def smart_search(
        self,
        eam_service: Any,
        *,
        query: str,
        search_type: str = "auto",
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search across EAM entities and return agent-ready formatted results."""
        parsed = self._engine.build_query(query)

        if search_type != "auto":
            try:
                parsed.intent = SearchIntent(search_type)
            except ValueError:
                pass

        result = await self._engine.execute_search(parsed, eam_service, limit=limit)
        response = {
            "success": True,
            "intent": parsed.intent.value,
            "confidence": round(parsed.confidence, 2),
            "total": result.total,
            "has_results": result.total > 0,
            "results": [self._format_scored_item(item) for item in result.items],
            "search_metadata": {
                "raw_input": parsed.raw_input,
                "normalized_terms": parsed.normalized_terms,
                "extracted_ids": parsed.extracted_ids,
                "filters": parsed.filters,
                "expanded_terms": parsed.expanded_terms,
                "search_time_ms": result.search_time_ms,
            },
        }
        if result.total == 0 and parsed.intent in {
            SearchIntent.work_order,
            SearchIntent.asset,
            SearchIntent.auto,
        }:
            response.update(
                await self._asset_confirmation_fields(
                    query,
                    eam_service,
                    parsed=parsed,
                    no_suggestion_message="Ask the user to confirm the exact asset tag.",
                    no_records_label=self._no_records_label(parsed, "records"),
                )
            )
        return response

    async def lookup_asset(
        self,
        eam_service: Any,
        *,
        query: str = "",
        asset_id: str = "",
        department: str = "",
        station: str = "",
        asset_type: str = "",
        limit: int = 10,
    ) -> dict[str, Any]:
        """Look up assets by exact ID or ASR-normalized natural-language query."""
        if asset_id:
            asset = await eam_service.get_asset(asset_id)
            if not asset:
                normalized = QueryEngine.normalize_asset_id(asset_id)
                if normalized and normalized != asset_id:
                    asset = await eam_service.get_asset(normalized)

            if asset:
                return {"found": True, "count": 1, "assets": [asset.model_dump()]}

            suggestions = await self._engine.suggest_asset_candidates(
                asset_id,
                eam_service,
                limit=3,
            )
            if suggestions:
                suggestion_ids = ", ".join(s["asset_id"] for s in suggestions)
                return {
                    "found": False,
                    "count": 0,
                    "needs_asset_confirmation": True,
                    "guessed_assets": suggestions,
                    "message": f"No asset found with ID: {asset_id}. Did you mean {suggestion_ids}?",
                }
            return {
                "found": False,
                "count": 0,
                "assets": [],
                "message": f"No asset found with ID: {asset_id}",
            }

        if query:
            parsed = self._engine.build_query(query)
            extracted_assets = await self._lookup_extracted_assets(
                parsed.extracted_ids,
                eam_service,
                limit=limit,
            )
            if extracted_assets:
                return {
                    "found": True,
                    "count": len(extracted_assets),
                    "assets": [asset.model_dump() for asset in extracted_assets],
                }

            department = department or parsed.filters.get("department", "")
            asset_type = asset_type or parsed.filters.get("asset_type", "")
            station = station or parsed.filters.get("location", "")
            query = " ".join(parsed.normalized_terms + parsed.expanded_terms)

        assets = await eam_service.search_assets(
            query=query,
            department=department,
            station=station,
            asset_type=asset_type,
        )
        if not assets and (department or station or asset_type):
            assets = await eam_service.search_assets(query=query)
        return {
            "found": len(assets) > 0,
            "count": len(assets),
            "assets": [asset.model_dump() for asset in assets[:limit]],
        }

    async def search_assets(
        self,
        eam_service: Any,
        *,
        query: str = "",
        department: str = "",
        station: str = "",
        asset_type: str = "",
        limit: int | None = None,
    ) -> list[Any]:
        """Return REST-compatible assets using the same ASR-aware normalization."""
        raw_query = query
        if query:
            parsed = self._engine.build_query(query)
            extracted_assets = await self._lookup_extracted_assets(
                parsed.extracted_ids,
                eam_service,
                limit=limit or 10_000,
            )
            if extracted_assets:
                return extracted_assets[:limit] if limit else extracted_assets

            department = department or parsed.filters.get("department", "")
            asset_type = asset_type or parsed.filters.get("asset_type", "")
            station = station or parsed.filters.get("location", "")
            query = " ".join(parsed.normalized_terms)

        assets = cast(
            list[Any],
            await eam_service.search_assets(
                query=query,
                department=department,
                station=station,
                asset_type=asset_type,
            ),
        )
        if not assets and (department or station or asset_type):
            assets = cast(list[Any], await eam_service.search_assets(query=query))
        if not assets and raw_query and raw_query != query:
            assets = cast(list[Any], await eam_service.search_assets(query=raw_query))
        return assets[:limit] if limit else assets

    async def search_work_orders(
        self,
        eam_service: Any,
        *,
        query: str = "",
        asset_id: str = "",
        status: str = "",
        priority: str = "",
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search work orders with ASR-aware parsing, expansion, and suggestions."""
        parsed = self._engine.build_query(query)
        wo_status = self._parse_work_order_status(status)
        if not wo_status and "status" in parsed.filters:
            wo_status = self._parse_work_order_status(parsed.filters["status"])

        resolved_priority = priority or parsed.filters.get("priority", "")
        resolved_department = parsed.filters.get("department", "")
        search_parts = list(parsed.normalized_terms)
        existing_upper = {part.upper() for part in search_parts}
        for eid in parsed.extracted_ids:
            upper = eid.upper()
            if not upper.startswith("WO-") and upper not in existing_upper:
                search_parts.append(upper)
                existing_upper.add(upper)
        if asset_id and asset_id.upper() not in existing_upper:
            search_parts.append(asset_id.upper())
        q_text = " ".join(search_parts)

        result = await eam_service.search_work_orders(
            q=q_text,
            priority=resolved_priority,
            department=resolved_department,
            status=wo_status,
            location=parsed.filters.get("location", ""),
        )

        if len(result) < 3 and parsed.expanded_terms:
            expanded_result = await eam_service.search_work_orders(
                q=" ".join(parsed.expanded_terms),
                priority=resolved_priority,
                department=resolved_department,
                status=wo_status,
                location=parsed.filters.get("location", ""),
            )
            existing_ids = {wo.wo_id for wo in result}
            for wo in expanded_result:
                if wo.wo_id not in existing_ids:
                    result.append(wo)

        result = BaseEAMService.sort_work_orders_latest_first(result)
        response: dict[str, Any] = {
            "success": True,
            "count": len(result),
            "work_orders": [wo.model_dump() for wo in result[:limit]],
        }
        if not result:
            response.update(
                await self._asset_confirmation_fields(
                    query,
                    eam_service,
                    parsed=parsed,
                    candidate_asset_ids=[asset_id] if asset_id else [],
                    no_suggestion_message="Please confirm the exact asset tag.",
                    no_records_label=self._work_order_no_records_label(wo_status),
                )
            )
        return response

    async def search_work_order_records(
        self,
        eam_service: Any,
        *,
        query: str = "",
        priority: str = "",
        department: str = "",
        status: WorkOrderStatus | None = None,
        location: str = "",
    ) -> list[Any]:
        """Return REST-compatible work-order records with ASR-aware query parsing."""
        parsed = self._engine.build_query(query)
        search_parts = list(parsed.normalized_terms)
        existing_upper = {part.upper() for part in search_parts}
        for eid in parsed.extracted_ids:
            upper = eid.upper()
            if not upper.startswith("WO-") and upper not in existing_upper:
                search_parts.append(upper)
                existing_upper.add(upper)
        records = cast(
            list[Any],
            await eam_service.search_work_orders(
                q=" ".join(search_parts),
                priority=priority or parsed.filters.get("priority", ""),
                department=department or parsed.filters.get("department", ""),
                status=status or self._parse_work_order_status(parsed.filters.get("status", "")),
                location=location or parsed.filters.get("location", ""),
            ),
        )
        return BaseEAMService.sort_work_orders_latest_first(records)

    @staticmethod
    def _format_scored_item(scored_item: Any) -> dict[str, Any]:
        item = scored_item.item
        entry = {
            "score": round(scored_item.score, 2),
            "type": scored_item.entity_type,
            "match": scored_item.match_type,
        }
        if hasattr(item, "model_dump"):
            entry["data"] = item.model_dump()
        elif isinstance(item, dict):
            entry["data"] = item
        else:
            entry["data"] = str(item)
        return entry

    async def _lookup_extracted_assets(
        self,
        extracted_ids: list[str],
        eam_service: Any,
        *,
        limit: int,
    ) -> list[Any]:
        assets: list[Any] = []
        seen_asset_ids: set[str] = set()
        for eid in extracted_ids:
            upper = eid.upper()
            if upper.startswith("WO-"):
                continue
            asset = await eam_service.get_asset(upper)
            if asset and asset.asset_id not in seen_asset_ids:
                assets.append(asset)
                seen_asset_ids.add(asset.asset_id)
            if len(assets) >= limit:
                break
        return assets

    async def _asset_confirmation_fields(
        self,
        raw_query: str,
        eam_service: Any,
        *,
        parsed: SearchQuery | None = None,
        candidate_asset_ids: list[str] | None = None,
        no_suggestion_message: str,
        no_records_label: str,
    ) -> dict[str, Any]:
        parsed = parsed or self._engine.build_query(raw_query)
        known_asset_ids = await self._known_asset_ids(
            eam_service,
            list(candidate_asset_ids or []) + list(parsed.extracted_ids),
        )
        if known_asset_ids:
            asset_label = ", ".join(known_asset_ids)
            return {
                "attempted_asset_ids": known_asset_ids,
                "message": f"No {no_records_label} found for {asset_label}.",
            }

        hints = QueryEngine.extract_asset_hints(raw_query)
        suggestions = await self._engine.suggest_asset_candidates(raw_query, eam_service, limit=3)
        if suggestions:
            suggestion_ids = ", ".join(s["asset_id"] for s in suggestions)
            hinted = ", ".join(hints) if hints else "that asset ID"
            return {
                "needs_asset_confirmation": True,
                "attempted_asset_hints": hints,
                "guessed_assets": suggestions,
                "message": f"No {no_records_label} found for {hinted}. Did you mean {suggestion_ids}?",
            }
        if hints:
            hinted = ", ".join(hints)
            return {
                "no_asset_match": True,
                "attempted_asset_hints": hints,
                "message": f"No asset found matching {hinted}. {no_suggestion_message}",
            }
        return {}

    async def _known_asset_ids(
        self,
        eam_service: Any,
        asset_ids: list[str],
    ) -> list[str]:
        known_asset_ids: list[str] = []
        for asset_id in asset_ids:
            upper = (asset_id or "").upper()
            if not upper or upper.startswith("WO-"):
                continue
            asset = await eam_service.get_asset(upper)
            if asset and asset.asset_id not in known_asset_ids:
                known_asset_ids.append(asset.asset_id)
        return known_asset_ids

    @staticmethod
    def _work_order_no_records_label(status: WorkOrderStatus | None) -> str:
        if not status:
            return "work orders"
        return f"{status.value.replace('_', ' ')} work orders"

    @staticmethod
    def _no_records_label(parsed: SearchQuery, fallback: str) -> str:
        if parsed.intent == SearchIntent.work_order:
            status = parsed.filters.get("status", "")
            if status:
                return f"{status.replace('_', ' ')} work orders"
            return "work orders"
        return fallback

    @staticmethod
    def _parse_work_order_status(status: str) -> WorkOrderStatus | None:
        if not status:
            return None
        try:
            return WorkOrderStatus(status.lower())
        except ValueError:
            return None
