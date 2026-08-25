# test1.py

"""
RAPPORT: TEST1
==============

Denne fil indeholder kun konfigurationen til Test1-rapporten.

Sammenhæng:
    rapport_id:
        Skal matche SharePoint-kolonnen "Title" præcist.

    kilde_queue:
        Skal matche workqueue.name i PostgreSQL præcist.

    status_filter:
        Bruges i den faste grund-query.

    time_field:
        Bestemmer hvilket teknisk databasefelt rapportperioden
        anvendes på.

Test1 har ingen ekstra SQL-filtrering og anvender derfor:

    extra_where_sql = ""
    sql_parameters = {}
    select_fields = []

Test1 bruger kun rapportmotorens faste standardfelter:

    id
    reference
    status
    message
    created_at
    updated_at
    started_at
    queue_name
    data
"""


REPORT = {
    # ---------------------------------------------------------
    # IDENTITET
    # ---------------------------------------------------------
    "rapport_id": "Test1",

    "rapport_navn": "Test1",

    # ---------------------------------------------------------
    # FAST SIKKER GRUND-QUERY
    # ---------------------------------------------------------
    "kilde_queue": "Test1",

    "status_filter": "COMPLETED",

    "time_field": "updated_at",

    # Bruges kun hvis der ikke findes et tidligere
    # rapportering_end for rapport_id=Test1.
    "default_rapportering_start": "2026-04-22 14:01:00",

    # ---------------------------------------------------------
    # RAPPORTENS EKSTRA SQL
    # ---------------------------------------------------------

    # Test1 har ingen ekstra WHERE-betingelser.
    "extra_where_sql": "",

    # Test1 har ingen ekstra SQL-parametre.
    "sql_parameters": {},

    # Test1 bruger kun rapportmotorens standardfelter.
    "select_fields": [],

    # ---------------------------------------------------------
    # MAIL
    # ---------------------------------------------------------
    "afsender_mail": "robot-data@haderslev.dk",

    "mail_subject": "Rapport - Test1",

    "mail_body": (
        "Hej\n\n"
        "Rapporten er vedhæftet.\n\n"
        "Rapport: {rapport_navn}\n"
        "Periode: {rapportering_start_dk} til "
        "{rapportering_end_dk}\n"
        "Antal rows: {antal_rows}\n\n"
        "Venlig hilsen\n"
        "Robotten"
    ),

    # ---------------------------------------------------------
    # EXCEL
    # ---------------------------------------------------------
    "excel_file_prefix": "Test1",

    "columns": [
        {
            "header": "Id",
            "source": "id",
            "type": "integer",
        },
        {
            "header": "Reference",
            "source": "reference",
            "type": "text",
        },
        {
            "header": "Status",
            "source": "status",
            "type": "text",
        },
        {
            "header": "Message",
            "source": "message",
            "type": "text",
        },
        {
            "header": "Oprettet",
            "source": "created_at",
            "type": "datetime",
        },
        {
            "header": "Opdateret",
            "source": "updated_at",
            "type": "datetime",
        },
        {
            "header": "Startet",
            "source": "started_at",
            "type": "datetime",
        },
        {
            "header": "Queue",
            "source": "queue_name",
            "type": "text",
        },

        # data er et standardfelt med hele workitemets JSON.
        # Mapperen kan derfor læse nested felter som data.cpr.
        {
            "header": "CPR",
            "source": "data.cpr",
            "type": "text",
        },
        {
            "header": "Type",
            "source": "data.type",
            "type": "text",
        },
        {
            "header": "Note",
            "source": "data.note",
            "type": "text",
        },
    ],
}