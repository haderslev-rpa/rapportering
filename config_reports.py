# config_reports.py

"""
FÆLLES RAPPORTREGISTER
======================

Denne fil er den fælles indgang til alle rapportkonfigurationer.

Resten af rapportmotoren importerer fortsat:

    REPORTS
    get_report_by_id
    validate_reports_config

De enkelte rapporter ligger i separate Python-filer:

    report_test1.py
    report_forebyggende_hjemmebesoeg.py

Hver rapportfil skal eksportere præcis én dictionary:

    REPORT = {
        ...
    }

SÅDAN TILFØJES EN NY RAPPORT
=============================

1. Opret en ny Python-fil med et sigende navn.

   Eksempel:

       ny_rapport.py

2. Opret rapportdefinitionen i filen:

       REPORT = {
           ...
       }

3. Importér rapporten i denne fil:

       from ny_rapport import REPORT as NY_RAPPORT

4. Tilføj rapporten til REPORTS:

       REPORTS = [
           TEST1,
           FOREBYGGENDE_HJEMMEBESOEG,
           NY_RAPPORT,
       ]

VIGTIGT
=======

En rapportfil bliver ikke aktiv, bare fordi filen findes.

Rapporten bliver først aktiv, når rapportens REPORT-dictionary
er tilføjet til REPORTS-listen i denne fil.

Det gør registreringen tydelig og forhindrer, at gamle testfiler
automatisk bliver kørt.

DATABASESTRUKTUR
================

Rapportmotoren arbejder med PostgreSQL-tabellerne:

    workqueue
    workitem

Sammenhængen er:

    FROM workitem w
    JOIN workqueue q
      ON w.workqueue_id = q.id

Faste workitem-felter:

    w.id
    w.reference
    w.status
    w.message
    w.created_at
    w.updated_at
    w.started_at
    w.data

Kønavnet findes som:

    q.name

Det dynamiske itemindhold findes i:

    w.data

Et typisk data-objekt:

    {
        "box": {
            "cpr": "1234567890",
            "manuel_behandling_aarsag": "Eksempel"
        },
        "state": [],
        "status": {},
        "defer": null
    }

Et JSON-felt kan hentes i PostgreSQL sådan:

    w.data::jsonb #>> %(json_path)s

Hvor sql_parameters eksempelvis indeholder:

    "json_path": [
        "box",
        "manuel_behandling_aarsag",
    ]

FAST SIKKER GRUND-QUERY
=======================

Rapportmotoren anvender altid:

    q.name = kilde_queue
    w.status = status_filter
    w.<time_field> > rapportering_start
    w.<time_field> <= rapportering_end

Rapportens extra_where_sql kan kun tilføje ekstra AND-betingelser.

Rapportens tidsvindue kan derfor ikke fjernes af en rapportfil.

STANDARD SELECT-FELTER
======================

Rapportmotoren vælger altid:

    id
    reference
    status
    message
    created_at
    updated_at
    started_at
    queue_name
    data

Rapportens select_fields bruges kun til ekstra felter.

EXCEL-TYPER
===========

Tilladte typer:

    text
    datetime
    integer
    decimal

datetime bliver vist i Excel som:

    dd-mm-yyyy hh:mm:ss

Værdien bevares som en rigtig Excel-dato.

SIKKERHED
=========

extra_where_sql og select_fields.sql er betroet kode fra Git.

SQL må ikke komme fra:

    SharePoint
    slutbrugere
    mail
    browserinput
    workitem-data

Alle dynamiske værdier skal placeres i sql_parameters.
"""

from report_forebyggende_hjemmebesoeg import (
    REPORT as FOREBYGGENDE_HJEMMEBESOEG,
)
from report_test1 import (
    REPORT as TEST1,
)


# -------------------------------------------------------------
# AKTIVE RAPPORTER
# -------------------------------------------------------------
#
# En rapport skal stå i denne liste for at blive kontrolleret
# og eventuelt oprettet i queue-mode.
#
# Rækkefølgen her er også rækkefølgen i queue-kontrollen.
REPORTS = [
    TEST1,
    FOREBYGGENDE_HJEMMEBESOEG,
]


def get_report_by_id(rapport_id):
    """
    Finder en rapportopsætning ud fra rapport_id.

    Input:
        rapport_id:
            Rapportens tekniske id.

            Værdien skal matche SharePoint-kolonnen "Title".

    Output:
        dict:
            Den fulde rapportopsætning, hvis rapport_id findes.

        None:
            Hvis rapport_id ikke findes.
    """

    for report in REPORTS:
        if report.get("rapport_id") == rapport_id:
            return report

    return None


