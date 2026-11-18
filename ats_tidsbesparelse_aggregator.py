from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from ats_tidsbesparelse_models import (
    AtsRule,
    ClassifiedItem,
    Row,
)


def aggregate_items(
    items: list[ClassifiedItem],
    rules: list[AtsRule],
) -> list[Row]:
    """
    Bygger rapportens opsummerede rækker.

    Først:
        Opretter resultatlinjer for klassificerede
        og ikke-klassificerede workitems.

    Derefter:
        Opretter højst én FAST_PR_MÅNED-linje for
        hver queue og måned med completed aktivitet.
    """
    grouped_items: dict[
        tuple,
        list[ClassifiedItem],
    ] = defaultdict(list)

    for item in items:
        if item.rule is not None:
            group_key = (
                item.month,
                item.queue_name,
                item.rule.technical_id,
            )
        else:
            group_key = (
                item.month,
                item.queue_name,
                "NO_MATCH",
                item.raw_stats,
            )

        grouped_items[
            group_key
        ].append(
            item
        )

    rows: list[Row] = []

    for group in grouped_items.values():
        rows.append(
            _create_item_group_row(
                group
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
        ),
    )


def _create_item_group_row(
    grouped_items: list[ClassifiedItem],
) -> Row:
    """
    Opretter én opsummeret række for en gruppe
    klassificerede workitems eller NO_MATCH-items.
    """
    first_item = grouped_items[0]
    rule = first_item.rule
    item_count = len(
        grouped_items
    )

    raw_stats = _join_unique(
        value
        for item in grouped_items
        for value in item.raw_stats
    )

    if rule is None:
        return _create_row(
            month=first_item.month,
            queue_name=first_item.queue_name,
            result="Ingen matchende regel",
            rule_id="INGEN_MATCH",
            match_type="NO_MATCH",
            matching_stats="",
            raw_stats=raw_stats,
            item_count=item_count,
            minutes_per_item=Decimal("0"),
            fixed_minutes_per_month=Decimal("0"),
            saved_minutes=Decimal("0"),
            detail_level="SUM_RESULTAT",
        )

    matching_stats = _join_unique(
        value
        for item in grouped_items
        for value in item.matched_stats
    )

    saved_minutes = (
        rule.minutes_per_item
        * item_count
    )

    return _create_row(
        month=first_item.month,
        queue_name=first_item.queue_name,
        result=rule.result,
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
        detail_level=rule.detail_level,
    )


def _create_fixed_month_rows(
    *,
    items: list[ClassifiedItem],
    rules: list[AtsRule],
) -> list[Row]:
    """
    Opretter én fast besparelseslinje pr.:

        Queue-navn + måned

    Linjen oprettes kun, hvis queuen har mindst ét
    completed workitem i den pågældende måned.
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
        completed_date = month

        applicable_fixed_rules = [
            rule
            for rule in fixed_rules_by_queue.get(
                queue_key,
                [],
            )
            if (
                rule.valid_from
                <= completed_date
                < rule.valid_to
            )
        ]

        if not applicable_fixed_rules:
            continue

        if len(
            applicable_fixed_rules
        ) > 1:
            matching_rows = [
                rule.row_number
                for rule in applicable_fixed_rules
            ]

            raise RuntimeError(
                "Der blev fundet flere gyldige "
                "FAST_PR_MÅNED-regler for "
                f"queue {queue_name!r} og "
                f"måned {month:%d-%m-%Y}. "
                "Excel-rækker: "
                f"{matching_rows}"
            )

        fixed_rule = (
            applicable_fixed_rules[0]
        )

        result = (
            fixed_rule.result
            or "Fast månedsbesparelse"
        )

        fixed_rows.append(
            _create_row(
                month=month,
                queue_name=queue_name,
                result=result,
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
                detail_level=(
                    fixed_rule.detail_level
                ),
            )
        )

    return fixed_rows


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
    detail_level: str,
) -> Row:
    """
    Opretter én række med de 17 aftalte kolonner.
    """
    return {
        "Er sumlinje": "Ja",
        "Rækketype": "Sum",
        "Detailniveau": detail_level,
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