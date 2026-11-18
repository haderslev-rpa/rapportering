from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import load_workbook
from openpyxl.utils.cell import range_boundaries

from ats_tidsbesparelse_config import (
    ATS_TIDSBESPARELSE_CONFIG,
)
from ats_tidsbesparelse_models import (
    AtsRule,
)


REQUIRED_COLUMNS = (
    "Aktiv",
    "Queue-navn",
    "Sharepoint navn",
    "Resultat",
    "States",
    "Matchtype",
    "Minutter pr. item",
    "Prioritet",
    "Beregningsmetode",
    "Faste minutter pr. måned",
    "Rapportvisning",
    "Gyldig fra",
    "Gyldig til",
)

MATCH_TYPES = {
    "ANY",
    "ALL",
    "NO_STATE_FILTER",
}

MATCH_ALIASES = {
    "EN AF": "ANY",
    "ÉN AF": "ANY",
    "ALLE STATES": "ALL",
    "INGEN STATES": "NO_STATE_FILTER",
}

CALCULATION_METHODS = {
    "PR_ITEM",
    "FAST_PR_MÅNED",
}

REPORT_VIEWS = {
    "RESULTAT",
    "REGEL_TAGS",
    "RÅ_TAGS",
}


def read_rules(
    file_bytes: bytes,
) -> list[AtsRule]:
    """
    Læser og validerer aktive regler fra ATS_ReglerTable.

    Excel-kolonnen Rapportvisning gemmes fortsat i modellens
    detail_level-felt. Det bevarer kompatibiliteten med
    rapportens eksisterende outputkolonne Detailniveau.
    """
    try:
        workbook = load_workbook(
            BytesIO(file_bytes),
            data_only=False,
            read_only=False,
        )
    except Exception as error:
        raise ValueError(
            "Regelprojektmappen kunne ikke åbnes."
        ) from error

    sheet_name = ATS_TIDSBESPARELSE_CONFIG[
        "sheet_name"
    ]
    table_name = ATS_TIDSBESPARELSE_CONFIG[
        "table_name"
    ]

    if sheet_name not in workbook.sheetnames:
        raise ValueError(
            f"Arket {sheet_name!r} mangler."
        )

    sheet = workbook[sheet_name]

    if table_name not in sheet.tables:
        raise ValueError(
            f"Tabellen {table_name!r} mangler "
            f"på arket {sheet_name!r}."
        )

    table = sheet.tables[table_name]

    (
        min_column,
        min_row,
        max_column,
        max_row,
    ) = range_boundaries(
        table.ref
    )

    headers = [
        str(
            sheet.cell(
                row=min_row,
                column=column_number,
            ).value
            or ""
        ).strip()
        for column_number in range(
            min_column,
            max_column + 1,
        )
    ]

    missing_columns = [
        column_name
        for column_name in REQUIRED_COLUMNS
        if column_name not in headers
    ]

    if missing_columns:
        raise ValueError(
            "ATS_ReglerTable mangler obligatoriske "
            f"kolonner: {missing_columns}"
        )

    rules: list[AtsRule] = []

    for row_number in range(
        min_row + 1,
        max_row + 1,
    ):
        values = {
            headers[index]: sheet.cell(
                row=row_number,
                column=min_column + index,
            ).value
            for index in range(
                len(headers)
            )
        }

        if not _is_yes(
            values["Aktiv"]
        ):
            continue

        rule = _build_rule(
            values=values,
            row_number=row_number,
        )

        rules.append(
            rule
        )

    if not rules:
        raise ValueError(
            "ATS_ReglerTable indeholder ingen "
            "aktive regler."
        )

    _validate_fixed_month_rules(
        rules
    )

    return sorted(
        rules,
        key=lambda rule: (
            rule.queue_name.casefold(),
            rule.priority,
            rule.row_number,
        ),
    )