def validate_reports_config():
    """
    Validerer alle aktive rapportkonfigurationer ved opstart.

    Valideringen kontrollerer blandt andet:

        rapport_id er unikt
        nødvendige nøgler findes
        time_field er tilladt
        extra_where_sql begynder med AND
        SQL-fragmenter har ikke semikolon
        sql_parameters er en dictionary
        select_fields har sikre navne
        Excel-kolonner bruger kendte sources
        Excel-kolonner bruger kendte typer

    Output:
        None:
            Hvis alle rapporter er gyldige.

    Fejl:
        ValueError:
            Hvis mindst én rapport er ugyldig.
    """

    if not isinstance(REPORTS, list):
        raise ValueError(
            "REPORTS skal være en liste"
        )

    if not REPORTS:
        raise ValueError(
            "REPORTS er tom"
        )

    seen_report_ids = set()

    standard_select_names = {
        "id",
        "reference",
        "status",
        "message",
        "created_at",
        "updated_at",
        "started_at",
        "queue_name",
        "data",
    }

    required_keys = [
        "rapport_id",
        "rapport_navn",
        "kilde_queue",
        "status_filter",
        "time_field",
        "default_rapportering_start",
        "extra_where_sql",
        "sql_parameters",
        "select_fields",
        "afsender_mail",
        "mail_subject",
        "mail_body",
        "excel_file_prefix",
        "columns",
    ]

    allowed_time_fields = {
        "created_at",
        "updated_at",
        "started_at",
    }

    allowed_column_types = {
        "text",
        "datetime",
        "integer",
        "decimal",
    }

    for report_index, report in enumerate(
        REPORTS,
        start=1,
    ):
        if not isinstance(report, dict):
            raise ValueError(
                f"Rapport nr. {report_index} "
                "er ikke en dictionary"
            )

        for key in required_keys:
            if key not in report:
                raise ValueError(
                    f"Rapport nr. {report_index} "
                    f"mangler nøgle: {key}"
                )

        rapport_id = report["rapport_id"]

        if not isinstance(rapport_id, str):
            raise ValueError(
                f"Rapport nr. {report_index} "
                "har rapport_id, som ikke er tekst"
            )

        if not rapport_id.strip():
            raise ValueError(
                f"Rapport nr. {report_index} "
                "har tom rapport_id"
            )

        if rapport_id in seen_report_ids:
            raise ValueError(
                f"Dublet rapport_id fundet: {rapport_id}"
            )

        seen_report_ids.add(rapport_id)

        if not report["rapport_navn"]:
            raise ValueError(
                f"Rapport {rapport_id} "
                "har tom rapport_navn"
            )

        if not report["kilde_queue"]:
            raise ValueError(
                f"Rapport {rapport_id} "
                "har tom kilde_queue"
            )

        if not report["status_filter"]:
            raise ValueError(
                f"Rapport {rapport_id} "
                "har tom status_filter"
            )

        if report["time_field"] not in allowed_time_fields:
            raise ValueError(
                f"Rapport {rapport_id} har ugyldigt "
                f"time_field: {report['time_field']}. "
                "Tilladte værdier er: "
                f"{sorted(allowed_time_fields)}"
            )

        _validate_extra_where_sql(
            rapport_id=rapport_id,
            extra_where_sql=report[
                "extra_where_sql"
            ],
        )

        sql_parameters = report[
            "sql_parameters"
        ]

        if not isinstance(
            sql_parameters,
            dict,
        ):
            raise ValueError(
                f"Rapport {rapport_id} har "
                "sql_parameters, som ikke er en dictionary"
            )

        select_fields = report[
            "select_fields"
        ]

        if not isinstance(
            select_fields,
            list,
        ):
            raise ValueError(
                f"Rapport {rapport_id} har "
                "select_fields, som ikke er en liste"
            )

        available_sources = set(
            standard_select_names
        )

        custom_select_names = set()

        for field_index, field in enumerate(
            select_fields,
            start=1,
        ):
            if not isinstance(field, dict):
                raise ValueError(
                    f"Rapport {rapport_id} har ugyldigt "
                    f"select_field nr. {field_index}"
                )

            if "name" not in field:
                raise ValueError(
                    f"Rapport {rapport_id} har "
                    f"select_field nr. {field_index} "
                    "uden name"
                )

            if "sql" not in field:
                raise ValueError(
                    f"Rapport {rapport_id} har "
                    f"select_field nr. {field_index} "
                    "uden sql"
                )

            name = field["name"]
            sql_expression = field["sql"]

            if not _is_safe_identifier(name):
                raise ValueError(
                    f"Rapport {rapport_id} har ugyldigt "
                    f"select field-navn: {name}"
                )

            if name in standard_select_names:
                raise ValueError(
                    f"Rapport {rapport_id} forsøger "
                    "at overskrive standardfeltet: "
                    f"{name}"
                )

            if name in custom_select_names:
                raise ValueError(
                    f"Rapport {rapport_id} har dublet "
                    f"select field-navn: {name}"
                )

            if not isinstance(
                sql_expression,
                str,
            ):
                raise ValueError(
                    f"Rapport {rapport_id} har SQL, "
                    f"som ikke er tekst for feltet: {name}"
                )

            if not sql_expression.strip():
                raise ValueError(
                    f"Rapport {rapport_id} har tom SQL "
                    f"for select field: {name}"
                )

            if ";" in sql_expression:
                raise ValueError(
                    f"Rapport {rapport_id} har semikolon "
                    f"i select SQL for feltet: {name}"
                )

            custom_select_names.add(name)
            available_sources.add(name)

        columns = report["columns"]

        if not isinstance(columns, list):
            raise ValueError(
                f"Rapport {rapport_id} har columns, "
                "som ikke er en liste"
            )

        if not columns:
            raise ValueError(
                f"Rapport {rapport_id} "
                "har en tom columns-liste"
            )

        seen_headers = set()

        for column_index, column in enumerate(
            columns,
            start=1,
        ):
            if not isinstance(column, dict):
                raise ValueError(
                    f"Rapport {rapport_id} har ugyldig "
                    f"column nr. {column_index}"
                )

            if "header" not in column:
                raise ValueError(
                    f"Rapport {rapport_id} har column "
                    f"nr. {column_index} uden header"
                )

            if "source" not in column:
                raise ValueError(
                    f"Rapport {rapport_id} har column "
                    f"nr. {column_index} uden source"
                )

            header = column["header"]
            source = column["source"]
            column_type = column.get(
                "type",
                "text",
            )

            if not isinstance(header, str):
                raise ValueError(
                    f"Rapport {rapport_id} har header, "
                    "som ikke er tekst i column "
                    f"nr. {column_index}"
                )

            if not header.strip():
                raise ValueError(
                    f"Rapport {rapport_id} har tom header "
                    f"i column nr. {column_index}"
                )

            if header in seen_headers:
                raise ValueError(
                    f"Rapport {rapport_id} har dublet "
                    f"Excel-header: {header}"
                )

            seen_headers.add(header)

            if not isinstance(source, str):
                raise ValueError(
                    f"Rapport {rapport_id} har source, "
                    "som ikke er tekst i column "
                    f"nr. {column_index}"
                )

            if column_type not in allowed_column_types:
                raise ValueError(
                    f"Rapport {rapport_id} har ugyldig "
                    f"column type: {column_type}"
                )

            # Nested source som data.box.cpr er tilladt,
            # fordi source-roden er standardfeltet data.
            source_root = source.split(".")[0]

            if source_root not in available_sources:
                raise ValueError(
                    f"Rapport {rapport_id} har ukendt "
                    f"column source: {source}"
                )


