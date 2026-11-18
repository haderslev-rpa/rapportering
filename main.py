# main.py

import asyncio
import logging
import sys

from ats_tidsbesparelse_report import run_ats_tidsbesparelse_report

from automation_server_client import (
    AutomationServer,
    WorkItemError,
)

from q_haderslev_vbo.automation_server.ats_update_item_data import (
    update_item_data,
)

from ats_drift_report import (
    run_ats_drift_report,
)
from behandel import behandel_item
from config_reports import (
    REPORTS,
    validate_reports_config,
)
from database_workitems_repository import (
    count_workitems_for_report,
    find_last_mail_sendt_timestamp,
    find_last_rapportering_end,
    get_database_time_minus_seconds,
)
from logging_helper import (
    log_block,
    log_dict,
    log_error,
    log_info,
    log_warning,
)
from reporting_item_builder import (
    build_report_item_data,
)
from scheduling_should_run import (
    should_run_report,
)
from sharepoint_report_config_repository import (
    find_sharepoint_config_by_rapport_id,
    set_run_now_to_no,
)

# ------------------------------------------------------------
# CLI FLAGS
# ------------------------------------------------------------
DEBUG = "--debug" in sys.argv
QUEUE_MODE = "--queue" in sys.argv
ATS_DRIFT_MODE = "--ats-drift" in sys.argv
ATS_TIDSBESPARELSE_MODE = "--ats-tidsbesparelse" in sys.argv
ATS_TIDSBESPARELSE_LOCAL_MODE = "--ats-tidsbesparelse-local" in sys.argv

# ------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------
#
# --debug giver kun mere log.
#
# --debug ændrer aldrig:
#     cron
#     rapporteringsperiode
#     queue-mode
#     ATS-driftsrapportens data
#
LOG_LEVEL = (
    logging.DEBUG
    if DEBUG
    else logging.INFO
)

logging.basicConfig(
    level=LOG_LEVEL,
    format=(
        "%(asctime)s [%(levelname)s] "
        "%(name)s: %(message)s"
    ),
    stream=sys.stdout,
    force=True,
)

logging.getLogger("httpx").setLevel(
    logging.WARNING
)
logging.getLogger("httpcore").setLevel(
    logging.WARNING
)
logging.getLogger(
    "automation_server_client"
).setLevel(logging.WARNING)
logging.getLogger("debugpy").setLevel(
    logging.WARNING
)

logger = logging.getLogger(__name__)