def _build_rule(
    *,
    values: dict,
    row_number: int,
) -> AtsRule:
    """
    Bygger og validerer én aktiv Excel-regel.
    """
    queue_name = _as_text(
        values["Queue-navn"]
    )

    if not queue_name:
        raise ValueError(
            f"Excel-række {row_number}: "
            "Aktiv regel mangler Queue-navn."
        )

    result = _as_text(
        values["Resultat"]
    )

    match_type = _as_text(
        values["Matchtype"]
    ).upper()

    match_type = MATCH_ALIASES.get(
        match_type,
        match_type,
    )

    if match_type not in MATCH_TYPES:
        raise ValueError(
            f"Excel-række {row_number}: "
            f"Ukendt Matchtype {match_type!r}."
        )

    calculation_method = _as_text(
        values["Beregningsmetode"]
    ).upper()

    if (
        calculation_method
        not in CALCULATION_METHODS
    ):
        raise ValueError(
            f"Excel-række {row_number}: "
            "Ukendt Beregningsmetode "
            f"{calculation_method!r}."
        )

    report_view = _as_text(
        values["Rapportvisning"]
    ).upper()

    if report_view not in REPORT_VIEWS:
        raise ValueError(
            f"Excel-række {row_number}: "
            f"Ukendt Rapportvisning {report_view!r}. "
            "Tilladte værdier er RESULTAT, "
            "REGEL_TAGS og RÅ_TAGS."
        )

    stats = tuple(
        line.strip()
        for line in str(
            values["States"]
            or ""
        ).splitlines()
        if line.strip()
    )

    minutes_per_item = _as_decimal(
        value=values["Minutter pr. item"],
        row_number=row_number,
        field_name="Minutter pr. item",
    )

    fixed_minutes_per_month = _as_decimal(
        value=values[
            "Faste minutter pr. måned"
        ],
        row_number=row_number,
        field_name=(
            "Faste minutter pr. måned"
        ),
    )

    if minutes_per_item < 0:
        raise ValueError(
            f"Excel-række {row_number}: "
            "Minutter pr. item må ikke være negativ."
        )

    if fixed_minutes_per_month < 0:
        raise ValueError(
            f"Excel-række {row_number}: "
            "Faste minutter pr. måned må ikke "
            "være negativ."
        )

    if (
        minutes_per_item > 0
        and fixed_minutes_per_month > 0
    ):
        raise ValueError(
            f"Excel-række {row_number}: "
            "Rækken har både Minutter pr. item "
            "og Faste minutter pr. måned. "
            "Kun ét af felterne må have en værdi "
            "over 0."
        )

    if (
        match_type != "NO_STATE_FILTER"
        and not stats
    ):
        raise ValueError(
            f"Excel-række {row_number}: "
            f"{match_type} kræver mindst én "
            "værdi i States."
        )

    if (
        match_type == "NO_STATE_FILTER"
        and stats
    ):
        raise ValueError(
            f"Excel-række {row_number}: "
            "NO_STATE_FILTER må ikke have States."
        )

    if calculation_method == "PR_ITEM":
        if not result:
            raise ValueError(
                f"Excel-række {row_number}: "
                "PR_ITEM kræver et Resultat."
            )

        if fixed_minutes_per_month != 0:
            raise ValueError(
                f"Excel-række {row_number}: "
                "PR_ITEM må ikke have Faste "
                "minutter pr. måned."
            )

    if calculation_method == "FAST_PR_MÅNED":
        if minutes_per_item != 0:
            raise ValueError(
                f"Excel-række {row_number}: "
                "FAST_PR_MÅNED må ikke have "
                "Minutter pr. item."
            )

        if fixed_minutes_per_month <= 0:
            raise ValueError(
                f"Excel-række {row_number}: "
                "FAST_PR_MÅNED kræver Faste "
                "minutter pr. måned over 0."
            )

        if stats:
            raise ValueError(
                f"Excel-række {row_number}: "
                "FAST_PR_MÅNED må ikke have States."
            )

        if match_type != "NO_STATE_FILTER":
            raise ValueError(
                f"Excel-række {row_number}: "
                "FAST_PR_MÅNED skal have "
                "Matchtype NO_STATE_FILTER."
            )

        if report_view == "RÅ_TAGS":
            raise ValueError(
                f"Excel-række {row_number}: "
                "FAST_PR_MÅNED kan ikke bruge "
                "Rapportvisning RÅ_TAGS, fordi "
                "månedsrækker ikke klassificerer "
                "enkelte workitems."
            )

    valid_from = _as_date(
        value=values["Gyldig fra"],
        row_number=row_number,
        field_name="Gyldig fra",
    )

    valid_to = _as_date(
        value=values["Gyldig til"],
        row_number=row_number,
        field_name="Gyldig til",
    )

    if valid_from >= valid_to:
        raise ValueError(
            f"Excel-række {row_number}: "
            "Gyldig fra skal ligge før Gyldig til."
        )

    return AtsRule(
        row_number=row_number,
        queue_name=queue_name,
        sharepoint_name=_as_text(
            values["Sharepoint navn"]
        ),
        result=result,
        stats=stats,
        match_type=match_type,
        minutes_per_item=minutes_per_item,
        priority=_as_integer(
            value=values["Prioritet"],
            row_number=row_number,
        ),
        calculation_method=calculation_method,
        fixed_minutes_per_month=(
            fixed_minutes_per_month
        ),
        # Feltet hedder detail_level i datamodellen,
        # men indeholder Excel-kolonnen Rapportvisning.
        detail_level=report_view,
        valid_from=valid_from,
        valid_to=valid_to,
    )


