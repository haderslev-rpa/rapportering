from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any


@dataclass(
    frozen=True
)
class AtsRule:
    """
    Én aktiv regel fra ATS_ReglerTable.

    row_number:
        Excel-rækken, hvor reglen blev fundet.

    detail_level:
        Indeholder værdien fra Excel-kolonnen
        Rapportvisning:

            RESULTAT
            REGEL_TAGS
            RÅ_TAGS
    """

    row_number: int
    queue_name: str
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
    def technical_id(
        self,
    ) -> str:
        """
        Opretter rapportens tekniske regel-ID.

        Eksempel:

            ATS_adviser_vedr_arbejdsskader_10_6
        """
        safe_queue_name = "".join(
            character
            if character.isalnum()
            else "_"
            for character
            in self.queue_name.casefold()
        ).strip("_")

        return (
            f"ATS_{safe_queue_name}_"
            f"{self.priority}_"
            f"{self.row_number}"
        )


@dataclass(
    frozen=True
)
class ClassifiedItem:
    """
    Ét completed workitem efter klassificering.
    """

    item_id: int
    queue_name: str
    completed_at: datetime
    month: date
    raw_stats: tuple[str, ...]
    matched_stats: tuple[str, ...]
    rule: AtsRule | None


Row = dict[str, Any]