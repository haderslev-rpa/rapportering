# main.py

import asyncio
import logging
import sys

from automation_server_client import (
    AutomationServer,
    WorkItemError,
)

from q_haderslev_vbo.automation_server.ats_update_item_data import update_item_data

from behandel import behandel_item
from config_reports import REPORTS, validate_reports_config
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
from reporting_item_builder import build_report_item_data
from scheduling_should_run import should_run_report
from sharepoint_report_config_repository import (
    find_sharepoint_config_by_rapport_id,
)

# ------------------------------------------------------------
# ✅ CLI flags (runtime-parametre)
# ------------------------------------------------------------
DEBUG = "--debug" in sys.argv
QUEUE_MODE = "--queue" in sys.argv

# ------------------------------------------------------------
# LOGGING (STANDARD)
# DEBUG = mere log
# QUEUE_MODE = ændrer mode
# ------------------------------------------------------------
LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("automation_server_client").setLevel(logging.WARNING)
logging.getLogger("debugpy").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def populate_queue(workqueue, debug):
    """
    Producer mode (opretter rapportering items).
    """

    log_block(
        logger,
        "QUEUE MODE START",
        [
            f"debug={debug}",
            f"antal_rapporter_i_config={len(REPORTS)}",
            f"sys.argv={sys.argv}",
            "Queue vælges via ATS_WORKQUEUE_OVERRIDE i .env",
        ],
    )

    created_count = 0
    skipped_count = 0

    for report in REPORTS:
        rapport_id = report["rapport_id"]

        log_block(
            logger,
            f"STARTER RAPPORTCHECK | rapport_id={rapport_id}",
            [
                f"rapport_navn={report['rapport_navn']}",
                f"kilde_queue={report['kilde_queue']}",
                f"status_filter={report['status_filter']}",
                f"time_field={report['time_field']}",
            ],
        )

        log_dict(logger, "Rapport config", report)

        sharepoint_config = find_sharepoint_config_by_rapport_id(rapport_id)

        if not sharepoint_config:
            skipped_count += 1
            log_warning(
                logger,
                (
                    f"SKIP | Ingen SharePoint config fundet | rapport_id={rapport_id} | "
                    "Husk: rapport_id skal matche SharePoint kolonnen Title"
                ),
            )
            continue

        log_info(
            logger,
            (
                f"SharePoint match | rapport_id={rapport_id} | "
                f"sharepoint_item_id={sharepoint_config.get('id')} | "
                f"title={sharepoint_config.get('titel')} | "
                f"aktiv={sharepoint_config.get('aktiv')} | "
                f"run_now={sharepoint_config.get('run_now')} | "
                f"cron={sharepoint_config.get('cron')}"
            ),
        )

        # -------------------------------------------------
        # HISTORIK
        # -------------------------------------------------
        last_mail_sendt_timestamp = find_last_mail_sendt_timestamp(rapport_id)
        last_rapportering_end = find_last_rapportering_end(rapport_id)

        log_info(
            logger,
            (
                f"Historik | rapport_id={rapport_id} | "
                f"last_mail_sendt_timestamp={last_mail_sendt_timestamp} | "
                f"last_rapportering_end={last_rapportering_end}"
            ),
        )

        should_run, koerselstype, reason = should_run_report(
            cron_text=sharepoint_config.get("cron"),
            run_now=sharepoint_config.get("run_now"),
            aktiv=sharepoint_config.get("aktiv"),
            minimum_dage_efter_sidste_rapport=sharepoint_config.get(
                "minimum_dage_efter_sidste_rapport",
                0,
            ),
            last_mail_sendt_timestamp=last_mail_sendt_timestamp,
            last_rapportering_end=last_rapportering_end,
            debug=debug,  # kun til log-niveau / kompatibilitet
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
                f"SKIP | rapport_id={rapport_id} | årsag={reason}",
            )
            continue

        # -------------------------------------------------
        # RAPPORTPERIODE
        # -------------------------------------------------
        rapportering_start = last_rapportering_end

        if not rapportering_start:
            rapportering_start = report["default_rapportering_start"]
            log_info(
                logger,
                (
                    f"rapportering_start ikke fundet i historik | "
                    f"rapport_id={rapport_id} | "
                    f"bruger_default={rapportering_start}"
                ),
            )
        else:
            log_info(
                logger,
                (
                    f"rapportering_start fundet i historik | "
                    f"rapport_id={rapport_id} | "
                    f"value={rapportering_start}"
                ),
            )

        rapportering_end = get_database_time_minus_seconds(5)
        log_info(
            logger,
            (
                f"rapportering_end beregnet | "
                f"rapport_id={rapport_id} | "
                f"value={rapportering_end}"
            ),
        )

        if str(rapportering_start) >= str(rapportering_end):
            skipped_count += 1
            log_warning(
                logger,
                (
                    f"SKIP | ugyldigt tidsvindue | "
                    f"rapport_id={rapport_id} | "
                    f"rapportering_start={rapportering_start} | "
                    f"rapportering_end={rapportering_end}"
                ),
            )
            continue

        antal_rows = count_workitems_for_report(
            report["kilde_queue"],
            report["status_filter"],
            report["time_field"],
            rapportering_start,
            rapportering_end,
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
            report,
            sharepoint_config,
            rapportering_start,
            rapportering_end,
            antal_rows,
            koerselstype,
        )

        log_dict(logger, "Data til nyt rapportering item", data_json)

        reference = f"{rapport_id}_{data_json['box']['rapportering_end']}"

        log_info(
            logger,
            f"OPRETTER ITEM | rapport_id={rapport_id} | reference={reference}",
        )

        workqueue.add_item(
            data=data_json,
            reference=reference,
        )

        created_count += 1

        log_info(
            logger,
            (
                f"ITEM OPRETTET | rapport_id={rapport_id} | "
                f"reference={reference} | "
                f"antal_rows={antal_rows}"
            ),
        )

        if sharepoint_config.get("run_now") == "Ja":
            from sharepoint_report_config_repository import set_run_now_to_no

            log_info(
                logger,
                (
                    f"Run now = Ja | sætter Run now = Nej | "
                    f"rapport_id={rapport_id} | "
                    f"sharepoint_item_id={sharepoint_config.get('id')}"
                ),
            )
            set_run_now_to_no(sharepoint_config.get("id"))

        log_info(logger, f"SLUT RAPPORTCHECK | rapport_id={rapport_id}")

    log_block(
        logger,
        "QUEUE MODE SLUT",
        [
            f"oprettede_items={created_count}",
            f"skippede_rapporter={skipped_count}",
        ],
    )


