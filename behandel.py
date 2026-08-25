# behandel.py

import logging
from pathlib import Path

from q_haderslev_vbo.automation_server.ats_update_item_data import (
    update_item_data,
)
from q_outlook_api.functionality.mail_api import (
    send_mail,
)

from config_reports import get_report_by_id
from database_workitems_repository import (
    fetch_workitems_for_report,
)
from reporting_data_mapper import (
    map_rows_to_excel_dicts,
)
from reporting_excel_builder import (
    create_excel_report,
)
from reporting_item_builder import (
    reorder_report_box,
)
from time_helper import (
    database_window_to_danish_string,
    now_danish_string,
)

logger = logging.getLogger(__name__)


async def behandel_item(item):
    """
    Behandler ét rapportering-item.

    Consumeren bruger den frosne report_definition fra itemet.
    Dermed bruges samme SQL- og Excel-definition som ved
    producerens optælling.

    Flow:
        1. Hent rapportens data fra databasen.
        2. Stop uden mail hvis rapporten har 0 rows.
        3. Opret Excel-filen.
        4. Send mailen med Excel-filen som vedhæftning.
        5. Markér først mailen som sendt efter vellykket
           svar fra Microsoft Graph.

    Output:
        None.

    Fejl:
        Fejl fra database, Excel eller Microsoft Graph sendes
        videre til fejlhåndteringen i main.py.

        Hvis Microsoft Graph fejler, sættes:
            mail_sendt

        ikke til True.
    """

    data = item.data
    box = data.get("box", {})

    rapport_id = box.get("rapport_id")

    if not rapport_id:
        raise ValueError(
            "rapport_id mangler i item.data['box']"
        )

    report = get_report_by_id(
        rapport_id
    )

    if not report:
        raise ValueError(
            f"Ukendt rapport_id: {rapport_id}"
        )

    # ----------------------------------------------------------
    # FROSSEN RAPPORTDEFINITION
    # ----------------------------------------------------------
    #
    # Nye items indeholder den rapportdefinition, der var aktiv,
    # da produceren oprettede itemet.
    #
    # Fallback til Git-konfigurationen gør ældre items kompatible.
    report_definition = box.get(
        "report_definition"
    )

    if not isinstance(
        report_definition,
        dict,
    ):
        report_definition = {
            "extra_where_sql": report.get(
                "extra_where_sql",
                "",
            ),
            "sql_parameters": report.get(
                "sql_parameters",
                {},
            ),
            "select_fields": report.get(
                "select_fields",
                [],
            ),
            "columns": report.get(
                "columns",
                [],
            ),
            "excel_file_prefix": report.get(
                "excel_file_prefix",
                rapport_id,
            ),
        }

    extra_where_sql = report_definition.get(
        "extra_where_sql",
        "",
    )

    sql_parameters = report_definition.get(
        "sql_parameters",
        {},
    )

    select_fields = report_definition.get(
        "select_fields",
        [],
    )

    columns = report_definition.get(
        "columns",
        report.get("columns", []),
    )

    excel_file_prefix = report_definition.get(
        "excel_file_prefix",
        report.get(
            "excel_file_prefix",
            rapport_id,
        ),
    )

    # ==========================================================
    # STATES
    # ==========================================================
    class States:
        HENT_DATA = "1.0 Data hentet"
        INGEN_ROWS = "1.5 Ingen rows"
        OPRET_EXCEL = "2.0 Excel oprettet"
        SEND_MAIL = "3.0 Mail sendt"

    # ==========================================================
    # HELPERS
    # ==========================================================
    def mangler_state(
        state,
        step,
    ):
        """
        Kontrollerer om et trin allerede er udført.

        Output:
            bool:
                True hvis state mangler.
                False hvis state allerede findes.
        """

        states = data.get("state", [])

        match = next(
            (
                state_line
                for state_line in states
                if state in state_line
            ),
            None,
        )

        if match:
            log_step(
                step,
                f'Skip "{match}"',
            )
            return False

        return True

    def set_state(state):
        """
        Gemmer state og holder box i fast rækkefølge.

        Output:
            None.
        """

        data["box"] = reorder_report_box(
            data.get("box", {})
        )

        update_item_data(
            data,
            item=item,
            state=state,
        )

    def log_step(
        step,
        text,
    ):
        """
        Logger rapporteringstrinnet.

        Output:
            None.
        """

        logger.info(
            f"[{step}] {text}"
        )

    # ==========================================================
    # STEP 1: HENT DATA
    # ==========================================================
    step = "HENT_DATA"
    state = getattr(
        States,
        step,
    )

    rows = []

    if mangler_state(
        state,
        step,
    ):
        log_step(
            step,
            "Start",
        )

        update_item_data(
            data,
            item=item,
            status="Processing",
            status_code="Henter data",
        )

        rows = fetch_workitems_for_report(
            kilde_queue=box["kilde_queue"],
            status_filter=box["status_filter"],
            time_field=box["time_field"],
            rapportering_start=box[
                "rapportering_start"
            ],
            rapportering_end=box[
                "rapportering_end"
            ],
            extra_where_sql=extra_where_sql,
            sql_parameters=sql_parameters,
            select_fields=select_fields,
        )

        data["box"][
            "excel_antal_rows"
        ] = len(rows)

        log_step(
            step,
            f"Rows hentet: {len(rows)}",
        )

        update_item_data(
            data,
            item=item,
        )

        set_state(state)

    else:
        rows = fetch_workitems_for_report(
            kilde_queue=box["kilde_queue"],
            status_filter=box["status_filter"],
            time_field=box["time_field"],
            rapportering_start=box[
                "rapportering_start"
            ],
            rapportering_end=box[
                "rapportering_end"
            ],
            extra_where_sql=extra_where_sql,
            sql_parameters=sql_parameters,
            select_fields=select_fields,
        )

    # ==========================================================
    # STEP 1.5: INGEN ROWS
    # ==========================================================
    if len(rows) == 0:
        step = "INGEN_ROWS"
        state = getattr(
            States,
            step,
        )

        if mangler_state(
            state,
            step,
        ):
            log_step(
                step,
                "Ingen rows - ingen mail",
            )

            data["box"]["mail_sendt"] = False
            data["box"][
                "mail_sprunget_over"
            ] = True
            data["box"][
                "mail_sprunget_over_aarsag"
            ] = (
                "Ingen rows matchede rapportens "
                "status-, periode- og SQL-filter"
            )
            data["box"][
                "afsluttet_tidspunkt"
            ] = now_danish_string()

            update_item_data(
                data,
                item=item,
                status="Completed",
                status_code=(
                    "Ingen rows - ingen mail sendt"
                ),
            )

            set_state(state)

        return

    # ==========================================================
    # STEP 2: OPRET EXCEL
    # ==========================================================
    step = "OPRET_EXCEL"
    state = getattr(
        States,
        step,
    )

    excel_file = None

    if mangler_state(
        state,
        step,
    ):
        log_step(
            step,
            "Start",
        )

        excel_rows = map_rows_to_excel_dicts(
            rows=rows,
            columns=columns,
        )

        excel_file = create_excel_report(
            rapport_navn=box["rapport_navn"],
            excel_file_prefix=excel_file_prefix,
            rows=excel_rows,
            columns=columns,
        )

        data["box"]["excel_fil"] = str(
            excel_file
        )

        log_step(
            step,
            f"Excel oprettet: {excel_file}",
        )

        update_item_data(
            data,
            item=item,
            status="Processing",
            status_code="Excel oprettet",
        )

        set_state(state)

    else:
        excel_file = data["box"].get(
            "excel_fil"
        )

    # ==========================================================
    # STEP 3: SEND MAIL
    # ==========================================================
    step = "SEND_MAIL"
    state = getattr(
        States,
        step,
    )

    if mangler_state(
        state,
        step,
    ):
        log_step(
            step,
            "Start",
        )

        mail_config = data["box"].get(
            "mail",
            {},
        )

        # ------------------------------------------------------
        # VALIDÉR EXCEL-FILEN
        # ------------------------------------------------------
        if not excel_file:
            raise ValueError(
                "Excel-filstien mangler før mailforsendelse"
            )

        excel_path = Path(
            excel_file
        )

        if not excel_path.is_file():
            raise FileNotFoundError(
                "Excel-filen findes ikke før mailforsendelse: "
                f"{excel_path}"
            )

        # ------------------------------------------------------
        # BYG MAIL-KONTEKST
        # ------------------------------------------------------
        #
        # Rapportering_start og rapportering_end forbliver
        # tekniske databaseværdier i queue-itemet.
        #
        # Kun mailteksten får den danske visning.
        mail_context = dict(
            data["box"]
        )

        mail_context[
            "rapportering_start_dk"
        ] = database_window_to_danish_string(
            data["box"].get(
                "rapportering_start"
            )
        )

        mail_context[
            "rapportering_end_dk"
        ] = database_window_to_danish_string(
            data["box"].get(
                "rapportering_end"
            )
        )

        mail_subject = report[
            "mail_subject"
        ].format(**mail_context)

        mail_body = report[
            "mail_body"
        ].format(**mail_context)

        sender_mail = (
            mail_config.get("from_user")
            or report["afsender_mail"]
        )

        recipients_to = mail_config.get(
            "to",
            [],
        )

        recipients_cc = mail_config.get(
            "cc",
            [],
        )

        recipients_bcc = mail_config.get(
            "bcc",
            [],
        )

        if not (
            recipients_to
            or recipients_cc
            or recipients_bcc
        ):
            raise ValueError(
                "Mailen har ingen modtagere i To, Cc eller Bcc"
            )

        logger.info(
            (
                "[SEND_MAIL] Sender mail | "
                f"fra={sender_mail} | "
                f"to={recipients_to} | "
                f"cc={recipients_cc} | "
                f"bcc={recipients_bcc} | "
                f"attachment={excel_path}"
            )
        )

        # ------------------------------------------------------
        # SEND RIGTIG MAIL
        # ------------------------------------------------------
        #
        # Funktionen returnerer først True, når Microsoft Graph
        # har accepteret sendMail-kaldet.
        mail_sent = send_mail(
            user_mail=sender_mail,
            mail={
                "subject": mail_subject,

                # Skabelonerne er i dag almindelig tekst.
                # Derfor sendes body som Text og ikke HTML.
                "content_type": "Text",

                "body": mail_body,
                "to": recipients_to,
                "cc": recipients_cc,
                "bcc": recipients_bcc,

                # Outlook gemmer en kopi i Sendt post.
                "save_to_sent_items": True,

                # q-outlook-api læser selv filen og konverterer
                # den til Microsoft Graph fileAttachment.
                "attachments": [
                    excel_path
                ],
            },
        )

        if mail_sent is not True:
            raise RuntimeError(
                "send_mail returnerede ikke True"
            )

        logger.info(
            (
                "[SEND_MAIL] Microsoft Graph accepterede "
                f"mailforsendelsen | attachment={excel_path.name}"
            )
        )

        # ------------------------------------------------------
        # OPDATÉR ITEM EFTER VELLYKKET MAIL
        # ------------------------------------------------------
        data["box"]["mail_sendt"] = True
        data["box"][
            "mail_sprunget_over"
        ] = False
        data["box"][
            "mail_sprunget_over_aarsag"
        ] = None
        data["box"][
            "mail_sendt_tidspunkt"
        ] = now_danish_string()
        data["box"][
            "afsluttet_tidspunkt"
        ] = now_danish_string()

        update_item_data(
            data,
            item=item,
            status="Completed",
            status_code="Mail sendt",
        )

        set_state(state)