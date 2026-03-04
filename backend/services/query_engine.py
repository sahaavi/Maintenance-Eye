"""
Intelligent Search Query Engine
Pre-query intelligence layer that normalizes, transforms, and routes
natural language queries from technicians to the appropriate EAM service methods.
"""

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("maintenance-eye.query-engine")


# ---------------------------------------------------------------------------
# Enums & Data Classes
# ---------------------------------------------------------------------------

class SearchIntent(str, Enum):
    work_order = "work_order"
    asset = "asset"
    location = "location"
    eam_code = "eam_code"
    knowledge = "knowledge"
    auto = "auto"


@dataclass
class SearchQuery:
    intent: SearchIntent
    raw_input: str
    normalized_terms: list[str] = field(default_factory=list)
    filters: dict[str, str] = field(default_factory=dict)
    extracted_ids: list[str] = field(default_factory=list)
    expanded_terms: list[str] = field(default_factory=list)
    confidence: float = 0.5


@dataclass
class ScoredItem:
    item: Any
    score: float
    match_type: str  # "exact_id", "name", "description", "code", "expanded"
    entity_type: str  # "work_order", "asset", "eam_code", "knowledge", "location"


@dataclass
class SearchResult:
    items: list[ScoredItem]
    total: int
    query: SearchQuery
    search_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# Constants — Alias Maps & Patterns
# ---------------------------------------------------------------------------

NOISE_WORDS = frozenset({
    "the", "a", "an", "for", "in", "at", "on", "about", "of", "to", "is",
    "are", "was", "were", "be", "been", "with", "and", "or", "not", "it",
    "show", "find", "get", "search", "look", "up", "lookup", "me", "my",
    "all", "list", "display", "what", "where", "which", "how", "please",
    "can", "you", "i", "need", "want",
    # Entity-type meta-words: describe WHAT the user wants, not content to match
    "work", "order", "orders", "wo", "wos", "ticket", "tickets",
    "asset", "assets", "equipment",
    "report", "reports", "record", "records",
    "inspection", "inspections",
})

PRIORITY_ALIASES: dict[str, str] = {
    "critical": "P1", "emergency": "P1", "urgent": "P1", "p1": "P1",
    "high": "P2", "important": "P2", "p2": "P2",
    "medium": "P3", "med": "P3", "moderate": "P3", "p3": "P3",
    "low": "P4", "minor": "P4", "p4": "P4",
    "planned": "P5", "routine": "P5", "scheduled": "P5", "p5": "P5",
}

STATUS_ALIASES: dict[str, str] = {
    "open": "open", "new": "open", "active": "open", "pending": "open",
    "wip": "in_progress", "in_progress": "in_progress", "progress": "in_progress",
    "working": "in_progress", "started": "in_progress",
    "done": "completed", "closed": "completed", "complete": "completed",
    "finished": "completed", "resolved": "completed",
    "hold": "on_hold", "waiting": "on_hold", "on_hold": "on_hold",
    "paused": "on_hold", "blocked": "on_hold",
    "cancelled": "cancelled", "canceled": "cancelled",
}

DEPARTMENT_ALIASES: dict[str, str] = {
    "rolling_stock": "rolling_stock", "rolling stock": "rolling_stock",
    "rolling": "rolling_stock", "trains": "rolling_stock", "train": "rolling_stock",
    "guideway": "guideway", "track": "guideway", "tracks": "guideway",
    "switch": "guideway", "rail": "guideway",
    "power": "power", "electrical": "power", "electric": "power",
    "signal_telecom": "signal_telecom", "signal": "signal_telecom",
    "signals": "signal_telecom", "telecom": "signal_telecom",
    "communication": "signal_telecom", "comms": "signal_telecom",
    "facilities": "facilities", "station": "facilities", "building": "facilities",
    "elevating_devices": "elevating_devices", "elevating": "elevating_devices",
    "elevator": "elevating_devices", "escalator": "elevating_devices",
    "elevators": "elevating_devices", "escalators": "elevating_devices",
}

