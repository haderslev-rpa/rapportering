# ats_tidsbesparelse.py

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from typing import Any, Iterable

from openpyxl import load_workbook
from q_sharepoint_api.sp_client import get_client

from configuration import (
    TIDSBESPARELSE_CACHE_SECONDS,
    TIDSBESPARELSE_FILE_PATH,
    TIDSBESPARELSE_SHEET_NAME,
    TIDSBESPARELSE_SITE_NAME,
    TIDSBESPARELSE_TABLE_NAME,
)

logger = logging.getLogger(__name__)

_CACHE: tuple[float, list["Tidsbesparelsesregel"]] | None = None


@dataclass(frozen=True)
class Tidsbesparelsesregel:
    aktiv: bool
    queue_navn: str
    sharepoint_navn: str | None
    resultat: str | None
    states: tuple[str, ...]
    matchtype: str
    minutter_pr_item: float
    prioritet: int
    beregningsmetode: str
    faste_minutter_pr_maaned: float
    detailniveau: str | None
    gyldig_fra: date | None
    gyldig_til: date | None


def hent_regler(*, force_refresh: bool = False) -> list[Tidsbesparelsesregel]:
    global _CACHE
    now = time.monotonic()
    if not force_refresh and _CACHE and now - _CACHE[0] < TIDSBESPARELSE_CACHE_SECONDS:
        return list(_CACHE[1])

    client = get_client()
    site_id = client.get_site_id(TIDSBESPARELSE_SITE_NAME)
    download = client.download_file_to_memory_by_path(
        site_id=site_id,
        file_path=TIDSBESPARELSE_FILE_PATH,
    )
    file_bytes = _extract_file_bytes(download)
    regler = _laes_regler_fra_excel(file_bytes)
    _CACHE = (now, regler)
    logger.info("Indlæste %s aktive tidsbesparelsesregler", len(regler))
    return list(regler)


def beregn_tidsbesparelse(
    workitems: Iterable[Any],
    *,
    periode_start: date | datetime | None = None,
    periode_slut: date | datetime | None = None,
) -> list[dict[str, Any]]:
    regler = hent_regler()
    start = _as_date(periode_start)
    slut = _as_date(periode_slut)
    tællere: dict[tuple[str, int], int] = {}
    resultater: list[dict[str, Any]] = []

    for item in workitems:
        item_data = _item_to_dict(item)
        queue_name = str(item_data.get("queue_name") or "").strip()
        regel = _find_regel(regler, queue_name, item_data, start, slut)
        if not regel:
            continue

        nøgle = (regel.queue_navn.casefold(), regel.prioritet)
        tællere[nøgle] = tællere.get(nøgle, 0) + 1
        resultater.append(
            {
                "workitem_id": item_data.get("id"),
                "reference": item_data.get("reference"),
                "queue_name": queue_name,
                "resultat": regel.resultat,
                "minutter_sparet": regel.minutter_pr_item,
                "regel_prioritet": regel.prioritet,
            }
        )

    for regel in regler:
        if regel.beregningsmetode.casefold() not in {"fast", "fast pr. måned", "faste minutter pr. måned"}:
            continue
        if regel.faste_minutter_pr_maaned <= 0:
            continue
        måneder = _antal_maaneder(start, slut)
        resultater.append(
            {
                "workitem_id": None,
                "reference": None,
                "queue_name": regel.queue_navn,
                "resultat": regel.resultat,
                "minutter_sparet": regel.faste_minutter_pr_maaned * måneder,
                "regel_prioritet": regel.prioritet,
            }
        )

    return resultater


def summer_tidsbesparelse(resultater: Iterable[dict[str, Any]]) -> dict[str, float]:
    minutter = sum(float(row.get("minutter_sparet") or 0) for row in resultater)
    return {"minutter": minutter, "timer": minutter / 60, "arbejdsdage": minutter / 60 / 7.4}