async def populate_queue(
    workqueue,
    debug,
):
    """
    Producer mode.

    Kontrollerer de almindelige dynamiske rapporter og
    opretter rapportering-items, når reglerne tillader det.

    Output:
        None.
    """

    log_block(
        logger,
        "QUEUE MODE START",
        [
            f"debug={debug}",
            (
                "antal_rapporter_i_config="
                f"{len(REPORTS)}"
            ),
            (
                "Queue vælges via "
                "ATS_WORKQUEUE_OVERRIDE i .env"
            ),
        ],
    )

    created_count = 0
    skipped_count = 0

    for report in REPORTS:
        rapport_id = report["rapport_id"]

        log_block(
            logger,
            (
                "STARTER RAPPORTCHECK | "
                f"rapport_id={rapport_id}"
            ),
            [
                (
                    "rapport_navn="
                    f"{report['rapport_navn']}"
                ),
                (
                    "kilde_queue="
                    f"{report['kilde_queue']}"
                ),
                (
                    "status_filter="
                    f"{report['status_filter']}"
                ),
                (
                    "time_field="
                    f"{report['time_field']}"
                ),
            ],
        )

        log_dict(
            logger,
            "Rapport config",
            report,
        )

        sharepoint_config = (
            find_sharepoint_config_by_rapport_id(
                rapport_id
            )
        )

        if not sharepoint_config:
            skipped_count += 1

            log_warning(
                logger,
                (
                    "SKIP | Ingen SharePoint config "
                    f"fundet | rapport_id={rapport_id}"
                ),
            )
            continue

        log_info(
            logger,
            (
                "SharePoint match | "
                f"rapport_id={rapport_id} | "
                "sharepoint_item_id="
                f"{sharepoint_config.get('id')} | "
                f"title={sharepoint_config.get('titel')} | "
                f"aktiv={sharepoint_config.get('aktiv')} | "
                "run_now="
                f"{sharepoint_config.get('run_now')} | "
                f"cron={sharepoint_config.get('cron')}"
            ),
        )

        last_mail_sendt_timestamp = (
            find_last_mail_sendt_timestamp(
                rapport_id
            )
        )

        last_rapportering_end = (
            find_last_rapportering_end(
                rapport_id
            )
        )

        log_info(
            logger,
            (
                f"Historik | rapport_id={rapport_id} | "
                "last_mail_sendt_timestamp="
                f"{last_mail_sendt_timestamp} | "
                "last_rapportering_end="
                f"{last_rapportering_end}"
            ),
        )

        should_run, koerselstype, reason = (
            should_run_report(
                cron_text=sharepoint_config.get(
                    "cron"
                ),
                run_now=sharepoint_config.get(
                    "run_now"
                ),
                aktiv=sharepoint_config.get(
                    "aktiv"
                ),
                minimum_dage_efter_sidste_rapport=(
                    sharepoint_config.get(
                        "minimum_dage_efter_sidste_rapport",
                        0,
                    )
                ),
                last_mail_sendt_timestamp=(
                    last_mail_sendt_timestamp
                ),
                last_rapportering_end=(
                    last_rapportering_end
                ),
                debug=debug,
            )
        )

        log_info(
            logger,
            (
                f"Beslutning | rapport_id={rapport_id} | "
                f"should_run={should_run} | "
                f"koerselstype={koerselstype} | "
                f"reason={reason}"
            ),
        )

        if not should_run:
            skipped_count += 1

            log_warning(
                logger,
                (
                    f"SKIP | rapport_id={rapport_id} | "
                    f"årsag={reason}"
                ),
            )
            continue

        rapportering_start = (
            last_rapportering_end
        )

        if not rapportering_start:
            rapportering_start = report[
                "default_rapportering_start"
            ]

            log_info(
                logger,
                (
                    "rapportering_start ikke fundet "
                    f"i historik | rapport_id={rapport_id} | "
                    f"bruger_default={rapportering_start}"
                ),
            )
        else:
            log_info(
                logger,
                (
                    "rapportering_start fundet "
                    f"i historik | rapport_id={rapport_id} | "
                    f"value={rapportering_start}"
                ),
            )

        # Fast sikkerhedsbuffer på 5 sekunder.
        rapportering_end = (
            get_database_time_minus_seconds(5)
        )

        log_info(
            logger,
            (
                f"rapportering_end beregnet | "
                f"rapport_id={rapport_id} | "
                f"value={rapportering_end}"
            ),
        )

        if str(rapportering_start) >= str(
            rapportering_end
        ):
            skipped_count += 1

            log_warning(
                logger,
                (
                    "SKIP | ugyldigt tidsvindue | "
                    f"rapport_id={rapport_id} | "
                    f"rapportering_start={rapportering_start} | "
                    f"rapportering_end={rapportering_end}"
                ),
            )
            continue

        antal_rows = count_workitems_for_report(
            kilde_queue=report["kilde_queue"],
            status_filter=report["status_filter"],
            time_field=report["time_field"],
            rapportering_start=rapportering_start,
            rapportering_end=rapportering_end,
            extra_where_sql=report.get(
                "extra_where_sql",
                "",
            ),
            sql_parameters=report.get(
                "sql_parameters",
                {},
            ),
        )

        log_info(
            logger,
            (
                f"Database check | rapport_id={rapport_id} | "
                f"kilde_queue={report['kilde_queue']} | "
                f"status_filter={report['status_filter']} | "
                f"time_field={report['time_field']} | "
                f"antal_rows={antal_rows}"
            ),
        )

        data_json = build_report_item_data(
            report=report,
            sharepoint_config=sharepoint_config,
            rapportering_start=rapportering_start,
            rapportering_end=rapportering_end,
            antal_rows=antal_rows,
            koerselstype=koerselstype,
        )

        log_dict(
            logger,
            "Data til nyt rapportering item",
            data_json,
        )

        reference = (
            f"{rapport_id}_"
            f"{data_json['box']['rapportering_end']}"
        )

        log_info(
            logger,
            (
                f"OPRETTER ITEM | "
                f"rapport_id={rapport_id} | "
                f"reference={reference}"
            ),
        )

        workqueue.add_item(
            data=data_json,
            reference=reference,
        )

        created_count += 1

        log_info(
            logger,
            (
                f"ITEM OPRETTET | "
                f"rapport_id={rapport_id} | "
                f"reference={reference} | "
                f"antal_rows={antal_rows}"
            ),
        )

        if sharepoint_config.get("run_now") == "Ja":
            log_info(
                logger,
                (
                    "Run now = Ja | "
                    "sætter Run now = Nej | "
                    f"rapport_id={rapport_id} | "
                    "sharepoint_item_id="
                    f"{sharepoint_config.get('id')}"
                ),
            )

            set_run_now_to_no(
                sharepoint_config.get("id")
            )

        log_info(
            logger,
            (
                f"SLUT RAPPORTCHECK | "
                f"rapport_id={rapport_id}"
            ),
        )

    log_block(
        logger,
        "QUEUE MODE SLUT",
        [
            f"oprettede_items={created_count}",
            f"skippede_rapporter={skipped_count}",
        ],
    )


