# ats_drift_report.py

"""
SAMLET FLOW FOR ATS-DRIFTSRAPPORT
================================

Flow:

1. Kontroller dansk ugedag.
2. Hent ét fælles database-now.
3. Hent alle aktive processer.
4. Fjern processer fra excluded_process_names.
5. Hent sessionstal.
6. Hent workitem-tal.
7. Hent triggers.
8. Byg én rapportlinje pr. proces.
9. Sortér rækkerne efter tidsplan:
       Time
       Daglig
       Uge
       Måned
       Queue
       Datostyret
       blank/ukendt
10. Sortér alfabetisk efter processens navn inden for gruppen.
11. Opret Excel.
12. Send mail.
13. Behold Excel-filen på disken.

Processer med samme workqueue får de samme workitem-tal,
men får fortsat deres egne sessionstal.
"""

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from q_outlook_api.functionality.mail_api import (
    send_mail,
)

from ats_drift_config import (
    ATS_DRIFT_CONFIG,
    validate_ats_drift_config,
)
from ats_drift_cron_formatter import (
    describe_triggers,
)
from ats_drift_excel_builder import (
    create_ats_drift_excel,
)
from ats_drift_repository import (
    fetch_active_processes,
    fetch_active_triggers,
    fetch_session_counts,
    fetch_workitem_counts,
    find_shared_workqueues,
    get_database_now,
)
from time_helper import (
    now_danish_string,
)

logger = logging.getLogger(__name__)

DK_ZONE = ZoneInfo(
    "Europe/Copenhagen"
)

SESSION_WINDOWS = [
    "24h",
    "48h",
    "72h",
    "7d",
    "14d",
    "30d",
    "40d",
]

WORKITEM_WINDOWS = [
    "24h",
    "48h",
    "72h",
    "7d",
    "14d",
    "30d",
    "40d",
]


