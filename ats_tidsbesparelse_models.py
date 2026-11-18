from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

@dataclass(frozen=True)
class AtsRule:
    row_number: int
    queue_name: str
    sharepoint_name: str
    result: str
    stats: tuple[str, ...]
    match_type: str
    minutes_per_item: Decimal
    priority: int
    calculation_method: str
    fixed_minutes_per_month: Decimal
    detail_level: str
    valid_from: date
    valid_to: date

    @property
    def technical_id(self) -> str:
        safe = "".join(ch if ch.isalnum() else "_" for ch in self.queue_name.casefold()).strip("_")
        return f"ATS_{safe}_{self.priority}_{self.row_number}"

@dataclass(frozen=True)
class ClassifiedItem:
    item_id: int
    queue_name: str
    completed_at: datetime
    month: date
    raw_stats: tuple[str, ...]
    matched_stats: tuple[str, ...]
    rule: AtsRule | None

Row = dict[str, Any]