def _validate_fixed_month_rules(
    rules: list[AtsRule],
) -> None:
    """
    Tillader højst én FAST_PR_MÅNED-regel pr. queue
    i en given gyldighedsperiode.
    """
    rules_by_queue: dict[
        str,
        list[AtsRule],
    ] = defaultdict(list)

    for rule in rules:
        if (
            rule.calculation_method
            == "FAST_PR_MÅNED"
        ):
            rules_by_queue[
                rule.queue_name.casefold()
            ].append(
                rule
            )

    for queue_rules in rules_by_queue.values():
        for rule_index, left_rule in enumerate(
            queue_rules
        ):
            for right_rule in queue_rules[
                rule_index + 1:
            ]:
                periods_overlap = (
                    max(
                        left_rule.valid_from,
                        right_rule.valid_from,
                    )
                    < min(
                        left_rule.valid_to,
                        right_rule.valid_to,
                    )
                )

                if periods_overlap:
                    raise ValueError(
                        "Der findes flere aktive "
                        "FAST_PR_MÅNED-regler for "
                        f"queue {left_rule.queue_name!r} "
                        "med overlappende gyldighed. "
                        "Kontrollér Excel-række "
                        f"{left_rule.row_number} og "
                        f"{right_rule.row_number}."
                    )


def _as_text(
    value,
) -> str:
    return str(
        value
        or ""
    ).strip()


def _is_yes(
    value,
) -> bool:
    return _as_text(
        value
    ).casefold() in {
        "ja",
        "yes",
        "true",
        "1",
        "x",
    }


def _as_decimal(
    *,
    value,
    row_number: int,
    field_name: str,
) -> Decimal:
    if value in (
        None,
        "",
    ):
        return Decimal("0")

    try:
        return Decimal(
            str(value).replace(
                ",",
                ".",
            )
        )
    except InvalidOperation as error:
        raise ValueError(
            f"Excel-række {row_number}: "
            f"{field_name} er ugyldig."
        ) from error


def _as_integer(
    *,
    value,
    row_number: int,
) -> int:
    try:
        return int(
            value
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            f"Excel-række {row_number}: "
            "Prioritet skal være et heltal."
        ) from error


def _as_date(
    *,
    value,
    row_number: int,
    field_name: str,
) -> date:
    if isinstance(
        value,
        datetime,
    ):
        return value.date()

    if isinstance(
        value,
        date,
    ):
        return value

    text = _as_text(
        value
    )

    for date_format in (
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(
                text,
                date_format,
            ).date()
        except ValueError:
            pass

    raise ValueError(
        f"Excel-række {row_number}: "
        f"{field_name} er ugyldig."
    )