def run_ats_drift_report():
    """
    Opretter og sender ATS-driftsrapporten.

    Processer i konfigurationens excluded_process_names
    bliver fjernet, før Excel-rækkerne opbygges.

    Excel-rækkerne sorteres efter:

        1. Time
        2. Daglig
        3. Uge
        4. Måned og Måned (n)
        5. Queue
        6. Datostyret
        7. Blank eller ukendt

    Inden for hver gruppe sorteres alfabetisk efter
    processens navn.

    Output:
        dict:
            Ved sendt rapport:

            {
                "sent": True,
                "skipped": False,
                "process_count": 9,
                "excluded_process_count": 2,
                "excel_file": "tests_local/ATS_....xlsx"
            }

            Ved weekend:

            {
                "sent": False,
                "skipped": True,
                "reason": "Weekend"
            }

    Fejl:
        Database-, Excel- og Graph-fejl sendes videre
        til main.py.
    """

    validate_ats_drift_config()

    should_run, skip_reason = (
        _should_run_today()
    )

    if not should_run:
        logger.info(
            (
                "ATS DRIFTRAPPORT SPRUNGET OVER | "
                f"årsag={skip_reason}"
            )
        )

        return {
            "sent": False,
            "skipped": True,
            "reason": skip_reason,
        }

    logger.info(
        "ATS DRIFTRAPPORT START"
    )

    # ---------------------------------------------------------
    # FÆLLES REFERENCE-TIDSPUNKT
    # ---------------------------------------------------------
    #
    # Alle tidsvinduer beregnes ud fra samme database-now.
    report_now = get_database_now()

    logger.info(
        f"Database reference-tidspunkt: {report_now}"
    )

    # ---------------------------------------------------------
    # HENT PROCESSER
    # ---------------------------------------------------------
    all_processes = fetch_active_processes()

    logger.info(
        (
            "Antal aktive processer før udeladelse: "
            f"{len(all_processes)}"
        )
    )

    # ---------------------------------------------------------
    # UDELAD KONFIGUREREDE PROCESSER
    # ---------------------------------------------------------
    processes, excluded_processes = (
        _exclude_configured_processes(
            all_processes
        )
    )

    logger.info(
        (
            "Antal processer efter udeladelse: "
            f"{len(processes)}"
        )
    )

    if excluded_processes:
        logger.info(
            (
                "Udeladte processer: "
                f"{excluded_processes}"
            )
        )

    # ---------------------------------------------------------
    # HENT TÆLLINGER OG TRIGGERS
    # ---------------------------------------------------------
    session_counts = fetch_session_counts(
        report_now
    )

    workitem_counts = fetch_workitem_counts(
        report_now
    )

    triggers_by_process = (
        fetch_active_triggers()
    )

    # ---------------------------------------------------------
    # DELTE WORKQUEUES
    # ---------------------------------------------------------
    #
    # Kontrollen udføres kun på de processer, der faktisk
    # skal vises i rapporten.
    shared_workqueues = find_shared_workqueues(
        processes
    )

    for workqueue_id, process_names in (
        shared_workqueues.items()
    ):
        logger.warning(
            (
                "DELT WORKQUEUE | "
                f"workqueue_id={workqueue_id} | "
                f"processer={process_names} | "
                "Processerne får samme workitem-tal, "
                "men egne sessionstal"
            )
        )

    # ---------------------------------------------------------
    # BYG RAPPORT-RÆKKER
    # ---------------------------------------------------------
    report_rows = []

    for process in processes:
        process_id = process[
            "process_id"
        ]

        workqueue_id = process.get(
            "workqueue_id"
        )

        process_sessions = (
            session_counts.get(
                process_id,
                {},
            )
        )

        process_workitems = (
            workitem_counts.get(
                workqueue_id,
                {},
            )
        )

        process_triggers = (
            triggers_by_process.get(
                process_id,
                [],
            )
        )

        trigger_description = (
            describe_triggers(
                process_triggers
            )
        )

        row = {
            "process_name": process[
                "process_name"
            ],
            "cron_text": trigger_description[
                "cron_text"
            ],
            "frequency_text": (
                trigger_description[
                    "frequency_text"
                ]
            ),
        }

        # -----------------------------------------------------
        # SESSIONS: COMPLETED/TOTAL
        # -----------------------------------------------------
        for window in SESSION_WINDOWS:
            completed = int(
                process_sessions.get(
                    f"completed_{window}",
                    0,
                )
                or 0
            )

            total = int(
                process_sessions.get(
                    f"total_{window}",
                    0,
                )
                or 0
            )

            row[f"session_{window}"] = (
                f"{completed}/{total}"
            )

        # -----------------------------------------------------
        # COMPLETED OG FAILED WORKITEMS
        # -----------------------------------------------------
        for window in WORKITEM_WINDOWS:
            row[
                f"completed_{window}"
            ] = int(
                process_workitems.get(
                    f"completed_{window}",
                    0,
                )
                or 0
            )

            row[
                f"failed_{window}"
            ] = int(
                process_workitems.get(
                    f"failed_{window}",
                    0,
                )
                or 0
            )

        # -----------------------------------------------------
        # ØVRIGE STATUSSER, 40 DAGE
        # -----------------------------------------------------
        row["in_progress_40d"] = int(
            process_workitems.get(
                "in_progress_40d",
                0,
            )
            or 0
        )

        row["new_40d"] = int(
            process_workitems.get(
                "new_40d",
                0,
            )
            or 0
        )

        row["pending_user_40d"] = int(
            process_workitems.get(
                "pending_user_40d",
                0,
            )
            or 0
        )

        report_rows.append(
            row
        )

        logger.debug(
            (
                "ATS driftrapport række | "
                f"process_id={process_id} | "
                "process_name="
                f"{process['process_name']} | "
                f"workqueue_id={workqueue_id} | "
                f"row={row}"
            )
        )

    # ---------------------------------------------------------
    # SORTÉR RÆKKER
    # ---------------------------------------------------------
    #
    # Sorteringen udføres før Excel-filen bliver oprettet.
    #
    # Primær sortering:
    #     Time
    #     Daglig
    #     Uge
    #     Måned
    #     Queue
    #     Datostyret
    #     øvrige
    #
    # Sekundær sortering:
    #     process_name alfabetisk
    report_rows.sort(
        key=_get_report_row_sort_key
    )

    logger.debug(
        (
            "Sorteret procesrækkefølge: "
            f"{[row['process_name'] for row in report_rows]}"
        )
    )

    # ---------------------------------------------------------
    # OPRET EXCEL
    # ---------------------------------------------------------
    excel_file = create_ats_drift_excel(
        rows=report_rows,
        output_folder=ATS_DRIFT_CONFIG[
            "output_folder"
        ],
        excel_file_prefix=ATS_DRIFT_CONFIG[
            "excel_file_prefix"
        ],
    )

    excel_path = Path(
        excel_file
    )

    if not excel_path.is_file():
        raise FileNotFoundError(
            "ATS-driftsrapportens Excel-fil "
            f"blev ikke fundet: {excel_path}"
        )

    # ---------------------------------------------------------
    # BYG MAIL
    # ---------------------------------------------------------
    created_at_dk = (
        now_danish_string()
    )

    mail_body = ATS_DRIFT_CONFIG[
        "mail_body"
    ].format(
        created_at_dk=created_at_dk,
    )

    logger.info(
        (
            "Sender ATS-driftsrapport | "
            f"fra={ATS_DRIFT_CONFIG['sender_mail']} | "
            f"to={ATS_DRIFT_CONFIG['to']} | "
            f"excel_file={excel_path}"
        )
    )

    # ---------------------------------------------------------
    # SEND MAIL
    # ---------------------------------------------------------
    mail_sent = send_mail(
        user_mail=ATS_DRIFT_CONFIG[
            "sender_mail"
        ],
        mail={
            "subject": ATS_DRIFT_CONFIG[
                "mail_subject"
            ],
            "content_type": "Text",
            "body": mail_body,
            "to": ATS_DRIFT_CONFIG[
                "to"
            ],
            "cc": ATS_DRIFT_CONFIG[
                "cc"
            ],
            "bcc": ATS_DRIFT_CONFIG[
                "bcc"
            ],
            "save_to_sent_items": (
                ATS_DRIFT_CONFIG[
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
            "for ATS-driftsrapporten"
        )

    logger.info(
        (
            "ATS DRIFTRAPPORT SENDT | "
            f"processer={len(report_rows)} | "
            "udeladte_processer="
            f"{len(excluded_processes)} | "
            f"excel_file={excel_path}"
        )
    )

    return {
        "sent": True,
        "skipped": False,
        "process_count": len(
            report_rows
        ),
        "excluded_process_count": len(
            excluded_processes
        ),
        "excluded_processes": (
            excluded_processes
        ),
        "excel_file": str(
            excel_path
        ),
        "created_at_dk": created_at_dk,
    }


def _exclude_configured_processes(
    processes,
):
    """
    Fjerner processer, som står i excluded_process_names.

    Sammenligningen:

        - ignorerer store og små bogstaver
        - ignorerer mellemrum før og efter navnet

    Input:
        processes:
            Liste med processer fra databasen.

            Eksempel:

            [
                {
                    "process_id": 1,
                    "process_name": "Test1",
                    "workqueue_id": 1,
                }
            ]

    Output:
        tuple:

        (
            included_processes,
            excluded_process_names,
        )

        Eksempel:

        (
            [
                {
                    "process_id": 3,
                    "process_name": "advis-dubletter-prisme",
                }
            ],
            [
                "Test1",
                "ats-playwright-test",
            ],
        )
    """

    configured_exclusions = (
        ATS_DRIFT_CONFIG.get(
            "excluded_process_names",
            [],
        )
        or []
    )

    normalized_exclusions = {
        _normalize_process_name(
            process_name
        )
        for process_name in configured_exclusions
        if _normalize_process_name(
            process_name
        )
    }

    included_processes = []
    excluded_process_names = []

    for process in processes:
        process_name = process.get(
            "process_name"
        )

        normalized_process_name = (
            _normalize_process_name(
                process_name
            )
        )

        if (
            normalized_process_name
            in normalized_exclusions
        ):
            excluded_process_names.append(
                process_name
            )

            logger.info(
                (
                    "PROCES UDELADT FRA ATS-DRIFTRAPPORT | "
                    f"process_id={process.get('process_id')} | "
                    f"process_name={process_name}"
                )
            )

            continue

        included_processes.append(
            process
        )

    return (
        included_processes,
        excluded_process_names,
    )


def _get_report_row_sort_key(row):
    """
    Bygger sorteringsnøglen til en Excel-række.

    Sorteringsrækkefølge:

        1. Time
        2. Daglig
        3. Uge
        4. Måned og Måned (n)
        5. Queue
        6. Datostyret
        7. Blank eller ukendt

    Inden for hver gruppe sorteres alfabetisk efter
    processens navn.

    Input:
        row:
            En færdig rapport-række.

            Eksempel:

            {
                "process_name": "Fordeling af mails",
                "frequency_text": "Time",
            }

    Output:
        tuple:

            (
                frequency_rank,
                process_name,
            )

        Eksempel:

            (
                0,
                "fordeling af mails",
            )
    """

    frequency_text = str(
        row.get("frequency_text") or ""
    ).strip()

    frequency_rank = (
        _get_frequency_rank(
            frequency_text
        )
    )

    process_name = (
        _normalize_process_name(
            row.get("process_name")
        )
    )

    return (
        frequency_rank,
        process_name,
    )


def _get_frequency_rank(
    frequency_text,
):
    """
    Oversætter frekvensteksten til et sorteringstal.

    Input:
        frequency_text:
            Eksempler:

                Time
                Daglig
                Uge
                Måned
                Måned (3)
                Queue
                Datostyret
                ""

    Output:
        int:

            0 = Time
            1 = Daglig
            2 = Uge
            3 = Måned eller Måned (n)
            4 = Queue
            5 = Datostyret
            6 = Specialplan
            7 = Blank eller ukendt

    Flere frekvenser kan være adskilt med linjeskift.
    I så fald bruges den højst prioriterede frekvens.
    """

    if not frequency_text:
        return 7

    frequency_lines = [
        line.strip()
        for line in frequency_text.splitlines()
        if line.strip()
    ]

    if not frequency_lines:
        return 7

    line_ranks = [
        _get_single_frequency_rank(
            frequency_line
        )
        for frequency_line in frequency_lines
    ]

    return min(
        line_ranks
    )


def _get_single_frequency_rank(
    frequency_text,
):
    """
    Finder sorteringsrang for én frekvenstekst.

    Måned (3) starter med ordet Måned og placeres
    derfor i samme gruppe som Måned.

    Output:
        int:
            Sorteringsrang.
    """

    normalized_frequency = str(
        frequency_text or ""
    ).strip().casefold()

    if normalized_frequency == "time":
        return 0

    if normalized_frequency == "daglig":
        return 1

    if normalized_frequency == "uge":
        return 2

    if normalized_frequency.startswith(
        "måned"
    ):
        return 3

    if normalized_frequency == "queue":
        return 4

    if normalized_frequency == "datostyret":
        return 5

    if normalized_frequency == "specialplan":
        return 6

    return 7


def _normalize_process_name(
    process_name,
):
    """
    Normaliserer et procesnavn til sammenligning og sortering.

    Input:
        process_name:
            Eksempel:

                " Test1 "

    Output:
        str:
            Eksempel:

                "test1"
    """

    return str(
        process_name or ""
    ).strip().casefold()


def _should_run_today():
    """
    Kontrollerer om ATS-driftsrapporten må køre i dag.

    Kontrollen bruger dansk tidszone.

    Output:
        tuple:

            (True, None)
                Rapporten må køre.

            (False, "Weekend")
                Rapporten springes over.

    Bemærkning:
        Danske helligdage kontrolleres ikke i første version.
    """

    now_dk = datetime.now(
        DK_ZONE
    )

    if (
        ATS_DRIFT_CONFIG.get(
            "skip_weekends",
            True,
        )
        and now_dk.weekday() >= 5
    ):
        return False, "Weekend"

    if ATS_DRIFT_CONFIG.get(
        "skip_public_holidays",
        False,
    ):
        logger.warning(
            (
                "skip_public_holidays=True, "
                "men helligdagskontrol er ikke "
                "implementeret i første version. "
                "Rapporten fortsætter."
            )
        )

    return True, None