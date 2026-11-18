from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal

from ats_tidsbesparelse_models import (
    AtsRule,
    ClassifiedItem,
    Row,
)


# Fjerner kun et afsluttende dansk dato- og klokkeslæt.
#
# Eksempel:
#
#     2.0 Advis færdiggjort 03-08-2026 09:02:05
#
# bliver:
#
#     2.0 Advis færdiggjort
#
TRAILING_TIMESTAMP_PATTERN = re.compile(
    r"\s+"
    r"\d{2}-\d{2}-\d{4}"
    r"\s+"
    r"\d{2}:\d{2}:\d{2}"
    r"\s*$"
)


def aggregate_items(
    items: list[ClassifiedItem],
    rules: list[AtsRule],
) -> list[Row]:
    """
    Samler workitems efter reglenes Rapportvisning.

    RESULTAT:
        Grupperer efter måned, queue og regel.
        Ingen tags vises.

    REGEL_TAGS:
        Grupperer efter måned, queue og regel.
        Matchende tags viser Excel-reglens States.
        Rå tags er tomme.

    RÅ_TAGS:
        Grupperer efter måned, queue, regel og den
        normaliserede kombination af rå tags.
        Både regel-tags og rå tags vises.

    NO_MATCH:
        Grupperer kun efter måned og queue.
        Ingen tags vises.
    """
    grouped_items: dict[
        tuple,
        list[ClassifiedItem],
    ] = defaultdict(list)

    for item in items:
        rule = item.rule

        if rule is None:
            group_key = (
                item.month,
                item.queue_name.casefold(),
                "NO_MATCH",
            )

        elif rule.detail_level == "RÅ_TAGS":
            normalized_raw_stats = (
                _normalize_raw_stats(
                    item.raw_stats
                )
            )

            group_key = (
                item.month,
                item.queue_name.casefold(),
                rule.technical_id,
                normalized_raw_stats,
            )

        else:
            # RESULTAT og REGEL_TAGS samles på reglen.
            group_key = (
                item.month,
                item.queue_name.casefold(),
                rule.technical_id,
            )

        grouped_items[
            group_key
        ].append(
            item
        )

    rows: list[Row] = []

    for grouped_items_for_row in (
        grouped_items.values()
    ):
        rows.append(
            _create_item_row(
                grouped_items_for_row
            )
        )

    rows.extend(
        _create_fixed_month_rows(
            items=items,
            rules=rules,
        )
    )

    return sorted(
        rows,
        key=lambda row: (
            row["Måned"],
            row["Queue Name"].casefold(),
            row["Resultat"].casefold(),
            row["Matchregel-ID"],
            row["Rå tags"],
        ),
    )


def _create_item_row(
    grouped_items: list[ClassifiedItem],
) -> Row:
    """
    Opretter én opsummeret rapportlinje.
    """
    first_item = grouped_items[0]
    rule = first_item.rule
    item_count = len(
        grouped_items
    )

    if rule is None:
        # NO_MATCH har ingen Excel-regel, som udtrykkeligt
        # tillader visning af rå data.
        return _create_row(
            month=first_item.month,
            queue_name=first_item.queue_name,
            result="Ingen matchende regel",
            rule_id="INGEN_MATCH",
            match_type="NO_MATCH",
            matching_stats="",
            raw_stats="",
            item_count=item_count,
            minutes_per_item=Decimal("0"),
            fixed_minutes_per_month=Decimal("0"),
            saved_minutes=Decimal("0"),
            report_view="RESULTAT",
        )

    if rule.detail_level == "RESULTAT":
        matching_stats = ""
        raw_stats = ""

    elif rule.detail_level == "REGEL_TAGS":
        matching_stats = _join_unique(
            configured_stat
            for item in grouped_items
            for configured_stat
            in item.matched_stats
        )
        raw_stats = ""

    elif rule.detail_level == "RÅ_TAGS":
        matching_stats = _join_unique(
            configured_stat
            for item in grouped_items
            for configured_stat
            in item.matched_stats
        )

        raw_stats = _join_unique(
            raw_stat
            for item in grouped_items
            for raw_stat in _normalize_raw_stats(
                item.raw_stats
            )
        )

    else:
        raise ValueError(
            "Ukendt Rapportvisning i klassificeret "
            f"regel: {rule.detail_level!r}"
        )

    saved_minutes = (
        rule.minutes_per_item
        * item_count
    )

    return _create_row(
        month=first_item.month,
        queue_name=first_item.queue_name,
        result=(
            rule.result
            or "Resultat"
        ),
        rule_id=rule.technical_id,
        match_type=rule.match_type,
        matching_stats=matching_stats,
        raw_stats=raw_stats,
        item_count=item_count,
        minutes_per_item=(
            rule.minutes_per_item
        ),
        fixed_minutes_per_month=Decimal("0"),
        saved_minutes=saved_minutes,
        report_view=rule.detail_level,
    )


