# config_reports.py

"""
Rapportopsætning i kode.

VIGTIGT:
- rapport_id SKAL være præcis samme værdi som SharePoint-kolonnen "Title"
  i listen "Rapportering opsætning".
- SharePoint styrer:
    - Til
    - Cc
    - Bcc
    - Cron
    - Run now
    - Aktiv
    - Minimum dage efter sidste rapport

Denne fil styrer:
- rapport_navn
- kilde_queue
- status_filter
- time_field
- default_rapportering_start
- afsender_mail
- mail_subject
- mail_body
- columns

VIGTIGT OM TIDSFELTER:
- rapportering_start og rapportering_end er TEKNISKE database-felter.
- De må IKKE pyntes til dansk visning i item-data.
- Dansk visning bruges kun til menneske-felter som:
    - oprettet_tidspunkt
    - afsluttet_tidspunkt
    - mail_sendt_tidspunkt
    - Excel-filnavn
    - mail-brødtekst
"""

REPORTS = [
    {
        "rapport_id": "Test1",
        "rapport_navn": "Test1",
        "kilde_queue": "Test1",
        "status_filter": "COMPLETED",
        "time_field": "updated_at",
        "default_rapportering_start": "2026-04-22 14:01:00",
        "afsender_mail": "rujo@haderslev.dk",
        "mail_subject": "Rapport - Test1",
        "mail_body": (
            "Hej\n\n"
            "Rapporten er vedhæftet.\n\n"
            "Rapport: {rapport_navn}\n"
            "Periode: {rapportering_start_dk} til {rapportering_end_dk}\n"
            "Antal rows: {antal_rows}\n\n"
            "Venlig hilsen\n"
            "Robotten"
        ),
        "excel_file_prefix": "Test1",
        "columns": [
            {"header": "Id", "source": "id"},
            {"header": "Reference", "source": "reference"},
            {"header": "Status", "source": "status"},
            {"header": "Message", "source": "message"},
            {"header": "Created at", "source": "created_at"},
            {"header": "Updated at", "source": "updated_at"},
            {"header": "Started at", "source": "started_at"},
            {"header": "Queue", "source": "queue_name"},
            {"header": "CPR", "source": "data.cpr"},
            {"header": "Type", "source": "data.type"},
            {"header": "Note", "source": "data.note"},
        ],
    }
]


def get_report_by_id(rapport_id):
    """
    Finder rapportopsætning ud fra rapport_id.

    funktion (genbrugelig kodeblok)
    """

    for report in REPORTS:
        if report.get("rapport_id") == rapport_id:
            return report

    return None


def validate_reports_config():
    """
    Validerer rapportopsætning ved opstart.

    funktion (genbrugelig kodeblok)

    Stopper tidligt hvis config er ugyldig.
    """

    if not isinstance(REPORTS, list):
        raise ValueError("REPORTS skal være en liste")

    if not REPORTS:
        raise ValueError("REPORTS er tom")

    seen_ids = set()

    required_keys = [
        "rapport_id",
        "rapport_navn",
        "kilde_queue",
        "status_filter",
        "time_field",
        "default_rapportering_start",
        "afsender_mail",
        "mail_subject",
        "mail_body",
        "excel_file_prefix",
        "columns",
    ]

    allowed_time_fields = ["created_at", "updated_at", "started_at"]

    for index, report in enumerate(REPORTS, start=1):
        if not isinstance(report, dict):
            raise ValueError(f"Rapport nr. {index} er ikke en dict")

        for key in required_keys:
            if key not in report:
                raise ValueError(
                    f"Rapport nr. {index} mangler nøgle: {key}"
                )

        rapport_id = report["rapport_id"]

        if not rapport_id:
            raise ValueError(f"Rapport nr. {index} har tom rapport_id")

        if rapport_id in seen_ids:
            raise ValueError(f"Dublet rapport_id fundet: {rapport_id}")

        seen_ids.add(rapport_id)

        if report["time_field"] not in allowed_time_fields:
            raise ValueError(
                f"Rapport {rapport_id} har ugyldigt time_field: {report['time_field']}"
            )

        if not isinstance(report["columns"], list):
            raise ValueError(f"Rapport {rapport_id} har columns som ikke er en liste")

        if not report["columns"]:
            raise ValueError(f"Rapport {rapport_id} har tom columns liste")

        for col_index, column in enumerate(report["columns"], start=1):
            if not isinstance(column, dict):
                raise ValueError(
                    f"Rapport {rapport_id} har ugyldig column nr. {col_index}"
                )

            if "header" not in column or "source" not in column:
                raise ValueError(
                    f"Rapport {rapport_id} har column nr. {col_index} uden header/source"
                )