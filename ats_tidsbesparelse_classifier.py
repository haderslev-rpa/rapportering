from __future__ import annotations

from datetime import datetime
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
    Klassificerer completed workitems efter reglerne fra Excel.

    Regler:
        Kun PR_ITEM-regler bruges til klassificering af
        de enkelte workitems.

        FAST_PR_MÅNED behandles separat i aggregatoren.

        Regler vurderes med:
            laveste prioritet først
            derefter laveste Excel-rækkenummer

        Den første matchende regel bruges.

    Matchgrundlag:
        data["state"]
        data["status"]
        data["status"]["status"]
        data["status"]["status_code"]
        data["status_code"]

        Funktionen understøtter også tilsvarende feltnavne
        med stort begyndelsesbogstav.

    Output:
        En liste med ClassifiedItem-objekter.

        raw_stats:
            De faktiske værdier fra workitemet.
            De vises kun, hvis Excel-reglen har
            Rapportvisning = RÅ_TAGS.

        matched_stats:
            De korte søgetekster fra Excel-reglens
            States-kolonne.

            Et workitem kan eksempelvis indeholde:

                2.0 Advis markeret færdiggjort i SAPA
                03-08-2026 09:02:05

            Hvis Excel-reglen indeholder:

                2.0 Advis markeret færdiggjort i SAPA

            bliver matched_stats:

                2.0 Advis markeret færdiggjort i SAPA
    """
    rules_by_queue: dict[
        str,
        list[AtsRule],
    ] = {}

    for rule in rules:
        # FAST_PR_MÅNED skal ikke klassificere
        # de enkelte workitems.
        if (
            rule.calculation_method
            != "PR_ITEM"
        ):
            continue

        queue_key = (
            rule.queue_name
            .strip()
            .casefold()
        )

        rules_by_queue.setdefault(
            queue_key,
            [],
        ).append(
            rule
        )

    # Laveste prioritet skal vurderes først.
    #
    # Excel-rækkenummeret er sekundær sortering,
    # hvis to regler har samme prioritet.
    for queue_rules in rules_by_queue.values():
        queue_rules.sort(
            key=lambda rule: (
                rule.priority,
                rule.row_number,
            )
        )

    classified_items: list[
        ClassifiedItem
    ] = []

    for workitem in workitems:
        completed_at = _as_danish_datetime(
            workitem["updated_at"]
        )

        queue_name = str(
            workitem["queue_name"]
        ).strip()

        raw_stats = _extract_stats(
            workitem.get("data")
            or {}
        )

        queue_rules = rules_by_queue.get(
            queue_name.casefold(),
            [],
        )

        (
            matched_rule,
            matched_stats,
        ) = _find_rule(
            rules=queue_rules,
            raw_stats=raw_stats,
            completed_date=(
                completed_at.date()
            ),
        )

        classified_items.append(
            ClassifiedItem(
                item_id=int(
                    workitem["id"]
                ),
                queue_name=queue_name,
                completed_at=completed_at,
                month=(
                    completed_at
                    .date()
                    .replace(
                        day=1
                    )
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
    Samler alle værdier, som må bruges til regelmatch.

    Der undersøges:

        data["state"]

        data["status"]

        data["status"]["status"]

        data["status"]["Status"]

        data["status"]["status_code"]

        data["status"]["Status_code"]

        data["status"]["Status_Code"]

        data["status"]["code"]

        data["status_code"]

        data["Status_code"]

        data["Status_Code"]

        data["Status"]

    Værdierne bevares som rå tekst.

    Dato og klokkeslæt fjernes ikke her, fordi de fulde
    værdier kan være nødvendige, hvis Excel-reglen har:

        Rapportvisning = RÅ_TAGS

    Aggregatoren bestemmer senere, om rå værdier må vises.
    """
    values: list[str] = []

    # ---------------------------------------------------------
    # DATA.STATE
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # DATA.STATUS
    # ---------------------------------------------------------
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
        # Understøtter også data["status"] som almindelig tekst.
        _append_text(
            values,
            status_value,
        )

    # ---------------------------------------------------------
    # STATUSFELTER DIREKTE UNDER DATA
    # ---------------------------------------------------------
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

    # Fjern dubletter, men bevar den oprindelige rækkefølge.
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
    Tilføjer en ikke-tom tekstværdi til en liste.

    Output:
        None.
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