def _create_fixed_month_rows(
    *,
    items: list[ClassifiedItem],
    rules: list[AtsRule],
) -> list[Row]:
    """
    Opretter højst én FAST_PR_MÅNED-række pr.
    queue og måned med completed aktivitet.
    """
    active_queue_months = {
        (
            item.queue_name.casefold(),
            item.queue_name,
            item.month,
        )
        for item in items
    }

    fixed_rules_by_queue: dict[
        str,
        list[AtsRule],
    ] = defaultdict(list)

    for rule in rules:
        if (
            rule.calculation_method
            != "FAST_PR_MÅNED"
        ):
            continue

        fixed_rules_by_queue[
            rule.queue_name.casefold()
        ].append(
            rule
        )

    fixed_rows: list[Row] = []

    for (
        queue_key,
        queue_name,
        month,
    ) in sorted(
        active_queue_months,
        key=lambda value: (
            value[2],
            value[1].casefold(),
        ),
    ):
        applicable_rules = [
            rule
            for rule
            in fixed_rules_by_queue.get(
                queue_key,
                [],
            )
            if (
                rule.valid_from
                <= month
                < rule.valid_to
            )
        ]

        if not applicable_rules:
            continue

        if len(
            applicable_rules
        ) > 1:
            excel_rows = [
                rule.row_number
                for rule in applicable_rules
            ]

            raise RuntimeError(
                "Der blev fundet flere gyldige "
                "FAST_PR_MÅNED-regler for "
                f"queue {queue_name!r} og "
                f"måned {month:%d-%m-%Y}. "
                f"Excel-rækker: {excel_rows}"
            )

        fixed_rule = (
            applicable_rules[0]
        )

        fixed_rows.append(
            _create_row(
                month=month,
                queue_name=queue_name,
                result=(
                    fixed_rule.result
                    or "Fast månedsbesparelse"
                ),
                rule_id=(
                    fixed_rule.technical_id
                ),
                match_type="NO_STATE_FILTER",
                matching_stats="",
                raw_stats="",
                item_count=0,
                minutes_per_item=Decimal("0"),
                fixed_minutes_per_month=(
                    fixed_rule
                    .fixed_minutes_per_month
                ),
                saved_minutes=(
                    fixed_rule
                    .fixed_minutes_per_month
                ),
                report_view=(
                    fixed_rule.detail_level
                ),
            )
        )

    return fixed_rows


def _normalize_raw_stats(
    raw_stats: tuple[str, ...],
) -> tuple[str, ...]:
    """
    Normaliserer rå tags før visning og gruppering.

    Funktionen:
        fjerner mellemrum før og efter teksten
        fjerner afsluttende dato og klokkeslæt
        fjerner dubletter
        sorterer værdierne stabilt

    Funktionen forsøger ikke at fjerne CPR, navne eller
    andre personoplysninger. Derfor må outputtet kun bruges,
    når Rapportvisning udtrykkeligt er RÅ_TAGS.
    """
    normalized_values = []

    for raw_stat in raw_stats:
        text = str(
            raw_stat
            or ""
        ).strip()

        if not text:
            continue

        text = TRAILING_TIMESTAMP_PATTERN.sub(
            "",
            text,
        ).strip()

        if text:
            normalized_values.append(
                text
            )

    unique_values = {
        value
        for value in normalized_values
    }

    return tuple(
        sorted(
            unique_values,
            key=str.casefold,
        )
    )


def _create_row(
    *,
    month,
    queue_name: str,
    result: str,
    rule_id: str,
    match_type: str,
    matching_stats: str,
    raw_stats: str,
    item_count: int,
    minutes_per_item: Decimal,
    fixed_minutes_per_month: Decimal,
    saved_minutes: Decimal,
    report_view: str,
) -> Row:
    """
    Opretter én række med rapportens 17 kolonner.

    Outputkolonnen hedder fortsat Detailniveau, så rækken kan
    kopieres til den eksisterende fælles tabel. Værdien er den
    valgte Rapportvisning fra Excel-reglen.
    """
    return {
        "Er sumlinje": "Ja",
        "Rækketype": "Sum",
        "Detailniveau": report_view,
        "Datoperspektiv": "Completed",
        "Måned": month,
        "Queue Name": queue_name,
        "Resultat": result,
        "Matchregel-ID": rule_id,
        "Matchtype": match_type,
        "Matchende tags": matching_stats,
        "Rå tags": raw_stats,
        "Antal items": item_count,
        "Itemmarkør": 0,
        "Minutter pr. item": float(
            minutes_per_item
        ),
        "Faste minutter pr. måned": float(
            fixed_minutes_per_month
        ),
        "Besparede minutter": float(
            saved_minutes
        ),
        "Besparede timer": float(
            saved_minutes
            / Decimal("60")
        ),
    }


def _join_unique(
    values,
) -> str:
    """
    Samler unikke, ikke-tomme værdier med linjeskift.
    """
    return "\n".join(
        dict.fromkeys(
            value
            for value in values
            if value
        )
    )