# report_lukning_af_personalesager.py

"""
RAPPORT: LUKNING AF PERSONALESAGER
==================================

Denne rapport finder completed items fra køen:

    lukning-af-personalesager

Rapporten er bevidst meget simpel.

Den medtager kun:

    Reference

fra alle completed items i rapportperioden.

Der anvendes ingen ekstra SQL-filtre.

Rapportmotorens faste filtre bruges:

    q.name = kilde_queue

    w.status = status_filter

    w.updated_at > rapportering_start

    w.updated_at <= rapportering_end

Excel-filen indeholder kun én kolonne:

    Reference
"""


REPORT = {
    # ---------------------------------------------------------
    # IDENTITET
    # ---------------------------------------------------------

    "rapport_id": "lukning-af-personalesager",

    "rapport_navn": (
        "Lukning af personalesager"
    ),

    # ---------------------------------------------------------
    # FAST SIKKER GRUND-QUERY
    # ---------------------------------------------------------

    "kilde_queue": "lukning-af-personalesager",

    "status_filter": "COMPLETED",

    "time_field": "updated_at",

    "default_rapportering_start": (
        "2026-09-01 00:00:00"
    ),

    # ---------------------------------------------------------
    # INGEN EKSTRA SQL
    # ---------------------------------------------------------

    "extra_where_sql": "",

    "sql_parameters": {},

    # ---------------------------------------------------------
    # INGEN EKSTRA FELTER
    # ---------------------------------------------------------

    "select_fields": [],

    # ---------------------------------------------------------
    # MAIL
    # ---------------------------------------------------------

    "afsender_mail": "robot-data@haderslev.dk",

    "mail_subject": (
        "Rapport - Lukning af personalesager"
    ),

    "mail_body": (
        "Hej\n\n"
        "Vedhæftet er rapporten over completed "
        "items fra processen "
        "'lukning-af-personalesager'.\n\n"
        "Rapport: {rapport_navn}\n"
        "Periode: {rapportering_start_dk} til "
        "{rapportering_end_dk}\n"
        "Antal items: {antal_rows}\n\n"
        "Venlig hilsen\n"
        "Robotten"
    ),

    # ---------------------------------------------------------
    # EXCEL
    # ---------------------------------------------------------

    "excel_file_prefix": (
        "Lukning_af_personalesager"
    ),

    "columns": [
        {
            "header": "Reference",
            "source": "reference",
            "type": "text",
        },
    ],
}