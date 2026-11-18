# integration_behandel.py
# Dette modul holder tidsbesparelse adskilt fra eksisterende rapporteringsflow.

from __future__ import annotations

from typing import Any, Iterable

from tidsbesparelse import beregn_tidsbesparelse, summer_tidsbesparelse


def tilfoej_tidsbesparelse_til_rapport(
    rapport_rows: list[dict[str, Any]],
    workitems: Iterable[Any],
    *,
    periode_start=None,
    periode_slut=None,
) -> dict[str, float]:
    beregnede_rows = beregn_tidsbesparelse(
        workitems,
        periode_start=periode_start,
        periode_slut=periode_slut,
    )
    rapport_rows.extend(beregnede_rows)
    return summer_tidsbesparelse(beregnede_rows)
