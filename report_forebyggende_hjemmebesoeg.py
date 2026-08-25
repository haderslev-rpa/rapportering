# forebyggende_hjemmebesoeg.py

"""
RAPPORT: FOREBYGGENDE HJEMMEBESØG
=================================

Denne rapport finder completed items fra køen:

    forebyggende-hjemmebesoeg

Rapporten medtager kun items, hvor JSON-feltet:

    data.box.manuel_behandling_aarsag

findes og indeholder reel tekst.

DATABASESTRUKTUR
================

Den faste rapportmotor arbejder med:

    FROM workitem w
    JOIN workqueue q
      ON w.workqueue_id = q.id

De faste felter findes som:

    w.id
    w.reference
    w.status
    w.message
    w.created_at
    w.updated_at
    w.started_at
    q.name

Det dynamiske itemindhold ligger i:

    w.data

Et typisk item kan se sådan ud:

    {
        "box": {
            "cpr": "1234567890",
            "navn": "Eksempel",
            "adresse": "Eksempelvej",
            "husnummer": "1",
            "postnummer": "6100",
            "manuel_behandling_aarsag": "Organisation blev ikke fundet"
        },
        "state": [],
        "status": {},
        "defer": null
    }

Feltet manuel_behandling_aarsag ligger derfor på JSON-stien:

    box.manuel_behandling_aarsag

PostgreSQL kan udtrække feltet som tekst sådan:

    w.data::jsonb #>> ARRAY[
        'box',
        'manuel_behandling_aarsag'
    ]

I denne rapport sendes JSON-stien som en parameter:

    "manuel_behandling_aarsag_path": [
        "box",
        "manuel_behandling_aarsag",
    ]

SQL-udtrykket bruger parameteren sådan:

    w.data::jsonb
    #>> %(manuel_behandling_aarsag_path)s

FILTERET
========

Den faste rapportmotor tilføjer altid:

    q.name = kilde_queue
    w.status = status_filter
    w.updated_at > rapportering_start
    w.updated_at <= rapportering_end

Denne rapport tilføjer derefter:

    manuel_behandling_aarsag skal være udfyldt

Filteret frasorterer:

    manglende felt
    JSON null
    tom tekst
    tekst med kun mellemrum

SELECT_FIELDS
=============

select_fields udtrækker udvalgte JSON-værdier direkte i PostgreSQL.

Eksempel:

    {
        "name": "cpr",
        "sql": "w.data::jsonb #>> %(cpr_path)s",
    }

Efter SQL-queryen findes værdien som:

    row["cpr"]

Excel-kolonnen kan derfor bruge:

    {
        "header": "CPR",
        "source": "cpr",
        "type": "text",
    }

EXCEL-DATOER
============

Kolonner med:

    "type": "datetime"

bliver bevaret som rigtige Excel-datoer og vist sådan:

    dd-mm-yyyy hh:mm:ss
"""


