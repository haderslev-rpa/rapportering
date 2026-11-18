from __future__ import annotations

import logging
from datetime import datetime, timezone
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

    Rapporten:
        1. Finder de seneste fulde måneder.
        2. Henter regler fra SharePoint.
        3. Slår aktive queue-navne op.
        4. Henter completed workitems.
        5. Klassificerer workitems med PR_ITEM.
        6. Tilføjer faste månedsbesparelser.
        7. Opretter Excel.
        8. Sender eventuelt mail.
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
            "ATS tidsbesparelse starter | "
            f"periode_start={period_start_danish} | "
            f"periode_slut_eksklusiv="
            f"{period_end_danish}"
        )
    )

    workbook_bytes = (
        download_rules_workbook()
    )

    rules = read_rules(
        workbook_bytes
    )

    queue_names = {
        rule.queue_name
        for rule in rules
    }

    queue_ids = resolve_queue_ids(
        queue_names
    )

    workitems = fetch_completed_workitems(
        queue_ids=queue_ids,
        start_utc=_to_naive_utc(
            period_start_danish
        ),
        end_utc_exclusive=_to_naive_utc(
            period_end_danish
        ),
    )

    classified_items = classify_items(
        workitems=workitems,
        rules=rules,
    )

    rows = aggregate_items(
        items=classified_items,
        rules=rules,
    )

    period_text = (
        f"{period_start_danish:%Y-%m-%d}"
        "_til_"
        f"{period_end_danish:%Y-%m-%d}"
    )

    excel_path = create_excel(
        rows=rows,
        period_text=period_text,
    )

    without_match_count = sum(
        1
        for item in classified_items
        if item.rule is None
    )

    total_saved_hours = sum(
        row["Besparede timer"]
        for row in rows
    )

    logger.info(
        (
            "ATS tidsbesparelse færdig | "
            f"aktive_regler={len(rules)} | "
            f"aktive_queues={len(queue_ids)} | "
            f"completed_workitems={len(workitems)} | "
            f"uden_match={without_match_count} | "
            f"outputrækker={len(rows)} | "
            f"samlede_timer={total_saved_hours:.2f} | "
            f"excel={excel_path}"
        )
    )

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
                    Path(
                        excel_path
                    )
                ],
            },
        )

    return {
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
        "without_match": (
            without_match_count
        ),
        "rows": len(
            rows
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
        Kørsel 18-11-2026 og months_back=3:

        start:
            01-08-2026 00:00 dansk tid

        slut eksklusiv:
            01-11-2026 00:00 dansk tid
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


def _to_naive_utc(
    value: datetime,
) -> datetime:
    """
    Omregner et tidszone-aware tidspunkt til
    UTC uden tzinfo.

    ATS-databasens tidskolonner behandles som
    timestamp without time zone.
    """
    return value.astimezone(
        timezone.utc
    ).replace(
        tzinfo=None
    )