def _find_rule(
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

    Reglerne vurderes efter:
        1. Laveste prioritet.
        2. Laveste Excel-rækkenummer.

    Gyldighed:
        valid_from <= completed_date < valid_to

    ANY:
        Mindst én af værdierne fra Excel-reglens States
        skal matche.

    ALL:
        Alle værdier fra Excel-reglens States skal matche.

        Værdierne behøver ikke findes i samme state.
        De kan eksempelvis findes fordelt på:

            data["state"]
            data["status"]
            data["status_code"]

    NO_STATE_FILTER:
        Reglen matcher uden krav om state eller status.

    Matchningen bruger startswith(), så en Excel-værdi som:

        2.0 Advis markeret færdiggjort i SAPA

    matcher en faktisk værdi som:

        2.0 Advis markeret færdiggjort i SAPA
        03-08-2026 09:02:05

    matched_stats indeholder kun de konfigurerede værdier
    fra Excel. De fulde workitem-værdier returneres ikke som
    matched_stats.
    """
    normalized_raw_stats = [
        raw_stat.casefold()
        for raw_stat in raw_stats
    ]

    sorted_rules = sorted(
        rules,
        key=lambda rule: (
            rule.priority,
            rule.row_number,
        ),
    )

    for rule in sorted_rules:
        # -----------------------------------------------------
        # GYLDIGHEDSPERIODE
        # -----------------------------------------------------
        if not (
            rule.valid_from
            <= completed_date
            < rule.valid_to
        ):
            continue

        # Ekstra sikkerhed:
        # FAST_PR_MÅNED må ikke klassificere workitems.
        if (
            rule.calculation_method
            != "PR_ITEM"
        ):
            continue

        # -----------------------------------------------------
        # INGEN STATE-FILTRERING
        # -----------------------------------------------------
        if (
            rule.match_type
            == "NO_STATE_FILTER"
        ):
            return (
                rule,
                (),
            )

        # -----------------------------------------------------
        # FIND KONFIGUREREDE VÆRDIER
        # -----------------------------------------------------
        matched_configured_stats: list[
            str
        ] = []

        for configured_stat in rule.stats:
            configured_normalized = (
                configured_stat.casefold()
            )

            has_match = any(
                raw_stat.startswith(
                    configured_normalized
                )
                for raw_stat
                in normalized_raw_stats
            )

            if has_match:
                # Gem den korte tekst fra Excel.
                #
                # Gem ikke den fulde workitem-værdi med
                # dato, klokkeslæt eller eventuel fritekst.
                matched_configured_stats.append(
                    configured_stat
                )

        matched_configured_stats = list(
            dict.fromkeys(
                matched_configured_stats
            )
        )

        # -----------------------------------------------------
        # ANY
        # -----------------------------------------------------
        if (
            rule.match_type == "ANY"
            and matched_configured_stats
        ):
            return (
                rule,
                tuple(
                    matched_configured_stats
                ),
            )

        # -----------------------------------------------------
        # ALL
        # -----------------------------------------------------
        if (
            rule.match_type == "ALL"
            and len(
                matched_configured_stats
            )
            == len(
                rule.stats
            )
        ):
            return (
                rule,
                tuple(
                    matched_configured_stats
                ),
            )

    return (
        None,
        (),
    )


def _as_danish_datetime(
    value: datetime,
) -> datetime:
    """
    Fortolker et tidspunkt fra workitem.updated_at som
    dansk lokaltid.

    Automation Server-databasens updated_at er i denne
    kodebase dokumenteret som timestamp without time zone,
    hvor værdien repræsenterer dansk lokal tid.

    Eksempel:
        Databaseværdi:
            2026-08-03 09:02:05

        Fortolkning:
            2026-08-03 09:02:05 Europe/Copenhagen

    Hvis værdien allerede har en tidszone, omregnes værdien
    til Europe/Copenhagen.
    """
    if value.tzinfo is None:
        return value.replace(
            tzinfo=DANISH_TIME_ZONE
        )

    return value.astimezone(
        DANISH_TIME_ZONE
    )