async def process_workqueue(
    workqueue,
    debug,
):
    """
    Consumer mode.

    Behandler eksisterende almindelige rapportering-items.

    Output:
        None.
    """

    log_block(
        logger,
        "PROCESS MODE START",
        [
            f"debug={debug}",
        ],
    )

    processed_count = 0

    for item in workqueue:
        with item:
            data = item.data

            try:
                log_info(
                    logger,
                    (
                        "STARTER ITEM | "
                        f"reference={item.reference}"
                    ),
                )

                log_dict(
                    logger,
                    "ITEM DATA",
                    data,
                )

                await behandel_item(item)

                item.complete("Completed")
                processed_count += 1

                log_info(
                    logger,
                    (
                        "ITEM COMPLETED | "
                        f"reference={item.reference}"
                    ),
                )

            except WorkItemError as error:
                log_error(
                    logger,
                    (
                        "WorkItemError | "
                        f"reference={item.reference} | "
                        f"fejl={error}"
                    ),
                )

                item.fail(str(error))

            except Exception as error:
                logger.exception(
                    (
                        "Uventet fejl | "
                        f"reference={item.reference}"
                    )
                )

                try:
                    update_item_data(
                        data,
                        item=item,
                        status="Failed",
                        status_code=str(error),
                        state=(
                            "Fejl: "
                            f"{type(error).__name__}"
                        ),
                    )

                    item.update(data)

                except Exception:
                    log_warning(
                        logger,
                        (
                            "Kunne ikke opdatere "
                            "item med fejlstatus"
                        ),
                    )

                raise

    log_block(
        logger,
        "PROCESS MODE SLUT",
        [
            f"behandlede_items={processed_count}",
        ],
    )