ASSET_TYPE_ALIASES: dict[str, str] = {
    "escalator": "escalator", "esc": "escalator",
    "elevator": "elevator", "elv": "elevator", "lift": "elevator",
    "switch_machine": "switch_machine", "switch machine": "switch_machine",
    "switch": "switch_machine", "swm": "switch_machine",
    "hvac_unit": "hvac_unit", "hvac": "hvac_unit", "ac": "hvac_unit",
    "air conditioning": "hvac_unit", "hvac_station": "hvac_station",
    "rail_section": "rail_section", "rail": "rail_section",
    "train_car": "train_car", "train": "train_car", "car": "train_car",
    "bogie": "bogie", "truck": "bogie",
    "transformer": "transformer", "xfmr": "transformer",
    "rectifier": "rectifier",
    "signal_controller": "signal_controller", "signal controller": "signal_controller",
    "track_circuit": "track_circuit", "track circuit": "track_circuit",
    "door_system": "door_system", "door": "door_system", "doors": "door_system",
    "platform_door": "platform_door", "platform door": "platform_door",
    "third_rail": "third_rail", "third rail": "third_rail",
    "power_cable": "power_cable", "cable": "power_cable",
    "radio_unit": "radio_unit", "radio": "radio_unit",
    "cctv_camera": "cctv_camera", "cctv": "cctv_camera", "camera": "cctv_camera",
    "lighting_panel": "lighting_panel", "lighting": "lighting_panel",
    "fire_suppression": "fire_suppression", "fire": "fire_suppression",
    "track_bed": "track_bed", "trackbed": "track_bed",
}

# Symptom → related search terms + EAM problem codes
SYNONYM_MAP: dict[str, dict] = {
    "vibration": {"terms": ["noise", "shaking", "rattling"], "codes": ["ME-008"]},
    "noise": {"terms": ["vibration", "rattling", "grinding"], "codes": ["ME-008"]},
    "leak": {"terms": ["fluid", "drip", "seepage", "oil"], "codes": ["ME-006"]},
    "corrosion": {"terms": ["rust", "oxidation", "galvanic"], "codes": ["ME-002"]},
    "rust": {"terms": ["corrosion", "oxidation"], "codes": ["ME-002"]},
    "wear": {"terms": ["worn", "erosion", "abrasion", "degraded"], "codes": ["ME-003"]},
    "crack": {"terms": ["fracture", "break", "split", "structural"], "codes": ["ME-001"]},
    "broken": {"terms": ["failure", "damaged", "malfunction", "fault"], "codes": ["ME-005"]},
    "hot": {"terms": ["temperature", "overheating", "thermal"], "codes": ["ME-011"]},
    "overheat": {"terms": ["temperature", "hot", "thermal"], "codes": ["ME-011"]},
    "misalign": {"terms": ["alignment", "offset", "skew"], "codes": ["ME-007"]},
    "alignment": {"terms": ["misaligned", "offset", "skew"], "codes": ["ME-007"]},
    "electrical": {"terms": ["wiring", "circuit", "short"], "codes": ["ME-004"]},
    "short": {"terms": ["electrical", "circuit", "arc"], "codes": ["ME-004"]},
    "safety": {"terms": ["hazard", "danger", "risk"], "codes": ["ME-009"]},
    "contamination": {"terms": ["debris", "dirt", "fouling"], "codes": ["ME-010"]},
    "signal": {"terms": ["degradation", "interference", "loss"], "codes": ["ME-012"]},
    "water": {"terms": ["ingress", "moisture", "flooding"], "codes": ["ME-013"]},
    "insulation": {"terms": ["degradation", "breakdown"], "codes": ["ME-014"]},
    "drainage": {"terms": ["drain", "trackbed", "ballast", "water"], "codes": ["ME-013"]},
    "trackbed": {"terms": ["ballast", "drainage", "subgrade", "track bed"], "codes": []},
    "ballast": {"terms": ["trackbed", "drainage", "subgrade"], "codes": []},
    "loto": {"terms": ["lockout", "tagout", "safety"], "codes": ["ME-009"]},
    "lockout": {"terms": ["loto", "tagout", "safety"], "codes": ["ME-009"]},
}

# Asset ID prefix → entity type code
_ASSET_ID_PREFIXES = {
    "ESC": "escalator", "ELV": "elevator", "SWM": "switch_machine",
    "RAL": "rail_section", "TRN": "train_car", "BOG": "bogie",
    "TRF": "transformer", "RCT": "rectifier", "SIG": "signal_controller",
    "TRK": "track_circuit", "DOR": "door_system", "PLD": "platform_door",
    "THR": "third_rail", "PWR": "power_cable", "RAD": "radio_unit",
    "CTV": "cctv_camera", "LIT": "lighting_panel", "FIR": "fire_suppression",
    "HVA": "hvac_unit", "HVS": "hvac_station", "TBD": "track_bed",
}