async def process_workqueue(workqueue, debug):
    """
    Consumer mode (behandler rapportering items).
    """

    log_block(
        logger,
        "PROCESS MODE START",
        [
            f"debug={debug}",
            f"sys.argv={sys.argv}",
        ],
    )

    processed_count = 0

    for item in workqueue:
        with item:
            data = item.data

            try:
                log_info(logger, f"STARTER ITEM | reference={item.reference}")
                log_dict(logger, "ITEM DATA", data)

                await behandel_item(item)

                item.complete("Completed")
                processed_count += 1

                log_info(logger, f"ITEM COMPLETED | reference={item.reference}")

            except WorkItemError as e:
                log_error(logger, f"WorkItemError | reference={item.reference} | fejl={e}")
                item.fail(str(e))

            except Exception as e:
                log_error(logger, f"Uventet fejl | reference={item.reference} | fejl={e}")

                try:
                    update_item_data(
                        data,
                        item=item,
                        status="Failed",
                        status_code=str(e),
                        state=f"Fejl: {type(e).__name__}",
                    )
                    item.update(data)
                except Exception:
                    log_warning(logger, "Kunne ikke opdatere item med fejlstatus")

                raise

    log_block(
        logger,
        "PROCESS MODE SLUT",
        [
            f"behandlede_items={processed_count}",
        ],
    )


if __name__ == "__main__":
    validate_reports_config()

    log_info(logger, f"PROGRAM START | DEBUG={DEBUG} | QUEUE_MODE={QUEUE_MODE}")

    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()

    # --------------------------------------------------------
    # QUEUE-MODE
    # --------------------------------------------------------
    if QUEUE_MODE:
        asyncio.run(populate_queue(workqueue, debug=DEBUG))
        sys.exit(0)

    # --------------------------------------------------------
    # PROCESS-MODE
    # --------------------------------------------------------
    asyncio.run(process_workqueue(workqueue, debug=DEBUG))