REPORT = {
    # ---------------------------------------------------------
    # IDENTITET
    # ---------------------------------------------------------

    # Skal matche SharePoint-kolonnen "Title" præcist.
    "rapport_id": "forebyggende-hjemmebesoeg",

    # Det pæne navn, som mailmodtageren ser.
    "rapport_navn": (
        "Forebyggende hjemmebesøg - manuel behandling"
    ),

    # ---------------------------------------------------------
    # FAST SIKKER GRUND-QUERY
    # ---------------------------------------------------------

    # Skal matche workqueue.name præcist.
    # Kønavnet i databasen har lille begyndelsesbogstav.
    "kilde_queue": "forebyggende-hjemmebesoeg",

    # Kun completed items skal med.
    "status_filter": "COMPLETED",

    # Rapportperioden anvendes på updated_at.
    "time_field": "updated_at",

    # Bruges kun hvis der ikke findes historik for rapport_id.
    "default_rapportering_start": "2026-08-01 00:00:00",

    # ---------------------------------------------------------
    # RAPPORTENS EKSTRA WHERE-FILTER
    # ---------------------------------------------------------

    # Kun items med udfyldt manuel_behandling_aarsag.
    #
    # NULLIF(..., '') IS NOT NULL sørger for, at manglende,
    # null, tomme og whitespace-værdier bliver frasorteret.
    "extra_where_sql": """
        AND NULLIF(
            BTRIM(
                COALESCE(
                    w.data::jsonb
                    #>> %(manuel_behandling_aarsag_path)s,
                    ''
                )
            ),
            ''
        ) IS NOT NULL
    """,

    # ---------------------------------------------------------
    # PARAMETRE TIL SQL
    # ---------------------------------------------------------

    # Alle dynamiske SQL-værdier ligger her.
    #
    # Lister med JSON-stier bliver sendt sikkert til PostgreSQL
    # som text-arrays via psycopg2.
    "sql_parameters": {
        "manuel_behandling_aarsag_path": [
            "box",
            "manuel_behandling_aarsag",
        ],
        "cpr_path": [
            "box",
            "cpr",
        ],
        "navn_path": [
            "box",
            "navn",
        ],
        "adresse_path": [
            "box",
            "adresse",
        ],
        "husnummer_path": [
            "box",
            "husnummer",
        ],
        "postnummer_path": [
            "box",
            "postnummer",
        ],
        "queue_aarsag_path": [
            "box",
            "queue_aarsag",
        ],
        "aldersregel_aarsag_path": [
            "box",
            "aldersregel_aarsag",
        ],
    },

    # ---------------------------------------------------------
    # EKSTRA SELECT-FELTER
    # ---------------------------------------------------------

    # Standardfelterne id, reference, status, message,
    # created_at, updated_at, started_at, queue_name og data
    # vælges automatisk af rapportmotoren.
    #
    # Her tilføjes kun rapportens særlige JSON-felter.
    "select_fields": [
        {
            "name": "cpr",
            "sql": (
                "w.data::jsonb "
                "#>> %(cpr_path)s"
            ),
        },
        {
            "name": "navn",
            "sql": (
                "w.data::jsonb "
                "#>> %(navn_path)s"
            ),
        },
        {
            "name": "adresse",
            "sql": (
                "w.data::jsonb "
                "#>> %(adresse_path)s"
            ),
        },
        {
            "name": "husnummer",
            "sql": (
                "w.data::jsonb "
                "#>> %(husnummer_path)s"
            ),
        },
        {
            "name": "postnummer",
            "sql": (
                "w.data::jsonb "
                "#>> %(postnummer_path)s"
            ),
        },
        {
            "name": "queue_aarsag",
            "sql": (
                "w.data::jsonb "
                "#>> %(queue_aarsag_path)s"
            ),
        },
        {
            "name": "aldersregel_aarsag",
            "sql": (
                "w.data::jsonb "
                "#>> %(aldersregel_aarsag_path)s"
            ),
        },
        {
            "name": "manuel_behandling_aarsag",
            "sql": (
                "w.data::jsonb "
                "#>> %(manuel_behandling_aarsag_path)s"
            ),
        },
    ],

    # ---------------------------------------------------------
    # MAIL
    # ---------------------------------------------------------
    "afsender_mail": "robot-data@haderslev.dk",

    "mail_subject": (
        "Rapport - Forebyggende hjemmebesøg "
        "- manuel behandling"
    ),

    "mail_body": (
        "Hej\n\n"
        "Vedhæftet er rapporten over completed items, "
        "som er sendt til manuel behandling.\n\n"
        "Rapport: {rapport_navn}\n"
        "Periode: {rapportering_start_dk} til "
        "{rapportering_end_dk}\n"
        "Antal items til manuel behandling: "
        "{antal_rows}\n\n"
        "Venlig hilsen\n"
        "Robotten"
    ),

    # ---------------------------------------------------------
    # EXCEL
    # ---------------------------------------------------------
    "excel_file_prefix": (
        "Forebyggende_hjemmebesoeg_manuel_behandling"
    ),

    # Kolonnerne står i den rækkefølge, de skal vises i Excel.
    #
    # source refererer enten til:
    # 1. et standardfelt fra rapportmotoren
    # 2. name fra select_fields ovenfor
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
        {
            "header": "CPR",
            "source": "cpr",
            "type": "text",
        },
        {
            "header": "Navn",
            "source": "navn",
            "type": "text",
        },
        {
            "header": "Adresse",
            "source": "adresse",
            "type": "text",
        },
        {
            "header": "Husnummer",
            "source": "husnummer",
            "type": "text",
        },
        {
            "header": "Postnummer",
            "source": "postnummer",
            "type": "text",
        },
        {
            "header": "Queue årsag",
            "source": "queue_aarsag",
            "type": "text",
        },
        {
            "header": "Aldersregel årsag",
            "source": "aldersregel_aarsag",
            "type": "text",
        },
        {
            "header": "Manuel behandling årsag",
            "source": "manuel_behandling_aarsag",
            "type": "text",
        },
    ],
}