# reporting_item_builder.py

from copy import deepcopy

from q_haderslev_vbo.automation_server.ats_update_item_data import (
    update_item_data,
)

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
    Bygger data til et rapportering-item.

    Rapportens SQL-opskrift og Excel-kolonner fryses i itemet.
    Consumeren bruger derfor samme definition som produceren.

    Output:
        dict:
            Komplet item-data med box, status, state og defer.
    """

    data_json = {}

    report_definition = {
        "extra_where_sql": report.get(
            "extra_where_sql",
            "",
        ),
        "sql_parameters": deepcopy(
            report.get(
                "sql_parameters",
                {},
            )
        ),
        "select_fields": deepcopy(
            report.get(
                "select_fields",
                [],
            )
        ),
        "columns": deepcopy(
            report.get(
                "columns",
                [],
            )
        ),
        "excel_file_prefix": report.get(
            "excel_file_prefix",
            report["rapport_id"],
        ),
    }

    box = {
        "rapport_id": report["rapport_id"],
        "rapport_navn": report["rapport_navn"],

        "kilde_queue": report["kilde_queue"],
        "status_filter": report["status_filter"],
        "time_field": report["time_field"],

        # TEKNISKE DATABASEVÆRDIER.
        # Må ikke konverteres til dansk visning her.
        "rapportering_start": (
            format_database_window_datetime(
                rapportering_start
            )
        ),
        "rapportering_end": (
            format_database_window_datetime(
                rapportering_end
            )
        ),

        "antal_rows": antal_rows,
        "excel_antal_rows": None,
        "excel_fil": None,

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

        "sharepoint": {
            "site_name": SHAREPOINT_SITE_NAME,
            "list_name": SHAREPOINT_LIST_NAME,
            "item_id": sharepoint_config.get("id"),
        },

        # Frossen rapportopskrift.
        "report_definition": report_definition,

        "koerselstype": koerselstype,
        "data_storage": "database_window",
        "data_note": (
            "Data er ikke gemt i queue item. "
            "Rapporten genskabes fra databasen via "
            "rapportering_start, rapportering_end og "
            "den frosne report_definition."
        ),

        "oprettet_tidspunkt": now_danish_string(),
        "afsluttet_tidspunkt": None,
    }

    update_item_data(
        data_json,
        box_updates=box,
        update=False,
    )

    data_json["box"] = reorder_report_box(
        data_json["box"]
    )

    return data_json


def reorder_report_box(box):
    """
    Returnerer box i fast logisk rækkefølge.

    Ukendte ekstra felter bevares til sidst.

    Output:
        dict:
            Ny dictionary i den ønskede rækkefølge.
    """

    if not isinstance(box, dict):
        return box

    ordered_keys = [
        "rapport_id",
        "rapport_navn",
        "kilde_queue",
        "status_filter",
        "time_field",
        "rapportering_start",
        "rapportering_end",
        "antal_rows",
        "excel_antal_rows",
        "excel_fil",
        "mail",
        "mail_sendt",
        "mail_sendt_tidspunkt",
        "mail_sprunget_over",
        "mail_sprunget_over_aarsag",
        "sharepoint",
        "report_definition",
        "koerselstype",
        "data_storage",
        "data_note",
        "oprettet_tidspunkt",
        "afsluttet_tidspunkt",
    ]

    reordered = {}

    for key in ordered_keys:
        if key in box:
            reordered[key] = box.get(key)

    # Bevar eventuelle fremtidige felter.
    for key, value in box.items():
        if key not in reordered:
            reordered[key] = value

    return reordered