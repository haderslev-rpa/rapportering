# reporting_item_builder.py

from q_haderslev_vbo.automation_server.ats_update_item_data import update_item_data

from time_helper import (
    format_database_window_datetime,
    now_danish_string,
)

SHAREPOINT_SITE_NAME = "Automatisering"
SHAREPOINT_LIST_NAME = "Rapportering opsætning"


def build_report_item_data(
    report,
    sharepoint_config,
    rapportering_start,
    rapportering_end,
    antal_rows,
    koerselstype,
):
    """
    Bygger data til rapportering item.

    funktion (genbrugelig kodeblok)

    VIGTIGT:
    - rapportering_start og rapportering_end er TEKNISKE database-felter.
    - De skal IKKE oversættes til dansk visning i item-data.
    - Dansk visning bruges kun til menneske-felter:
        - oprettet_tidspunkt
        - afsluttet_tidspunkt
        - mail_sendt_tidspunkt
        - Excel-filnavn
        - mail-brødtekst
    """

    data_json = {}

    box = {
        # -------------------------------------------------
        # IDENTITET
        # -------------------------------------------------
        "rapport_id": report["rapport_id"],
        "rapport_navn": report["rapport_navn"],

        # -------------------------------------------------
        # KILDE / FILTER
        # -------------------------------------------------
        "kilde_queue": report["kilde_queue"],
        "status_filter": report["status_filter"],
        "time_field": report["time_field"],

        # -------------------------------------------------
        # RAPPORTPERIODE
        # -------------------------------------------------
        # TEKNISK DATABASE-VINDUE
        "rapportering_start": format_database_window_datetime(rapportering_start),
        "rapportering_end": format_database_window_datetime(rapportering_end),

        # -------------------------------------------------
        # ANTAL
        # -------------------------------------------------
        "antal_rows": antal_rows,
        "excel_antal_rows": None,

        # -------------------------------------------------
        # EXCEL
        # -------------------------------------------------
        "excel_fil": None,

        # -------------------------------------------------
        # MAIL
        # -------------------------------------------------
        "mail": {
            "from_user": report["afsender_mail"],
            "to": sharepoint_config.get("til", []),
            "cc": sharepoint_config.get("cc", []),
            "bcc": sharepoint_config.get("bcc", []),
        },
        "mail_sendt": False,
        "mail_sendt_tidspunkt": None,
        "mail_sprunget_over": False,
        "mail_sprunget_over_aarsag": None,

        # -------------------------------------------------
        # SHAREPOINT
        # -------------------------------------------------
        "sharepoint": {
            "site_name": SHAREPOINT_SITE_NAME,
            "list_name": SHAREPOINT_LIST_NAME,
            "item_id": sharepoint_config.get("id"),
        },

        # -------------------------------------------------
        # META
        # -------------------------------------------------
        "koerselstype": koerselstype,
        "data_storage": "database_window",
        "data_note": (
            "Data er ikke gemt i queue item. "
            "Rapporten genskabes fra databasen via rapportering_start og rapportering_end."
        ),
        "oprettet_tidspunkt": now_danish_string(),
        "afsluttet_tidspunkt": None,
    }

    update_item_data(
        data_json,
        box_updates=box,
        update=False,
    )

    data_json["box"] = reorder_report_box(data_json["box"])

    return data_json


def reorder_report_box(box):
    """
    Returnerer box i fast logisk rækkefølge.

    funktion (genbrugelig kodeblok)
    """

    if not isinstance(box, dict):
        return box

    reordered = {
        "rapport_id": box.get("rapport_id"),
        "rapport_navn": box.get("rapport_navn"),

        "kilde_queue": box.get("kilde_queue"),
        "status_filter": box.get("status_filter"),
        "time_field": box.get("time_field"),

        # TEKNISK DATABASE-VINDUE
        "rapportering_start": box.get("rapportering_start"),
        "rapportering_end": box.get("rapportering_end"),

        "antal_rows": box.get("antal_rows"),
        "excel_antal_rows": box.get("excel_antal_rows"),

        "excel_fil": box.get("excel_fil"),

        "mail": _reorder_mail_box(box.get("mail", {})),
        "mail_sendt": box.get("mail_sendt"),
        "mail_sendt_tidspunkt": box.get("mail_sendt_tidspunkt"),
        "mail_sprunget_over": box.get("mail_sprunget_over"),
        "mail_sprunget_over_aarsag": box.get("mail_sprunget_over_aarsag"),

        "sharepoint": _reorder_sharepoint_box(box.get("sharepoint", {})),

        "koerselstype": box.get("koerselstype"),
        "data_storage": box.get("data_storage"),
        "data_note": box.get("data_note"),
        "oprettet_tidspunkt": box.get("oprettet_tidspunkt"),
        "afsluttet_tidspunkt": box.get("afsluttet_tidspunkt"),
    }

    return reordered


def _reorder_mail_box(mail_box):
    if not isinstance(mail_box, dict):
        return mail_box

    return {
        "from_user": mail_box.get("from_user"),
        "to": mail_box.get("to", []),
        "cc": mail_box.get("cc", []),
        "bcc": mail_box.get("bcc", []),
    }


def _reorder_sharepoint_box(sharepoint_box):
    if not isinstance(sharepoint_box, dict):
        return sharepoint_box

    return {
        "site_name": sharepoint_box.get("site_name"),
        "list_name": sharepoint_box.get("list_name"),
        "item_id": sharepoint_box.get("item_id"),
    }