def _validate_extra_where_sql(
    rapport_id,
    extra_where_sql,
):
    """
    Validerer rapportens extra_where_sql.

    Regler:
        Skal være tekst.
        Må gerne være tom.
        Skal begynde med AND, hvis teksten ikke er tom.
        Må ikke indeholde semikolon.

    Output:
        None:
            Hvis SQL-fragmentet er gyldigt.

    Fejl:
        ValueError:
            Hvis SQL-fragmentet er ugyldigt.
    """

    if not isinstance(extra_where_sql, str):
        raise ValueError(
            f"Rapport {rapport_id} har "
            "extra_where_sql, som ikke er tekst"
        )

    cleaned_sql = extra_where_sql.strip()

    if not cleaned_sql:
        return

    if not cleaned_sql.upper().startswith("AND "):
        raise ValueError(
            f"Rapport {rapport_id}: "
            "extra_where_sql skal begynde med AND"
        )

    if ";" in cleaned_sql:
        raise ValueError(
            f"Rapport {rapport_id}: "
            "extra_where_sql må ikke indeholde semikolon"
        )


def _is_safe_identifier(value):
    """
    Kontrollerer om et navn kan bruges som sikkert SQL-alias.

    Tilladt:
        bogstaver
        tal
        underscore

    Navnet må ikke starte med et tal.

    Input:
        value:
            Navnet der skal kontrolleres.

    Output:
        bool:
            True ved gyldigt navn.
            False ved ugyldigt navn.
    """

    if not isinstance(value, str):
        return False

    if not value:
        return False

    if value[0].isdigit():
        return False

    return value.replace("_", "").isalnum()