if __name__ == "__main__":
    # --------------------------------------------------------
    # VALIDER KOMBINEREDE MODES
    # --------------------------------------------------------
    #
    # Følgende specialfunktioner må ikke køres samtidig:
    #
    #     --ats-drift
    #     --ats-tidsbesparelse
    #     --ats-tidsbesparelse-local
    #
    # Specialfunktionerne må heller ikke kombineres med
    # --queue.
    #
    selected_special_modes = sum(
        (
            ATS_DRIFT_MODE,
            ATS_TIDSBESPARELSE_MODE,
            ATS_TIDSBESPARELSE_LOCAL_MODE,
        )
    )

    if (
        selected_special_modes > 1
        or (
            QUEUE_MODE
            and selected_special_modes > 0
        )
    ):
        raise ValueError(
            "--queue og specialrapport-flags må ikke "
            "bruges sammen. Vælg kun én af: "
            "--queue, --ats-drift, "
            "--ats-tidsbesparelse eller "
            "--ats-tidsbesparelse-local."
        )

    # --------------------------------------------------------
    # PROGRAMSTART
    # --------------------------------------------------------
    log_info(
        logger,
        (
            "PROGRAM START | "
            f"DEBUG={DEBUG} | "
            f"QUEUE_MODE={QUEUE_MODE} | "
            f"ATS_DRIFT_MODE={ATS_DRIFT_MODE} | "
            "ATS_TIDSBESPARELSE_MODE="
            f"{ATS_TIDSBESPARELSE_MODE} | "
            "ATS_TIDSBESPARELSE_LOCAL_MODE="
            f"{ATS_TIDSBESPARELSE_LOCAL_MODE}"
        ),
    )

    # --------------------------------------------------------
    # ATS-TIDSBESPARELSE, LOKAL UDEN MAIL
    # --------------------------------------------------------
    #
    # Denne mode:
    #
    #     henter regler fra SharePoint
    #     henter completed workitems
    #     opretter Excel-filen
    #     sender ikke mail
    #
    # Automation Server-klienten oprettes ikke, fordi
    # tidsbesparelsesrapporten læser direkte fra databasen.
    #
    if ATS_TIDSBESPARELSE_LOCAL_MODE:
        result = run_ats_tidsbesparelse_report(
            send_email=False,
        )

        log_info(
            logger,
            (
                "ATS TIDSBESPARELSE LOKAL RESULTAT | "
                f"{result}"
            ),
        )

        sys.exit(0)

    # --------------------------------------------------------
    # ATS-TIDSBESPARELSE MED MAIL
    # --------------------------------------------------------
    #
    # Denne mode:
    #
    #     henter regler fra SharePoint
    #     henter completed workitems
    #     opretter Excel-filen
    #     sender rapporten med mail
    #
    if ATS_TIDSBESPARELSE_MODE:
        result = run_ats_tidsbesparelse_report(
            send_email=True,
        )

        log_info(
            logger,
            (
                "ATS TIDSBESPARELSE RESULTAT | "
                f"{result}"
            ),
        )

        sys.exit(0)

    # --------------------------------------------------------
    # ATS-DRIFTSRAPPORT
    # --------------------------------------------------------
    #
    # Denne mode bruger ikke rapportering-workqueue.
    #
    if ATS_DRIFT_MODE:
        result = run_ats_drift_report()

        log_info(
            logger,
            (
                "ATS DRIFTRAPPORT RESULTAT | "
                f"{result}"
            ),
        )

        sys.exit(0)

    # --------------------------------------------------------
    # ALMINDELIG RAPPORTERING
    # --------------------------------------------------------
    #
    # Først her oprettes forbindelsen til Automation Server.
    #
    # Det sker kun, hvis programmet ikke allerede er afsluttet
    # efter en af specialrapporterne ovenfor.
    #
    validate_reports_config()

    ats = AutomationServer.from_environment()

    workqueue = ats.workqueue()

    # --------------------------------------------------------
    # QUEUE-MODE
    # --------------------------------------------------------
    #
    # Produceren kontrollerer rapportdefinitionerne og
    # opretter nye rapporterings-items.
    #
    if QUEUE_MODE:
        asyncio.run(
            populate_queue(
                workqueue,
                debug=DEBUG,
            )
        )

        sys.exit(0)

    # --------------------------------------------------------
    # PROCESS-MODE
    # --------------------------------------------------------
    #
    # Uden --queue eller et specialflag behandles de
    # eksisterende items i rapporteringskøen.
    #
    asyncio.run(
        process_workqueue(
            workqueue,
            debug=DEBUG,
        )
    )