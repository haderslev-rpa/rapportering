from __future__ import annotations

from datetime import timezone
from zoneinfo import ZoneInfo

from ats_tidsbesparelse_models import (
    AtsRule,
    ClassifiedItem,
)


DANISH_TIME_ZONE = ZoneInfo(
    "Europe/Copenhagen"
)


def classify_items(
    workitems: list[dict],
    rules: list[AtsRule],
) -> list[ClassifiedItem]:
    """
    Klassificerer completed workitems.

    Kun PR_ITEM-regler bruges til at klassificere
    de enkelte workitems.

    FAST_PR_MÅNED-regler behandles senere af
    aggregatoren, én gang pr. queue og måned.
    """
    classification_rules_by_queue: dict[
        str,
        list[AtsRule],
    ] = {}

    for rule in rules:
        if (
            rule.calculation_method
            != "PR_ITEM"
        ):
            continue

        queue_key = (
             rule.queue_name.casefold()
        )

        classification_rules_by_queue.setdefault(
           queue_key,
            [],
        ).append(
            rule
        )

    classified_items: list[
        ClassifiedItem
    ] = []

    for workitem in workitems:
        completed_at = _as_danish_datetime(
            workitem["updated_at"]
        )

        raw_stats = _extract_stats(
            workitem.get("data")
            or {}
        )

        queue_name = str(
            workitem["queue_name"]
        ).strip()

        queue_rules = (
            classification_rules_by_queue.get(
                queue_name.casefold(),
                [],
            )
        )

        matched_rule, matched_stats = (
            _find_matching_rule(
                rules=queue_rules,
                raw_stats=raw_stats,
                completed_date=(
                    completed_at.date()
                ),
            )
        )

        classified_items.append(
            ClassifiedItem(
                item_id=int(
                    workitem["id"]
                ),
                queue_name=queue_name,
                completed_at=completed_at,
                month=completed_at.date().replace(
                    day=1
                ),
                raw_stats=raw_stats,
                matched_stats=matched_stats,
                rule=matched_rule,
            )
        )

    return classified_items


def _extract_stats(
    data: dict,
) -> tuple[str, ...]:
    """
    Samler de værdier, der må bruges til match.

    Der søges i:
        data["state"]
        data["status"]
        data["status"]["status"]
        data["status"]["status_code"]
        data["status_code"]
        samt varianter med stort begyndelsesbogstav.
    """
    values: list[str] = []

    state_value = data.get(
        "state",
        [],
    )

    if isinstance(
        state_value,
        list,
    ):
        for value in state_value:
            _append_text(
                values,
                value,
            )
    else:
        _append_text(
            values,
            state_value,
        )

    status_value = data.get(
        "status"
    )

    if isinstance(
        status_value,
        dict,
    ):
        for status_key in (
            "status",
            "Status",
            "status_code",
            "Status_code",
            "Status_Code",
            "code",
        ):
            _append_text(
                values,
                status_value.get(
                    status_key
                ),
            )
    else:
        _append_text(
            values,
            status_value,
        )

    for status_key in (
        "status_code",
        "Status_code",
        "Status_Code",
        "Status",
    ):
        _append_text(
            values,
            data.get(
                status_key
            ),
        )

    return tuple(
        dict.fromkeys(
            values
        )
    )


def _append_text(
    values: list[str],
    value,
) -> None:
    """
    Tilføjer en ikke-tom tekstværdi til listen.
    """
    if value is None:
        return

    text = str(
        value
    ).strip()

    if text:
        values.append(
            text
        )


def _find_matching_rule(
    *,
    rules: list[AtsRule],
    raw_stats: tuple[str, ...],
    completed_date,
) -> tuple[
    AtsRule | None,
    tuple[str, ...],
]:
    """
    Finder den første matchende regel.

    Reglerne forventes allerede sorteret efter:
        prioritet
        Excel-række

    Gyldighed:
        valid_from <= completed_date < valid_to
    """
    normalized_stats = [
        raw_stat.casefold()
        for raw_stat in raw_stats
    ]

    for rule in rules:
        if not (
            rule.valid_from
            <= completed_date
            < rule.valid_to
        ):
            continue

        matching_values: list[str] = []

        for configured_stat in rule.stats:
            configured_normalized = (
                configured_stat.casefold()
            )

            matching_raw_value = next(
                (
                    raw_stat
                    for (
                        raw_stat,
                        normalized_stat,
                    ) in zip(
                        raw_stats,
                        normalized_stats,
                    )
                    if normalized_stat.startswith(
                        configured_normalized
                    )
                ),
                None,
            )

            if matching_raw_value:
                matching_values.append(
                    matching_raw_value
                )

        if (
            rule.match_type
            == "NO_STATE_FILTER"
        ):
            return (
                rule,
                (),
            )

        if (
            rule.match_type
            == "ANY"
            and matching_values
        ):
            return (
                rule,
                tuple(
                    dict.fromkeys(
                        matching_values
                    )
                ),
            )

        if (
            rule.match_type
            == "ALL"
            and len(
                matching_values
            )
            == len(
                rule.stats
            )
        ):
            return (
                rule,
                tuple(
                    dict.fromkeys(
                        matching_values
                    )
                ),
            )

    return (
        None,
        (),
    )


def _as_danish_datetime(
    value,
):
    """
    Fortolker naive database-tidspunkter som UTC
    og omregner dem til dansk tid.
    """
    if value.tzinfo is None:
        value = value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        DANISH_TIME_ZONE
    )