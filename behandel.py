# behandel.py

import logging

from q_haderslev_vbo.automation_server.ats_update_item_data import update_item_data

from config_reports import get_report_by_id
from database_workitems_repository import fetch_workitems_for_report
from reporting_data_mapper import map_rows_to_excel_dicts
from reporting_excel_builder import create_excel_report
from reporting_item_builder import reorder_report_box
from time_helper import (
    database_window_to_danish_string,
    now_danish_string,
)

logger = logging.getLogger(__name__)


def send_mail(user_mail, mail):
    """
    Fake mail funktion (genbrugelig kodeblok)

    ✅ Denne funktion sender IKKE mail
    ✅ Den printer hvad der ville blive sendt
    ✅ Bruges til test uden Outlook

    🔴 TODO:
    Erstat med rigtig send_mail
    """

    print("\n================= FAKE MAIL =================")
    print(f"Fra: {user_mail}")
    print(f"Til: {mail.get('to')}")
    print(f"Cc: {mail.get('cc')}")
    print(f"Bcc: {mail.get('bcc')}")
    print(f"Emne: {mail.get('subject')}")
    print(f"Body:\n{mail.get('body')}")
    print(f"Attachments: {mail.get('attachments')}")
    print("=============================================\n")

    logger.info("FAKE MAIL sendt (kun print)")


async def behandel_item(item):
    """
    Behandler ét rapportering item.

    funktion (genbrugelig kodeblok)
    """

    data = item.data
    box = data.get("box", {})

    rapport_id = box.get("rapport_id")

    if not rapport_id:
        raise ValueError("rapport_id mangler i item.data['box']")

    report = get_report_by_id(rapport_id)

    if not report:
        raise ValueError(f"Ukendt rapport_id: {rapport_id}")

    class States:
        HENT_DATA = "1.0 Data hentet"
        INGEN_ROWS = "1.5 Ingen rows"
        OPRET_EXCEL = "2.0 Excel oprettet"
        SEND_MAIL = "3.0 Mail sendt"

    def mangler_state(state, step):
        states = data.get("state", [])
        match = next((s for s in states if state in s), None)

        if match:
            log_step(step, f'Skip "{match}"')
            return False

        return True

    def set_state(state):
        data["box"] = reorder_report_box(data.get("box", {}))
        update_item_data(data, item=item, state=state)

    def log_step(step, text):
        logger.info(f"[{step}] {text}")

    # ==========================================================
    # STEP 1: HENT_DATA
    # ==========================================================
    step = "HENT_DATA"
    state = getattr(States, step)

    rows = []

    if mangler_state(state, step):
        log_step(step, "Start")

        data["box"] = reorder_report_box(data.get("box", {}))

        update_item_data(
            data,
            item=item,
            status="Processing",
            status_code="Henter data",
        )

        rows = fetch_workitems_for_report(
            box["kilde_queue"],
            box["status_filter"],
            box["time_field"],
            box["rapportering_start"],
            box["rapportering_end"],
        )

        data["box"]["excel_antal_rows"] = len(rows)
        data["box"] = reorder_report_box(data.get("box", {}))

        log_step(step, f"Rows hentet: {len(rows)}")

        update_item_data(data, item=item)
        set_state(state)
    else:
        rows = fetch_workitems_for_report(
            box["kilde_queue"],
            box["status_filter"],
            box["time_field"],
            box["rapportering_start"],
            box["rapportering_end"],
        )

    # ==========================================================
    # STEP 1.5: INGEN_ROWS
    # ==========================================================
    if len(rows) == 0:
        step = "INGEN_ROWS"
        state = getattr(States, step)

        if mangler_state(state, step):
            log_step(step, "Ingen rows - ingen mail")

            data["box"]["mail_sendt"] = False
            data["box"]["mail_sprunget_over"] = True
            data["box"]["mail_sprunget_over_aarsag"] = "Ingen rows"
            data["box"]["afsluttet_tidspunkt"] = now_danish_string()
            data["box"] = reorder_report_box(data.get("box", {}))

            update_item_data(
                data,
                item=item,
                status="Completed",
                status_code="Ingen rows",
            )

            set_state(state)

        return

    # ==========================================================
    # STEP 2: OPRET_EXCEL
    # ==========================================================
    step = "OPRET_EXCEL"
    state = getattr(States, step)

    excel_file = None

    if mangler_state(state, step):
        log_step(step, "Start")

        excel_rows = map_rows_to_excel_dicts(rows, report["columns"])

        excel_file = create_excel_report(
            box["rapport_navn"],
            report["excel_file_prefix"],
            excel_rows,
        )

        data["box"]["excel_fil"] = str(excel_file)
        data["box"] = reorder_report_box(data.get("box", {}))

        log_step(step, f"Excel oprettet: {excel_file}")

        update_item_data(
            data,
            item=item,
            status="Processing",
            status_code="Excel oprettet",
        )

        set_state(state)
    else:
        excel_file = box.get("excel_fil")

    # ==========================================================
    # STEP 3: SEND_MAIL
    # ==========================================================
    step = "SEND_MAIL"
    state = getattr(States, step)

    if mangler_state(state, step):
        log_step(step, "Start")

        mail_config = data["box"].get("mail", {})

        # Mail får dansk visning af rapportperioden,
        # men item-data beholder de tekniske database-felter.
        mail_context = dict(data["box"])
        mail_context["rapportering_start_dk"] = database_window_to_danish_string(
            data["box"].get("rapportering_start")
        )
        mail_context["rapportering_end_dk"] = database_window_to_danish_string(
            data["box"].get("rapportering_end")
        )

        mail_subject = report["mail_subject"].format(**mail_context)
        mail_body = report["mail_body"].format(**mail_context)

        send_mail(
            user_mail=report["afsender_mail"],
            mail={
                "subject": mail_subject,
                "body": mail_body,
                "to": mail_config.get("to", []),
                "cc": mail_config.get("cc", []),
                "bcc": mail_config.get("bcc", []),
                "attachments": [str(excel_file)],
            },
        )

        data["box"]["mail_sendt"] = True
        data["box"]["mail_sprunget_over"] = False
        data["box"]["mail_sprunget_over_aarsag"] = None
        data["box"]["mail_sendt_tidspunkt"] = now_danish_string()
        data["box"]["afsluttet_tidspunkt"] = now_danish_string()
        data["box"] = reorder_report_box(data.get("box", {}))

        update_item_data(
            data,
            item=item,
            status="Completed",
            status_code="Mail sendt (FAKE)",
        )

        set_state(state)