# Regex patterns for ID detection
_WO_ID_PATTERN = re.compile(
    r"(?:WO[-\s]?)?(\d{4})[-\s]?(\d{3,5})",
    re.IGNORECASE,
)
_ASSET_ID_PATTERN = re.compile(
    r"([A-Z]{2,3})[-\s]([A-Z]{2})[-\s](\d{3,4})",
    re.IGNORECASE,
)
_WO_FULL_ID_PATTERN = re.compile(
    r"WO-\d{4}-\d{4}",
    re.IGNORECASE,
)
_ASSET_FULL_ID_PATTERN = re.compile(
    r"[A-Z]{2,3}-[A-Z]{2}-\d{3,4}",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Query Cache
# ---------------------------------------------------------------------------

class _QueryCache:
    """Simple TTL cache for query results."""

    def __init__(self, ttl_seconds: int = 60, max_size: int = 100):
        self._cache: dict[str, tuple[float, SearchResult]] = {}
        self._ttl = ttl_seconds
        self._max_size = max_size

    def _make_key(self, query: SearchQuery) -> str:
        raw = f"{query.intent}|{'|'.join(query.normalized_terms)}|{'|'.join(query.extracted_ids)}|{query.filters}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, query: SearchQuery) -> Optional[SearchResult]:
        key = self._make_key(query)
        entry = self._cache.get(key)
        if entry and (time.time() - entry[0]) < self._ttl:
            return entry[1]
        if entry:
            del self._cache[key]
        return None

    def put(self, query: SearchQuery, result: SearchResult) -> None:
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]
        key = self._make_key(query)
        self._cache[key] = (time.time(), result)


# ---------------------------------------------------------------------------
# QueryEngine
# ---------------------------------------------------------------------------