def _laes_regler_fra_excel(file_bytes: bytes) -> list[Tidsbesparelsesregel]:
    workbook = load_workbook(BytesIO(file_bytes), read_only=False, data_only=True)
    try:
        if TIDSBESPARELSE_SHEET_NAME not in workbook.sheetnames:
            raise ValueError(f"Arket {TIDSBESPARELSE_SHEET_NAME!r} findes ikke")
        sheet = workbook[TIDSBESPARELSE_SHEET_NAME]
        table = sheet.tables.get(TIDSBESPARELSE_TABLE_NAME)
        if table is None:
            raise ValueError(f"Tabellen {TIDSBESPARELSE_TABLE_NAME!r} findes ikke")

        rows = sheet[table.ref]
        headers = [str(cell.value or "").strip() for cell in rows[0]]
        regler: list[Tidsbesparelsesregel] = []
        for excel_row in rows[1:]:
            row = dict(zip(headers, (cell.value for cell in excel_row)))
            if not _as_bool(row.get("Aktiv")):
                continue
            queue_navn = _as_text(row.get("Queue-navn"))
            if not queue_navn:
                continue
            regler.append(
                Tidsbesparelsesregel(
                    aktiv=True,
                    queue_navn=queue_navn,
                    sharepoint_navn=_as_text(row.get("Sharepoint navn")),
                    resultat=_as_text(row.get("Resultat")),
                    states=_as_lines(row.get("States (én pr. linje)")),
                    matchtype=(_as_text(row.get("Matchtype")) or "Alle").strip(),
                    minutter_pr_item=_as_float(row.get("Minutter pr. item")),
                    prioritet=_as_int(row.get("Prioritet"), default=999),
                    beregningsmetode=(_as_text(row.get("Beregningsmetode")) or "Pr. item").strip(),
                    faste_minutter_pr_maaned=_as_float(row.get("Faste minutter pr. måned")),
                    detailniveau=_as_text(row.get("Detailniveau")),
                    gyldig_fra=_as_date(row.get("Gyldig fra")),
                    gyldig_til=_as_date(row.get("Gyldig til")),
                )
            )
        return sorted(regler, key=lambda rule: rule.prioritet)
    finally:
        workbook.close()


def _find_regel(regler, queue_name, item_data, start, slut):
    item_states = {str(state).strip().casefold() for state in item_data.get("state", [])}
    for regel in regler:
        if regel.queue_navn.casefold() != queue_name.casefold():
            continue
        if regel.gyldig_fra and slut and regel.gyldig_fra > slut:
            continue
        if regel.gyldig_til and start and regel.gyldig_til < start:
            continue
        wanted = {state.casefold() for state in regel.states}
        matchtype = regel.matchtype.casefold()
        if not wanted or matchtype in {"alle", "all", "ingen states"}:
            return regel
        if matchtype in {"en af", "én af", "any"} and wanted & item_states:
            return regel
        if matchtype in {"alle states", "all states"} and wanted <= item_states:
            return regel
        if matchtype in {"ingen", "none"} and not wanted & item_states:
            return regel
    return None


def _extract_file_bytes(download: Any) -> bytes:
    if isinstance(download, bytes):
        return download
    if isinstance(download, dict):
        for key in ("file_bytes", "bytes", "content"):
            value = download.get(key)
            if isinstance(value, bytes):
                return value
    if isinstance(download, tuple):
        for value in download:
            if isinstance(value, bytes):
                return value
    raise TypeError("SharePoint-download indeholdt ikke fil-bytes")


def _item_to_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    return {
        "id": getattr(item, "id", None),
        "reference": getattr(item, "reference", None),
        "queue_name": getattr(item, "queue_name", None),
        "state": (getattr(item, "data", None) or {}).get("state", []),
    }


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "ja", "yes", "x"}


def _as_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _as_lines(value: Any) -> tuple[str, ...]:
    return tuple(line.strip() for line in str(value or "").replace(";", "\n").splitlines() if line.strip())


def _as_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    return float(str(value).replace(",", "."))


def _as_int(value: Any, *, default: int) -> int:
    if value in (None, ""):
        return default
    return int(float(str(value).replace(",", ".")))


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Ugyldig dato: {value!r}")


def _antal_maaneder(start: date | None, slut: date | None) -> int:
    if not start or not slut:
        return 1
    return max(1, (slut.year - start.year) * 12 + slut.month - start.month + 1)
