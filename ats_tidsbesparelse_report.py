from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from q_outlook_api.functionality.mail_api import (
    send_mail,
)

from ats_tidsbesparelse_aggregator import (
    aggregate_items,
)
from ats_tidsbesparelse_classifier import (
    classify_items,
)
from ats_tidsbesparelse_config import (
    ATS_TIDSBESPARELSE_CONFIG,
    validate_ats_tidsbesparelse_config,
)
from ats_tidsbesparelse_excel import (
    create_excel,
)
from ats_tidsbesparelse_repository import (
    fetch_completed_workitems,
    resolve_queue_ids,
)
from ats_tidsbesparelse_rules import (
    read_rules,
)
from ats_tidsbesparelse_sharepoint import (
    download_rules_workbook,
)


logger = logging.getLogger(
    __name__
)

DANISH_TIME_ZONE = ZoneInfo(
    "Europe/Copenhagen"
)


def run_ats_tidsbesparelse_report(
    *,
    send_email: bool = True,
    now: datetime | None = None,
) -> dict:
    """
    Opretter ATS-tidsbesparelsesrapporten.

    Flow:
        1. Valider konfigurationen.
        2. Find de seneste fulde måneder.
        3. Hent Excel-reglerne fra SharePoint.
        4. Valider og indlæs reglerne.
        5. Slå queue-navne op i Automation Server.
        6. Hent COMPLETED workitems på updated_at.
        7. Klassificér workitems med PR_ITEM-regler.
        8. Gruppér linjerne efter Rapportvisning.
        9. Tilføj FAST_PR_MÅNED-rækker.
        10. Opret Excel-filen.
        11. Send eventuelt filen med mail.

    Rapportvisning:
        RESULTAT:
            Ingen tags vises.

        REGEL_TAGS:
            Kun søgeteksterne fra Excel vises.

        RÅ_TAGS:
            De faktiske, normaliserede værdier må vises.

        NO_MATCH:
            Viser aldrig rå tags.

    Output:
        En dictionary med oplysninger om kørslen.
    """
    validate_ats_tidsbesparelse_config()

    current_time = (
        now
        or datetime.now(
            DANISH_TIME_ZONE
        )
    )

    (
        period_start_danish,
        period_end_danish,
    ) = _get_full_month_period(
        current_time=current_time,
        months_back=(
            ATS_TIDSBESPARELSE_CONFIG[
                "months_back"
            ]
        ),
    )

    logger.info(
        (
            "ATS TIDSBESPARELSE START | "
            f"periode_start={period_start_danish} | "
            "periode_slut_eksklusiv="
            f"{period_end_danish} | "
            "months_back="
            f"{ATS_TIDSBESPARELSE_CONFIG['months_back']}"
        )
    )

    # ---------------------------------------------------------
    # HENT OG VALIDER REGLER
    # ---------------------------------------------------------
    workbook_bytes = (
        download_rules_workbook()
    )

    rules = read_rules(
        workbook_bytes
    )

    logger.info(
        (
            "ATS tidsbesparelse | "
            f"aktive_regler={len(rules)}"
        )
    )

    # ---------------------------------------------------------
    # FIND AKTIVE QUEUES
    # ---------------------------------------------------------
    queue_names = {
        rule.queue_name
        for rule in rules
    }

    queue_ids = resolve_queue_ids(
        queue_names
    )

    logger.info(
        (
            "ATS tidsbesparelse | "
            f"aktive_queues={len(queue_ids)}"
        )
    )

    # ---------------------------------------------------------
    # HENT COMPLETED WORKITEMS
    # ---------------------------------------------------------
    #
    # Repositoryet forventer naive danske databasetidspunkter,
    # fordi workitem.updated_at i denne kodebase er gemt som:
    #
    #     timestamp without time zone
    #
    # og indeholder dansk lokal tid.
    #
    workitems = fetch_completed_workitems(
        queue_ids=queue_ids,
        start_utc=_as_naive_danish_datetime(
            period_start_danish
        ),
        end_utc_exclusive=(
            _as_naive_danish_datetime(
                period_end_danish
            )
        ),
    )

    logger.info(
        (
            "ATS tidsbesparelse | "
            "completed_workitems="
            f"{len(workitems)}"
        )
    )

    # ---------------------------------------------------------
    # KLASSIFICÉR WORKITEMS
    # ---------------------------------------------------------
    classified_items = classify_items(
        workitems=workitems,
        rules=rules,
    )

    classified_count = sum(
        1
        for item in classified_items
        if item.rule is not None
    )

    without_match_count = sum(
        1
        for item in classified_items
        if item.rule is None
    )

    logger.info(
        (
            "ATS tidsbesparelse | "
            f"klassificerede={classified_count} | "
            f"uden_match={without_match_count}"
        )
    )

    # ---------------------------------------------------------
    # AGGREGÉR RAPPORTLINJER
    # ---------------------------------------------------------
    #
    # rules sendes med, fordi FAST_PR_MÅNED-regler ikke
    # klassificerer de enkelte workitems.
    #
    rows = aggregate_items(
        items=classified_items,
        rules=rules,
    )

    total_saved_minutes = sum(
        row["Besparede minutter"]
        for row in rows
    )

    total_saved_hours = sum(
        row["Besparede timer"]
        for row in rows
    )

    logger.info(
        (
            "ATS tidsbesparelse | "
            f"outputrækker={len(rows)} | "
            "besparede_minutter="
            f"{total_saved_minutes:.2f} | "
            "besparede_timer="
            f"{total_saved_hours:.2f}"
        )
    )

    # ---------------------------------------------------------
    # OPRET EXCEL
    # ---------------------------------------------------------
    #
    # Slutdatoen er eksklusiv.
    #
    # Eksempel:
    #     start = 01-08-2026
    #     slut  = 01-11-2026
    #
    # Rapporten indeholder:
    #     august
    #     september
    #     oktober
    #
    period_text = (
        f"{period_start_danish:%Y-%m-%d}"
        "_til_"
        f"{period_end_danish:%Y-%m-%d}"
    )

    excel_path = create_excel(
        rows=rows,
        period_text=period_text,
    )

    excel_path = Path(
        excel_path
    )

    if not excel_path.is_file():
        raise FileNotFoundError(
            "ATS-tidsbesparelsesrapportens "
            "Excel-fil blev ikke fundet efter "
            f"oprettelsen: {excel_path}"
        )

    logger.info(
        (
            "ATS tidsbesparelse | "
            f"excel_oprettet={excel_path}"
        )
    )

    # ---------------------------------------------------------
    # SEND EVENTUELT MAIL
    # ---------------------------------------------------------
    mail_sent = False

    if send_email:
        mail_body = (
            ATS_TIDSBESPARELSE_CONFIG[
                "mail_body"
            ].format(
                period_text=period_text,
                months_back=(
                    ATS_TIDSBESPARELSE_CONFIG[
                        "months_back"
                    ]
                ),
            )
        )

        mail_subject = (
            ATS_TIDSBESPARELSE_CONFIG[
                "mail_subject"
            ].format(
                period_text=period_text,
            )
        )

        logger.info(
            (
                "Sender ATS-tidsbesparelsesrapport | "
                "fra="
                f"{ATS_TIDSBESPARELSE_CONFIG['sender_mail']} | "
                "to="
                f"{ATS_TIDSBESPARELSE_CONFIG['to']} | "
                f"excel_file={excel_path}"
            )
        )

        mail_sent = send_mail(
            user_mail=(
                ATS_TIDSBESPARELSE_CONFIG[
                    "sender_mail"
                ]
            ),
            mail={
                "subject": mail_subject,
                "content_type": "Text",
                "body": mail_body,
                "to": (
                    ATS_TIDSBESPARELSE_CONFIG[
                        "to"
                    ]
                ),
                "cc": (
                    ATS_TIDSBESPARELSE_CONFIG[
                        "cc"
                    ]
                ),
                "bcc": (
                    ATS_TIDSBESPARELSE_CONFIG[
                        "bcc"
                    ]
                ),
                "save_to_sent_items": (
                    ATS_TIDSBESPARELSE_CONFIG[
                        "save_to_sent_items"
                    ]
                ),
                "attachments": [
                    excel_path
                ],
            },
        )

        if mail_sent is not True:
            raise RuntimeError(
                "send_mail returnerede ikke True "
                "for ATS-tidsbesparelsesrapporten."
            )

        logger.info(
            (
                "ATS TIDSBESPARELSE SENDT | "
                f"excel_file={excel_path}"
            )
        )
    else:
        logger.info(
            (
                "ATS TIDSBESPARELSE LOKAL | "
                "Mail blev ikke sendt | "
                f"excel_file={excel_path}"
            )
        )

    # ---------------------------------------------------------
    # RESULTAT
    # ---------------------------------------------------------
    result = {
        "period_start": (
            period_start_danish.isoformat()
        ),
        "period_end_exclusive": (
            period_end_danish.isoformat()
        ),
        "active_rules": len(
            rules
        ),
        "active_queues": len(
            queue_ids
        ),
        "completed": len(
            workitems
        ),
        "classified": (
            classified_count
        ),
        "without_match": (
            without_match_count
        ),
        "rows": len(
            rows
        ),
        "saved_minutes": round(
            total_saved_minutes,
            2,
        ),
        "hours": round(
            total_saved_hours,
            2,
        ),
        "excel_path": str(
            excel_path
        ),
        "mail_sent": bool(
            mail_sent
        ),
    }

    logger.info(
        (
            "ATS TIDSBESPARELSE FÆRDIG | "
            f"{result}"
        )
    )

    return result