class QueryEngine:
    """
    Pre-query intelligence layer. Normalizes natural language input,
    detects intent, expands synonyms, and executes ranked searches.
    """

    def __init__(self):
        self._cache = _QueryCache()

    # ------ Public API ------

    def build_query(self, raw_input: str) -> SearchQuery:
        """Parse raw user input into a structured SearchQuery."""
        text = raw_input.strip()
        if not text:
            return SearchQuery(intent=SearchIntent.auto, raw_input=raw_input)

        extracted_ids = self._extract_ids(text)
        filters = self._extract_filters(text)
        cleaned_terms = self._clean_terms(text, filters)
        expanded = self._expand_terms(cleaned_terms)
        intent = self._detect_intent(text, extracted_ids, filters, cleaned_terms)

        # Confidence heuristic
        confidence = 0.5
        if extracted_ids:
            confidence = 0.95
        elif filters:
            confidence = min(0.6 + 0.1 * len(filters), 0.9)
        if intent != SearchIntent.auto:
            confidence = max(confidence, 0.7)

        return SearchQuery(
            intent=intent,
            raw_input=raw_input,
            normalized_terms=cleaned_terms,
            filters=filters,
            extracted_ids=extracted_ids,
            expanded_terms=expanded,
            confidence=confidence,
        )

    async def execute_search(
        self,
        query: SearchQuery,
        eam_service: Any,
        limit: int = 10,
    ) -> SearchResult:
        """Execute the search against the EAM service and return ranked results."""
        cached = self._cache.get(query)
        if cached is not None:
            return cached

        t0 = time.time()
        items: list[ScoredItem] = []

        # 1) Direct ID lookups — but only when intent matches the ID type.
        # When user says "ESC-SR-001 open work orders", the asset ID should
        # NOT short-circuit to an asset lookup; we need the WO search path
        # which includes the asset ID as a filter term.
        for eid in query.extracted_ids:
            upper = eid.upper()
            # WO IDs always go through lookup
            if upper.startswith("WO-"):
                id_items = await self._lookup_by_id(eid, eam_service)
                items.extend(id_items)
            # Asset IDs only go through lookup if intent is asset (not work_order)
            elif query.intent != SearchIntent.work_order:
                id_items = await self._lookup_by_id(eid, eam_service)
                items.extend(id_items)

        # If exact ID matches found, skip broad search
        if items:
            result = SearchResult(
                items=items[:limit],
                total=len(items),
                query=query,
                search_time_ms=round((time.time() - t0) * 1000, 1),
            )
            self._cache.put(query, result)
            return result

        # 2) Intent-routed search
        if query.intent == SearchIntent.work_order:
            items.extend(await self._search_work_orders(query, eam_service))
        elif query.intent == SearchIntent.asset:
            items.extend(await self._search_assets(query, eam_service))
        elif query.intent == SearchIntent.location:
            items.extend(await self._search_locations(query, eam_service))
        elif query.intent == SearchIntent.eam_code:
            items.extend(await self._search_eam_codes(query, eam_service))
        elif query.intent == SearchIntent.knowledge:
            items.extend(await self._search_knowledge(query, eam_service))
        elif query.intent == SearchIntent.auto:
            items.extend(await self._search_auto(query, eam_service))

        # Deduplicate by item identity
        seen = set()
        unique_items = []
        for si in items:
            item_key = self._item_key(si)
            if item_key not in seen:
                seen.add(item_key)
                unique_items.append(si)

        # Sort by score descending
        unique_items.sort(key=lambda x: x.score, reverse=True)
        unique_items = unique_items[:limit]

        result = SearchResult(
            items=unique_items,
            total=len(unique_items),
            query=query,
            search_time_ms=round((time.time() - t0) * 1000, 1),
        )
        self._cache.put(query, result)
        return result

    @staticmethod
    def normalize_wo_id(raw: str) -> list[str]:
        """Try to normalize a raw string into valid WO-YYYY-NNNN formats."""
        raw = raw.strip()
        upper = raw.upper()
        # Already well-formed
        if _WO_FULL_ID_PATTERN.fullmatch(upper):
            return [upper]

        candidates = []
        m = _WO_ID_PATTERN.search(raw)
        if m:
            year, num = m.group(1), m.group(2)
            padded = num.zfill(4)
            candidates.append(f"WO-{year}-{padded}")
        else:
            digits = re.findall(r"\d+", raw)
            for d in digits:
                if len(d) >= 3:
                    padded = d.zfill(4)
                    for year in ["2025", "2026", "2024"]:
                        candidates.append(f"WO-{year}-{padded}")
        return candidates

    @staticmethod
    def normalize_asset_id(raw: str) -> Optional[str]:
        """Try to normalize a raw string into a valid XXX-YY-NNN asset ID."""
        raw = raw.strip().upper()
        if _ASSET_FULL_ID_PATTERN.fullmatch(raw):
            return raw
        m = _ASSET_ID_PATTERN.search(raw)
        if m:
            prefix, station_code, num = m.group(1), m.group(2), m.group(3)
            return f"{prefix}-{station_code}-{num.zfill(3)}"
        return None

    # ------ Private: Intent Detection ------

    def _detect_intent(
        self,
        text: str,
        extracted_ids: list[str],
        filters: dict,
        terms: list[str],
    ) -> SearchIntent:
        lower = text.lower()

        # Keyword sets (defined early so ID-based detection can check them)
        wo_keywords = {"work order", "work orders", "wo ", "wos", "workorder"}

        # ID-based detection
        for eid in extracted_ids:
            if eid.upper().startswith("WO-"):
                return SearchIntent.work_order
            if _ASSET_FULL_ID_PATTERN.fullmatch(eid.upper()):
                # If WO keywords also present, user wants work orders FOR this asset
                if any(kw in lower for kw in wo_keywords) or "status" in filters or "priority" in filters:
                    return SearchIntent.work_order
                return SearchIntent.asset

        # Keyword-based
        asset_keywords = {"asset", "equipment", "machine", "device", "unit"}
        location_keywords = {"location", "station", "where", "site"}
        code_keywords = {"eam code", "problem code", "fault code", "action code", "code"}
        knowledge_keywords = {"procedure", "manual", "guide", "safety", "protocol",
                              "how to", "troubleshoot", "repair guide", "knowledge",
                              "maintenance", "inspection", "checklist", "check",
                              "standard", "guidelines"}

        for kw in wo_keywords:
            if kw in lower:
                return SearchIntent.work_order
        for kw in knowledge_keywords:
            if kw in lower:
                return SearchIntent.knowledge
        for kw in code_keywords:
            if kw in lower:
                return SearchIntent.eam_code
        for kw in location_keywords:
            if kw in lower:
                return SearchIntent.location

        # Filter-based hints
        if "priority" in filters or "status" in filters:
            return SearchIntent.work_order
        if "asset_type" in filters:
            return SearchIntent.asset
        if "department" in filters and any(t in lower for t in asset_keywords):
            return SearchIntent.asset

        for kw in asset_keywords:
            if kw in lower:
                return SearchIntent.asset

        return SearchIntent.auto

    # ------ Private: Extraction ------

    def _extract_ids(self, text: str) -> list[str]:
        ids = []
        # Full WO IDs
        for m in _WO_FULL_ID_PATTERN.finditer(text):
            ids.append(m.group().upper())
        # Full asset IDs
        for m in _ASSET_FULL_ID_PATTERN.finditer(text):
            val = m.group().upper()
            if not val.startswith("WO-") and val not in ids:
                ids.append(val)
        # Partial WO IDs like "wo 10234" or "wo10234"
        if not ids:
            wo_partial = re.findall(r"(?:wo|work\s*order)\s*#?\s*(\d{3,5})", text, re.IGNORECASE)
            for num in wo_partial:
                for year in ["2025", "2026", "2024"]:
                    ids.append(f"WO-{year}-{num.zfill(4)}")
        return ids

    def _extract_filters(self, text: str) -> dict[str, str]:
        filters: dict[str, str] = {}
        lower = text.lower()
        tokens = lower.split()

        # Priority
        for token in tokens:
            if token in PRIORITY_ALIASES:
                filters["priority"] = PRIORITY_ALIASES[token]
                break

        # Status
        for token in tokens:
            if token in STATUS_ALIASES:
                filters["status"] = STATUS_ALIASES[token]
                break
        # Multi-word status
        for phrase, value in STATUS_ALIASES.items():
            if " " in phrase and phrase in lower:
                filters["status"] = value

        # Department — check multi-word first, then single tokens
        for phrase, dept in DEPARTMENT_ALIASES.items():
            if " " in phrase and phrase in lower:
                filters["department"] = dept
                break
        if "department" not in filters:
            for token in tokens:
                if token in DEPARTMENT_ALIASES:
                    filters["department"] = DEPARTMENT_ALIASES[token]
                    break

        # Asset type — check multi-word first, then single tokens
        for phrase, atype in ASSET_TYPE_ALIASES.items():
            if " " in phrase and phrase in lower:
                filters["asset_type"] = atype
                break
        if "asset_type" not in filters:
            for token in tokens:
                if token in ASSET_TYPE_ALIASES:
                    filters["asset_type"] = ASSET_TYPE_ALIASES[token]
                    break

        return filters

    def _clean_terms(self, text: str, filters: dict) -> list[str]:
        """Remove noise words, IDs, and pure filter tokens (not content words)."""
        # Remove detected IDs from text
        cleaned = _WO_FULL_ID_PATTERN.sub("", text)
        cleaned = _ASSET_FULL_ID_PATTERN.sub("", cleaned)
        cleaned = re.sub(r"(?:wo|work\s*order)\s*#?\s*\d{3,5}", "", cleaned, flags=re.IGNORECASE)

        tokens = re.findall(r"[a-zA-Z0-9]+", cleaned.lower())
        result = []

        # Only strip pure filter tokens — priority values and status keywords.
        # Do NOT strip department/asset_type words because they are also
        # meaningful content terms for knowledge base and asset searches
        # (e.g., "signal", "controller", "escalator" are search-relevant).
        strip_tokens = set()
        for alias, canonical in PRIORITY_ALIASES.items():
            if canonical == filters.get("priority"):
                strip_tokens.update(alias.lower().split())
        for alias, canonical in STATUS_ALIASES.items():
            if canonical == filters.get("status"):
                strip_tokens.update(alias.lower().split())

        for token in tokens:
            if token in NOISE_WORDS:
                continue
            if token in strip_tokens:
                continue
            if len(token) <= 1:
                continue
            result.append(token)
        return result

    def _expand_terms(self, terms: list[str]) -> list[str]:
        """Expand terms with synonyms and related EAM codes."""
        expanded = []
        for term in terms:
            if term in SYNONYM_MAP:
                entry = SYNONYM_MAP[term]
                for syn in entry["terms"]:
                    if syn not in terms and syn not in expanded:
                        expanded.append(syn)
                for code in entry["codes"]:
                    if code not in expanded:
                        expanded.append(code)
        return expanded

    # ------ Private: Search Execution ------

    async def _lookup_by_id(self, eid: str, eam) -> list[ScoredItem]:
        items = []
        upper = eid.upper()
        if upper.startswith("WO-"):
            wo = await self._get_work_order_by_id(upper, eam)
            if wo:
                items.append(ScoredItem(
                    item=wo, score=1.0, match_type="exact_id", entity_type="work_order"
                ))
        elif _ASSET_FULL_ID_PATTERN.fullmatch(upper):
            asset = await eam.get_asset(upper)
            if asset:
                items.append(ScoredItem(
                    item=asset, score=1.0, match_type="exact_id", entity_type="asset"
                ))
        return items

    async def _get_work_order_by_id(self, wo_id: str, eam) -> Any:
        """Try to get a single work order by ID using available methods."""
        # Try direct lookup if the method exists
        if hasattr(eam, "get_work_order"):
            result = await eam.get_work_order(wo_id)
            if result:
                return result
        # Fallback: search by WO ID text
        results = await eam.search_work_orders(q=wo_id)
        for wo in results:
            if wo.wo_id.upper() == wo_id.upper():
                return wo
        return None

    async def _search_work_orders(self, query: SearchQuery, eam) -> list[ScoredItem]:
        from models.schemas import WorkOrderStatus

        status = None
        if "status" in query.filters:
            try:
                status = WorkOrderStatus(query.filters["status"])
            except ValueError:
                pass

        # Build search text from normalized terms + any extracted asset IDs
        # Asset IDs are stripped from normalized_terms during cleaning, but
        # search_work_orders() matches q tokens against asset_id fields, so
        # we must re-include them for asset-scoped WO searches.
        search_parts = list(query.normalized_terms)
        for eid in query.extracted_ids:
            upper = eid.upper()
            if not upper.startswith("WO-") and _ASSET_FULL_ID_PATTERN.fullmatch(upper):
                search_parts.append(upper)
        search_text = " ".join(search_parts)

        results = await eam.search_work_orders(
            q=search_text,
            priority=query.filters.get("priority", ""),
            department=query.filters.get("department", ""),
            status=status,
            location=query.filters.get("location", ""),
        )

        items = []
        for wo in results:
            score = self._score_work_order(wo, query)
            items.append(ScoredItem(
                item=wo, score=score, match_type="search", entity_type="work_order"
            ))

        # If we have expanded terms and few results, try expanded search
        # IMPORTANT: preserve all filters from the original query
        if len(items) < 3 and query.expanded_terms:
            expanded_text = " ".join(query.expanded_terms)
            expanded_results = await eam.search_work_orders(
                q=expanded_text,
                priority=query.filters.get("priority", ""),
                department=query.filters.get("department", ""),
                status=status,
                location=query.filters.get("location", ""),
            )
            existing_ids = {si.item.wo_id for si in items}
            for wo in expanded_results:
                if wo.wo_id not in existing_ids:
                    items.append(ScoredItem(
                        item=wo, score=0.3, match_type="expanded", entity_type="work_order"
                    ))
        return items

    async def _search_assets(self, query: SearchQuery, eam) -> list[ScoredItem]:
        search_text = " ".join(query.normalized_terms)
        results = await eam.search_assets(
            query=search_text,
            department=query.filters.get("department", ""),
            station=query.filters.get("location", ""),
            asset_type=query.filters.get("asset_type", ""),
        )

        items = []
        for asset in results:
            score = self._score_asset(asset, query)
            items.append(ScoredItem(
                item=asset, score=score, match_type="search", entity_type="asset"
            ))

        if len(items) < 3 and query.expanded_terms:
            expanded_text = " ".join(query.expanded_terms)
            expanded_results = await eam.search_assets(query=expanded_text)
            existing_ids = {si.item.asset_id for si in items}
            for asset in expanded_results:
                if asset.asset_id not in existing_ids:
                    items.append(ScoredItem(
                        item=asset, score=0.3, match_type="expanded", entity_type="asset"
                    ))
        return items

    async def _search_locations(self, query: SearchQuery, eam) -> list[ScoredItem]:
        locations = await eam.get_locations()
        search_text = " ".join(query.normalized_terms).lower()
        items = []
        for loc in locations:
            station_lower = loc.get("station", "").lower()
            code_lower = loc.get("station_code", "").lower()
            if search_text and (search_text in station_lower or search_text in code_lower):
                items.append(ScoredItem(
                    item=loc, score=0.8, match_type="name", entity_type="location"
                ))
            elif not search_text:
                items.append(ScoredItem(
                    item=loc, score=0.5, match_type="search", entity_type="location"
                ))
        return items

    async def _search_eam_codes(self, query: SearchQuery, eam) -> list[ScoredItem]:
        codes = await eam.get_eam_codes(
            department=query.filters.get("department", ""),
            asset_type=query.filters.get("asset_type", ""),
        )
        search_text = " ".join(query.normalized_terms).lower()
        items = []
        for code in codes:
            if not search_text:
                items.append(ScoredItem(
                    item=code, score=0.5, match_type="search", entity_type="eam_code"
                ))
                continue
            searchable = f"{code.code} {code.label} {code.description}".lower()
            if any(t in searchable for t in query.normalized_terms):
                items.append(ScoredItem(
                    item=code, score=0.7, match_type="description", entity_type="eam_code"
                ))
            elif any(t in searchable for t in query.expanded_terms):
                items.append(ScoredItem(
                    item=code, score=0.4, match_type="expanded", entity_type="eam_code"
                ))
        return items

    async def _search_knowledge(self, query: SearchQuery, eam) -> list[ScoredItem]:
        search_text = " ".join(query.normalized_terms) if query.normalized_terms else "maintenance"
        results = await eam.search_knowledge_base(
            query=search_text,
            department=query.filters.get("department", ""),
            asset_type=query.filters.get("asset_type", ""),
        )
        items = []
        for entry in results:
            items.append(ScoredItem(
                item=entry, score=0.7, match_type="search", entity_type="knowledge"
            ))
        return items

    async def _search_auto(self, query: SearchQuery, eam) -> list[ScoredItem]:
        """Fan-out search across work orders, assets, and knowledge base."""
        wo_items = await self._search_work_orders(query, eam)
        asset_items = await self._search_assets(query, eam)
        kb_items = await self._search_knowledge(query, eam)
        # Slightly prefer assets in auto mode since technicians usually mean equipment
        for ai in asset_items:
            ai.score = min(ai.score + 0.05, 1.0)
        return wo_items + asset_items + kb_items

    # ------ Private: Scoring ------

    def _score_work_order(self, wo, query: SearchQuery) -> float:
        score = 0.5
        search_terms = query.normalized_terms
        wo_text = f"{wo.wo_id} {wo.description} {wo.asset_id} {wo.problem_code} {wo.fault_code}".lower()

        for term in search_terms:
            if term in wo.wo_id.lower():
                score = max(score, 0.9)
            elif term in wo.description.lower():
                score = max(score, 0.7)
            elif term in wo_text:
                score = max(score, 0.6)

        # Boost for filter matches
        if "priority" in query.filters and wo.priority.upper() == query.filters["priority"]:
            score += 0.1
        if "status" in query.filters and wo.status == query.filters["status"]:
            score += 0.1
        return min(score, 1.0)

    def _score_asset(self, asset, query: SearchQuery) -> float:
        score = 0.5
        search_terms = query.normalized_terms
        asset_text = f"{asset.asset_id} {asset.name} {asset.type} {asset.location.station}".lower()

        for term in search_terms:
            if term in asset.asset_id.lower():
                score = max(score, 0.9)
            elif term in asset.name.lower():
                score = max(score, 0.8)
            elif term in asset_text:
                score = max(score, 0.6)

        if "asset_type" in query.filters and asset.type == query.filters["asset_type"]:
            score += 0.1
        if "department" in query.filters and asset.department == query.filters["department"]:
            score += 0.1
        return min(score, 1.0)

    @staticmethod
    def _item_key(si: ScoredItem) -> str:
        item = si.item
        if hasattr(item, "wo_id"):
            return f"wo:{item.wo_id}"
        if hasattr(item, "asset_id"):
            return f"asset:{item.asset_id}"
        if hasattr(item, "doc_id"):
            return f"kb:{item.doc_id}"
        if hasattr(item, "code"):
            return f"code:{item.code}"
        if isinstance(item, dict):
            return f"loc:{item.get('station', '')}"
        return f"unknown:{id(item)}"
