# report_forebyggende_hjemmebesoeg.py

"""
RAPPORT: FOREBYGGENDE HJEMMEBESØG
=================================

Rapporten finder completed items fra køen:

    forebyggende-hjemmebesoeg

Rapporten bruger den almindelige rapportmotors sikre grund-query:

    FROM workitem w
    JOIN workqueue q
      ON w.workqueue_id = q.id

    WHERE q.name = kilde_queue
      AND w.status = status_filter
      AND det valgte time_field ligger i rapporteringsperioden

Denne rapport tilføjer et ekstra filter på JSON-arrayet:

    data.state

Et item medtages, hvis state indeholder mindst én tekst,
som starter med:

    9.0 Sendt til manuel behandling
    4.2 Intern kontaktperson oprettet
    3.1 Organisation oprettet

Kun 9.0 med punktum accepteres.

Eksempel på state:

    {
        "state": [
            "0.5 Borger fundet i Cura 26-08-2026 10:14:48",
            "1.0 Aldersregel vurderet 26-08-2026 10:14:48",
            "9.0 Sendt til manuel behandling 26-08-2026 10:14:48"
        ]
    }

Procenttegnet i SQL-mønstrene betyder, at teksten gerne må
fortsætte med dato, klokkeslæt eller anden tekst:

    9.0 Sendt til manuel behandling%

DATA.BOX
========

Borgerdata ligger under:

    data.box

Eksempel:

    {
        "box": {
            "cpr": "1234567890",
            "navn": "Eksempel",
            "adresse": "Eksempelvej",
            "husnummer": "1",
            "postnr": "6100",
            "queue_aarsag": "Eksempel",
            "aldersregel_aarsag": "Eksempel"
        }
    }

JSON-felter udtrækkes i PostgreSQL med:

    w.data::jsonb #>> ARRAY[
        'box',
        'cpr'
    ]

JSON-stien sendes som en sikker psycopg2-parameter:

    "cpr_path": [
        "box",
        "cpr",
    ]

POSTNUMMER
==========

Det aktuelle felt forventes at hedde:

    data.box.postnr

Rapporten understøtter samtidig det tidligere feltnavn:

    data.box.postnummer

Postnummer beregnes derfor med:

    COALESCE(
        data.box.postnr,
        data.box.postnummer
    )

Prioriteten er:

    1. box.postnr
    2. box.postnummer
    3. tom værdi

Det betyder, at både nye og eventuelle ældre items kan få
postnummer med i Excel.

DATA.STATE
==========

State ligger direkte under data:

    data.state

State ligger ikke inde i box.

PostgreSQL-funktionen:

    jsonb_array_elements_text(...)

gennemgår hvert element i state-arrayet som tekst.

Hvis state mangler, er null eller ikke er et JSON-array,
behandles state som:

    []::jsonb

Itemet giver derfor ikke SQL-fejl.
Itemet matcher blot ingen relevante states.

BESKED
======

Excel-kolonnen Besked beregnes sådan:

1. Hvis state indeholder:

       9.0 Sendt til manuel behandling

   bliver:

       Besked = w.message

2. Hvis state indeholder både:

       4.2 Intern kontaktperson oprettet

   og:

       3.1 Organisation oprettet

   bliver:

       Besked =
       Intern kontaktperson oprettet og Organisation oprettet

3. Hvis state kun indeholder 4.2:

       Besked = Intern kontaktperson oprettet

4. Hvis state kun indeholder 3.1:

       Besked = Organisation oprettet

Hvis 9.0 findes sammen med 4.2 eller 3.1, har 9.0 højeste
prioritet. Besked bliver derfor w.message.

MESSAGE
=======

Excel-kolonnen Message indeholder altid det oprindelige:

    w.message

Ved manuel behandling vil Besked og Message derfor have
samme værdi.

Ved de øvrige kategorier indeholder:

    Besked:
        Den afledte proceskategori.

    Message:
        Den oprindelige værdi fra workitem.message.

EXCEL-DATOER
============

Kolonner med:

    "type": "datetime"

bevares som rigtige Excel-datoer og vises som:

    dd-mm-yyyy hh:mm:ss
"""


