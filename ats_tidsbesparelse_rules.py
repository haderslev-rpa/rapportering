from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from openpyxl import load_workbook
from openpyxl.utils.cell import range_boundaries
from ats_tidsbesparelse_config import ATS_TIDSBESPARELSE_CONFIG
from ats_tidsbesparelse_models import AtsRule

REQUIRED_COLUMNS = (
    "Aktiv", "Queue-navn", "Sharepoint navn", "Resultat", "States", "Matchtype",
    "Minutter pr. item", "Prioritet", "Beregningsmetode",
    "Faste minutter pr. måned", "Detailniveau", "Gyldig fra", "Gyldig til",
)
MATCH_TYPES = {"ANY", "ALL", "NO_STATE_FILTER"}
MATCH_ALIASES = {"EN AF":"ANY", "ÉN AF":"ANY", "ALLE STATES":"ALL", "INGEN STATES":"NO_STATE_FILTER"}
METHODS = {"PR_ITEM", "FAST_PR_MÅNED"}


def read_rules(file_bytes: bytes) -> list[AtsRule]:
    try:
        workbook = load_workbook(BytesIO(file_bytes), data_only=False, read_only=False)
    except Exception as error:
        raise ValueError("Regelprojektmappen kunne ikke åbnes.") from error
    sheet_name = ATS_TIDSBESPARELSE_CONFIG["sheet_name"]
    table_name = ATS_TIDSBESPARELSE_CONFIG["table_name"]
    if sheet_name not in workbook.sheetnames:
        raise ValueError(f"Arket {sheet_name!r} mangler.")
    sheet = workbook[sheet_name]
    if table_name not in sheet.tables:
        raise ValueError(f"Tabellen {table_name!r} mangler på arket {sheet_name!r}.")
    table = sheet.tables[table_name]
    min_col, min_row, max_col, max_row = range_boundaries(table.ref)
    headers = [str(sheet.cell(min_row, col).value or "").strip() for col in range(min_col, max_col + 1)]
    missing = [name for name in REQUIRED_COLUMNS if name not in headers]
    if missing:
        raise ValueError(f"ATS_ReglerTable mangler obligatoriske kolonner: {missing}")
    rules=[]
    for row_no in range(min_row + 1, max_row + 1):
        values={headers[i]: sheet.cell(row_no, min_col+i).value for i in range(len(headers))}
        if not _yes(values["Aktiv"]):
            continue
        queue=_text(values["Queue-navn"])
        result=_text(values["Resultat"])
        if not queue:
            raise ValueError(f"Aktiv regel på Excel-række {row_no} mangler Queue-navn.")
        method=_text(values["Beregningsmetode"]).upper()
        match=_text(values["Matchtype"]).upper()
        match=MATCH_ALIASES.get(match, match)
        stats=tuple(line.strip() for line in str(values["States"] or "").splitlines() if line.strip())
        if method not in METHODS:
            raise ValueError(f"Excel-række {row_no}: ukendt Beregningsmetode {method!r}.")
        if match not in MATCH_TYPES:
            raise ValueError(f"Excel-række {row_no}: ukendt Matchtype {match!r}.")
        if match != "NO_STATE_FILTER" and not stats:
            raise ValueError(f"Excel-række {row_no}: {match} kræver mindst én værdi i States.")
        if match == "NO_STATE_FILTER" and stats:
            raise ValueError(f"Excel-række {row_no}: NO_STATE_FILTER må ikke have States.")
        if not result and method != "FAST_PR_MÅNED":
            raise ValueError(f"Excel-række {row_no}: Resultat mangler.")
        valid_from=_date(values["Gyldig fra"], row_no, "Gyldig fra")
        valid_to=_date(values["Gyldig til"], row_no, "Gyldig til")
        if valid_from >= valid_to:
            raise ValueError(f"Excel-række {row_no}: Gyldig fra skal ligge før Gyldig til.")
        minutes=_decimal(values["Minutter pr. item"], row_no, "Minutter pr. item")
        fixed=_decimal(values["Faste minutter pr. måned"], row_no, "Faste minutter pr. måned")
        if method == "PR_ITEM" and minutes <= 0:
            raise ValueError(f"Excel-række {row_no}: PR_ITEM kræver Minutter pr. item over 0.")
        if method == "FAST_PR_MÅNED" and fixed <= 0:
            raise ValueError(f"Excel-række {row_no}: FAST_PR_MÅNED kræver Faste minutter pr. måned over 0.")
        rules.append(AtsRule(row_no, queue, _text(values["Sharepoint navn"]), result, stats, match,
                             minutes, _integer(values["Prioritet"], row_no), method, fixed,
                             _text(values["Detailniveau"]) or "SUM_RESULTAT", valid_from, valid_to))
    if not rules:
        raise ValueError("ATS_ReglerTable indeholder ingen aktive regler.")
    _validate_fixed_consistency(rules)
    return sorted(rules, key=lambda r:(r.queue_name.casefold(), r.priority, r.row_number))


def _validate_fixed_consistency(rules: list[AtsRule]) -> None:
    groups=defaultdict(list)
    for rule in rules:
        if rule.calculation_method == "FAST_PR_MÅNED":
            groups[rule.queue_name.casefold()].append(rule)
    for queue, queue_rules in groups.items():
        for i,left in enumerate(queue_rules):
            for right in queue_rules[i+1:]:
                overlaps=max(left.valid_from,right.valid_from) < min(left.valid_to,right.valid_to)
                if overlaps and (left.fixed_minutes_per_month != right.fixed_minutes_per_month or left.detail_level != right.detail_level):
                    raise ValueError(f"Queue {left.queue_name!r} har modstridende FAST_PR_MÅNED-opsætning på række {left.row_number} og {right.row_number}.")

def _text(value) -> str: return str(value or "").strip()
def _yes(value) -> bool: return _text(value).casefold() in {"ja","yes","true","1","x"}
def _decimal(value,row,field):
    try: return Decimal(str(value or 0).replace(",","."))
    except InvalidOperation as error: raise ValueError(f"Excel-række {row}: {field} er ugyldig.") from error
def _integer(value,row):
    try: return int(value)
    except (TypeError,ValueError) as error: raise ValueError(f"Excel-række {row}: Prioritet skal være et heltal.") from error
def _date(value,row,field):
    if isinstance(value,datetime): return value.date()
    if isinstance(value,date): return value
    for fmt in ("%d-%m-%Y","%Y-%m-%d","%d/%m/%Y"):
        try: return datetime.strptime(_text(value),fmt).date()
        except ValueError: pass
    raise ValueError(f"Excel-række {row}: {field} er ugyldig.")