def _get_full_month_period(
    *,
    current_time: datetime,
    months_back: int,
) -> tuple[
    datetime,
    datetime,
]:
    """
    Finder de seneste afsluttede kalendermåneder.

    Eksempel:
        current_time:
            18-11-2026

        months_back:
            3

        start:
            01-08-2026 00:00 dansk tid

        slut, eksklusiv:
            01-11-2026 00:00 dansk tid

    Output:
        tuple:
            (
                period_start,
                period_end_exclusive,
            )
    """
    if current_time.tzinfo is None:
        current_time = current_time.replace(
            tzinfo=DANISH_TIME_ZONE
        )
    else:
        current_time = current_time.astimezone(
            DANISH_TIME_ZONE
        )

    period_end = current_time.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    start_year = period_end.year
    start_month = (
        period_end.month
        - months_back
    )

    while start_month <= 0:
        start_year -= 1
        start_month += 12

    period_start = period_end.replace(
        year=start_year,
        month=start_month,
    )

    return (
        period_start,
        period_end,
    )


def _as_naive_danish_datetime(
    value: datetime,
) -> datetime:
    """
    Konverterer et tidspunkt til dansk lokaltid og
    fjerner derefter tidszoneinformationen.

    Det passer til workitem.updated_at i den aktuelle
    databasekode, hvor feltet er timestamp without time zone
    og værdien repræsenterer dansk lokal tid.

    Eksempel:
        Input:
            2026-08-01 00:00:00+02:00

        Output:
            2026-08-01 00:00:00
    """
    if value.tzinfo is None:
        return value

    return value.astimezone(
        DANISH_TIME_ZONE
    ).replace(
        tzinfo=None
    )