REPORT = {
    # ---------------------------------------------------------
    # IDENTITET
    # ---------------------------------------------------------

    # Skal matche SharePoint-kolonnen Title præcist.
    "rapport_id": "forebyggende-hjemmebesoeg",

    "rapport_navn": (
        "Forebyggende hjemmebesøg - processtatus"
    ),

    # ---------------------------------------------------------
    # FAST SIKKER GRUND-QUERY
    # ---------------------------------------------------------

    # Skal matche workqueue.name præcist.
    "kilde_queue": "forebyggende-hjemmebesoeg",

    # Kun completed items medtages.
    "status_filter": "COMPLETED",

    # Rapportperioden anvendes på updated_at.
    "time_field": "updated_at",

    # Bruges kun, hvis der ikke findes historik
    # for dette rapport_id.
    "default_rapportering_start": "2026-08-01 00:00:00",

    # ---------------------------------------------------------
    # RAPPORTENS EKSTRA WHERE-FILTER
    # ---------------------------------------------------------

    # Medtag kun items, hvor data.state indeholder mindst én
    # af de tre relevante states.
    #
    # Kun 9.0 med punktum understøttes.
    "extra_where_sql": """
        AND EXISTS (
            SELECT 1

            FROM jsonb_array_elements_text(
                CASE
                    WHEN jsonb_typeof(
                        w.data::jsonb -> 'state'
                    ) = 'array'
                    THEN w.data::jsonb -> 'state'

                    ELSE '[]'::jsonb
                END
            ) AS state_item(state_text)

            WHERE state_item.state_text
                  ILIKE ANY(%(relevant_state_patterns)s)
        )
    """,

    # ---------------------------------------------------------
    # PARAMETRE TIL SQL
    # ---------------------------------------------------------

    "sql_parameters": {
        # -----------------------------------------------------
        # RELEVANTE STATES
        # -----------------------------------------------------
        "relevant_state_patterns": [
            "9.0 Sendt til manuel behandling%",
            "4.2 Intern kontaktperson oprettet%",
            "3.1 Organisation oprettet%",
        ],

        "sendt_til_manuel_pattern": (
            "9.0 Sendt til manuel behandling%"
        ),

        "intern_kontaktperson_pattern": (
            "4.2 Intern kontaktperson oprettet%"
        ),

        "organisation_oprettet_pattern": (
            "3.1 Organisation oprettet%"
        ),

        # -----------------------------------------------------
        # JSON-STIER TIL DATA.BOX
        # -----------------------------------------------------
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

        # Aktuelt feltnavn.
        "postnr_path": [
            "box",
            "postnr",
        ],

        # Fallback til eventuelle ældre items.
        "postnummer_path": [
            "box",
            "postnummer",
        ],

        "queue_aarsag_path": [
            "box",
            "queue_aarsag",
        ],
    },

    # ---------------------------------------------------------
    # EKSTRA SELECT-FELTER
    # ---------------------------------------------------------

    # Rapportmotoren vælger automatisk:
    #
    #     id
    #     reference
    #     status
    #     message
    #     created_at
    #     updated_at
    #     started_at
    #     queue_name
    #     data
    #
    # Her tilføjes de ønskede JSON-felter og den
    # beregnede Besked.
    "select_fields": [
        # -----------------------------------------------------
        # CPR
        # -----------------------------------------------------
        {
            "name": "cpr",
            "sql": (
                "w.data::jsonb "
                "#>> %(cpr_path)s"
            ),
        },

        # -----------------------------------------------------
        # NAVN
        # -----------------------------------------------------
        {
            "name": "navn",
            "sql": (
                "w.data::jsonb "
                "#>> %(navn_path)s"
            ),
        },

        # -----------------------------------------------------
        # ADRESSE
        # -----------------------------------------------------
        {
            "name": "adresse",
            "sql": (
                "w.data::jsonb "
                "#>> %(adresse_path)s"
            ),
        },

        # -----------------------------------------------------
        # HUSNUMMER
        # -----------------------------------------------------
        {
            "name": "husnummer",
            "sql": (
                "w.data::jsonb "
                "#>> %(husnummer_path)s"
            ),
        },

        # -----------------------------------------------------
        # POSTNUMMER
        # -----------------------------------------------------
        {
            "name": "postnummer",

            # Først bruges box.postnr.
            #
            # Hvis box.postnr mangler eller er null,
            # bruges box.postnummer som fallback.
            "sql": """
                COALESCE(
                    w.data::jsonb
                    #>> %(postnr_path)s,

                    w.data::jsonb
                    #>> %(postnummer_path)s
                )
            """,
        },

        # -----------------------------------------------------
        # QUEUE-ÅRSAG
        # -----------------------------------------------------
        {
            "name": "queue_aarsag",
            "sql": (
                "w.data::jsonb "
                "#>> %(queue_aarsag_path)s"
            ),
        },


        # -----------------------------------------------------
        # AFLEDT KATEGORI: BESKED
        # -----------------------------------------------------
        {
            "name": "besked",

            # Prioritet:
            #
            # 1. Manuel behandling:
            #       Besked = w.message
            #
            # 2. Både kontaktperson og organisation:
            #       Besked = begge kategorier
            #
            # 3. Kun kontaktperson:
            #       Besked = kontaktpersonkategorien
            #
            # 4. Kun organisation:
            #       Besked = organisationskategorien
            "sql": """
                CASE
                    -- =========================================
                    -- 1. SENDT TIL MANUEL BEHANDLING
                    -- =========================================
                    WHEN EXISTS (
                        SELECT 1

                        FROM jsonb_array_elements_text(
                            CASE
                                WHEN jsonb_typeof(
                                    w.data::jsonb -> 'state'
                                ) = 'array'
                                THEN w.data::jsonb -> 'state'

                                ELSE '[]'::jsonb
                            END
                        ) AS manual_state(state_text)

                        WHERE manual_state.state_text
                              ILIKE
                              %(sendt_til_manuel_pattern)s
                    )

                    -- Ved manuel behandling bruges det
                    -- oprindelige message-felt som Besked.
                    THEN w.message

                    -- =========================================
                    -- 2. BÅDE INTERN KONTAKTPERSON
                    --    OG ORGANISATION OPRETTET
                    -- =========================================
                    WHEN
                        EXISTS (
                            SELECT 1

                            FROM jsonb_array_elements_text(
                                CASE
                                    WHEN jsonb_typeof(
                                        w.data::jsonb -> 'state'
                                    ) = 'array'
                                    THEN w.data::jsonb -> 'state'

                                    ELSE '[]'::jsonb
                                END
                            ) AS contact_state(state_text)

                            WHERE contact_state.state_text
                                  ILIKE
                                  %(intern_kontaktperson_pattern)s
                        )

                        AND

                        EXISTS (
                            SELECT 1

                            FROM jsonb_array_elements_text(
                                CASE
                                    WHEN jsonb_typeof(
                                        w.data::jsonb -> 'state'
                                    ) = 'array'
                                    THEN w.data::jsonb -> 'state'

                                    ELSE '[]'::jsonb
                                END
                            ) AS organisation_state(state_text)

                            WHERE organisation_state.state_text
                                  ILIKE
                                  %(organisation_oprettet_pattern)s
                        )

                    THEN (
                        'Intern kontaktperson oprettet og '
                        'Organisation oprettet'
                    )

                    -- =========================================
                    -- 3. KUN INTERN KONTAKTPERSON OPRETTET
                    -- =========================================
                    WHEN EXISTS (
                        SELECT 1

                        FROM jsonb_array_elements_text(
                            CASE
                                WHEN jsonb_typeof(
                                    w.data::jsonb -> 'state'
                                ) = 'array'
                                THEN w.data::jsonb -> 'state'

                                ELSE '[]'::jsonb
                            END
                        ) AS contact_state(state_text)

                        WHERE contact_state.state_text
                              ILIKE
                              %(intern_kontaktperson_pattern)s
                    )

                    THEN 'Intern kontaktperson oprettet'

                    -- =========================================
                    -- 4. KUN ORGANISATION OPRETTET
                    -- =========================================
                    WHEN EXISTS (
                        SELECT 1

                        FROM jsonb_array_elements_text(
                            CASE
                                WHEN jsonb_typeof(
                                    w.data::jsonb -> 'state'
                                ) = 'array'
                                THEN w.data::jsonb -> 'state'

                                ELSE '[]'::jsonb
                            END
                        ) AS organisation_state(state_text)

                        WHERE organisation_state.state_text
                              ILIKE
                              %(organisation_oprettet_pattern)s
                    )

                    THEN 'Organisation oprettet'

                    ELSE NULL
                END
            """,
        },
    ],

    # ---------------------------------------------------------
    # MAIL
    # ---------------------------------------------------------
    "afsender_mail": "robot-data@haderslev.dk",

    "mail_subject": (
        "Rapport - Forebyggende hjemmebesøg "
        "- processtatus"
    ),

    "mail_body": (
        "Hej\n\n"
        "Vedhæftet er rapporten over completed items, "
        "som indeholder et af de relevante procestrin.\n\n"
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
        "Forebyggende_hjemmebesoeg_processtatus"
    ),

    # Kolonnerne står her i præcis den rækkefølge,
    # de skal vises i Excel.
    # ---------------------------------------------------------
    # EXCEL-KOLONNER
    # ---------------------------------------------------------
    #
    # Kolonnerne står i præcis den rækkefølge,
    # de skal vises i Excel.
    #
    # States (handlinger) bruger fortsat det interne
    # SQL-felt med navnet "besked".
    #
    # Det er kun Excel-overskriften, der er ændret.
    "columns": [
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
            "header": "States (handlinger)",
            "source": "besked",
            "type": "text",
        },

        {
            "header": "Message",
            "source": "message",
            "type": "text",
        },

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
    ],
}