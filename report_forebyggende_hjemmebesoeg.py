# report_forebyggende_hjemmebesoeg.py

"""
RAPPORT: FOREBYGGENDE HJEMMEBESØG
=================================

Denne rapport finder completed items fra køen:

    forebyggende-hjemmebesoeg

Rapporten medtager kun items, hvor JSON-arrayet:

    data.state

indeholder mindst én state, som starter med:

    9.0 Sendt til manuel behandling
    4.2 Intern kontaktperson oprettet
    3.1 Organisation oprettet

Teksten efter procestrinnet må gerne indeholde dato og tidspunkt.

Eksempel:

    9.0 Sendt til manuel behandling 26-08-2026 10:14:48

Derfor anvendes SQL-mønstre med procenttegn:

    9.0 Sendt til manuel behandling%

Procenttegnet betyder:

    Alt efter den faste tekst accepteres.

VIGTIGT:

    Kun 9.0 med punktum accepteres.

Denne tekst accepteres:

    9.0 Sendt til manuel behandling

Denne tekst accepteres ikke:

    9,0 Sendt til manuel behandling


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
            "postnummer": "6100"
        },
        "defer": null,
        "state": [
            "0.5 Borger fundet i Cura 26-08-2026 10:14:48",
            "1.0 Aldersregel vurderet 26-08-2026 10:14:48",
            "9.0 Sendt til manuel behandling 26-08-2026 10:14:48"
        ],
        "status": {
            "status": "Completed",
            "status_code": "Manuel"
        }
    }


VIGTIGT OM DATA.BOX
===================

De almindelige procesdata ligger typisk under:

    data.box

Eksempel:

    data.box.cpr

I PostgreSQL kan feltet hentes sådan:

    w.data::jsonb #>> ARRAY[
        'box',
        'cpr'
    ]

I rapportkonfigurationen sendes JSON-stien som en parameter:

    "cpr_path": [
        "box",
        "cpr",
    ]

SQL-udtrykket bruger parameteren sådan:

    w.data::jsonb #>> %(cpr_path)s


VIGTIGT OM DATA.STATE
=====================

State ligger direkte under data:

    data.state

State ligger altså ikke inde i box.

I PostgreSQL findes state-arrayet som:

    w.data::jsonb -> 'state'

Et state-array kan eksempelvis se sådan ud:

    [
        "3.1 Organisation oprettet 26-08-2026 10:12:00",
        "4.2 Intern kontaktperson oprettet 26-08-2026 10:13:00"
    ]


GENNEMGANG AF STATE
===================

PostgreSQL-funktionen:

    jsonb_array_elements_text(...)

udvider JSON-arrayet til én tekstværdi pr. state.

Konceptuelt:

    SELECT state_item.state_text

    FROM jsonb_array_elements_text(
        w.data::jsonb -> 'state'
    ) AS state_item(state_text)

Et item med tre states bliver dermed kontrolleret som tre
separate tekstværdier.

Rapportens EXISTS-filter spørger:

    Findes der mindst én relevant state?

Hvis ja:

    Itemet medtages.

Hvis nej:

    Itemet frasorteres.


ROBUST HÅNDTERING AF STATE
==========================

Koden kontrollerer først, om data.state er et JSON-array:

    jsonb_typeof(
        w.data::jsonb -> 'state'
    ) = 'array'

Hvis state mangler, er null eller har en anden datatype,
bruges et tomt array:

    []::jsonb

Det betyder:

    SQL-queryen fejler ikke.

    Itemet matcher blot ingen relevante states.


KATEGORISERING
==============

Rapporten opretter et afledt SQL-felt med navnet:

    besked

Feltet kan få én af disse værdier:

    Sendt til manuel behandling

    Intern kontaktperson oprettet og Organisation oprettet

    Intern kontaktperson oprettet

    Organisation oprettet

Excel viser værdien i kolonnen:

    Besked


KATEGORISERINGENS PRIORITET
==========================

Et item kan indeholde mere end én relevant state.

Kategoriseringen bruger denne prioritet:

1. Sendt til manuel behandling

2. Både intern kontaktperson og organisation oprettet

3. Kun intern kontaktperson oprettet

4. Kun organisation oprettet


EKSEMPEL 1
==========

State:

    [
        "9.0 Sendt til manuel behandling 26-08-2026 10:14:48"
    ]

Besked:

    Sendt til manuel behandling


EKSEMPEL 2
==========

State:

    [
        "4.2 Intern kontaktperson oprettet 26-08-2026 10:14:48"
    ]

Besked:

    Intern kontaktperson oprettet


EKSEMPEL 3
==========

State:

    [
        "3.1 Organisation oprettet 26-08-2026 10:14:48"
    ]

Besked:

    Organisation oprettet


EKSEMPEL 4
==========

State:

    [
        "3.1 Organisation oprettet 26-08-2026 10:13:00",
        "4.2 Intern kontaktperson oprettet 26-08-2026 10:14:48"
    ]

Besked:

    Intern kontaktperson oprettet og Organisation oprettet


EKSEMPEL 5
==========

State:

    [
        "3.1 Organisation oprettet 26-08-2026 10:12:00",
        "4.2 Intern kontaktperson oprettet 26-08-2026 10:13:00",
        "9.0 Sendt til manuel behandling 26-08-2026 10:14:48"
    ]

Besked:

    Sendt til manuel behandling

Det skyldes, at manuel behandling har højeste prioritet.


FILTERET
========

Den faste rapportmotor tilføjer altid:

    q.name = kilde_queue

    w.status = status_filter

    w.updated_at > rapportering_start

    w.updated_at <= rapportering_end

Denne rapport tilføjer derefter:

    data.state skal indeholde mindst ét relevant procestrin.

Statusfilteret er:

    COMPLETED

Rapporten medtager derfor kun completed items inden for det
tekniske rapporteringsvindue.


SELECT_FIELDS
=============

select_fields udtrækker:

    værdier fra data.box

    den beregnede kategori Besked

Eksempel på et JSON-felt:

    {
        "name": "cpr",
        "sql": (
            "w.data::jsonb "
            "#>> %(cpr_path)s"
        ),
    }

Efter SQL-queryen findes værdien som:

    row["cpr"]

Excel-kolonnen bruger:

    {
        "header": "CPR",
        "source": "cpr",
        "type": "text",
    }

Det beregnede felt Besked oprettes med SQL CASE.

Efter SQL-queryen findes værdien som:

    row["besked"]

Excel-kolonnen bruger:

    {
        "header": "Besked",
        "source": "besked",
        "type": "text",
    }


EXCEL-DATOER
============

Kolonner med:

    "type": "datetime"

bevares som rigtige Excel-datoer og vises sådan:

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
        "Forebyggende hjemmebesøg - processtatus"
    ),

    # ---------------------------------------------------------
    # FAST SIKKER GRUND-QUERY
    # ---------------------------------------------------------

    # Skal matche workqueue.name præcist.
    "kilde_queue": "forebyggende-hjemmebesoeg",

    # Kun completed items skal med.
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
    # af de tre relevante states:
    #
    #     9.0 Sendt til manuel behandling
    #
    #     4.2 Intern kontaktperson oprettet
    #
    #     3.1 Organisation oprettet
    #
    # Kun 9.0 med punktum understøttes.
    #
    # jsonb_array_elements_text gennemgår alle tekster
    # i data.state.
    #
    # Hvis state mangler eller ikke er et JSON-array,
    # behandles state som et tomt array.
    #
    # ILIKE gør søgningen uafhængig af store og små bogstaver.
    #
    # ANY sammenligner state-teksten med alle mønstrene
    # i relevant_state_patterns.
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

    # Alle dynamiske SQL-værdier ligger her.
    #
    # Procenttegnet % betyder:
    #
    #     Accepter al tekst efter det faste procestrin.
    #
    # Det betyder, at dato og klokkeslæt efter procestrinnet
    # ikke skal være kendt på forhånd.
    "sql_parameters": {
        # -----------------------------------------------------
        # ALLE RELEVANTE STATES
        # -----------------------------------------------------
        "relevant_state_patterns": [
            "9.0 Sendt til manuel behandling%",
            "4.2 Intern kontaktperson oprettet%",
            "3.1 Organisation oprettet%",
        ],

        # -----------------------------------------------------
        # KATEGORI: SENDT TIL MANUEL BEHANDLING
        # -----------------------------------------------------

        # VIGTIGT:
        # Kun 9.0 med punktum.
        "sendt_til_manuel_pattern": (
            "9.0 Sendt til manuel behandling%"
        ),

        # -----------------------------------------------------
        # KATEGORI: INTERN KONTAKTPERSON
        # -----------------------------------------------------
        "intern_kontaktperson_pattern": (
            "4.2 Intern kontaktperson oprettet%"
        ),

        # -----------------------------------------------------
        # KATEGORI: ORGANISATION
        # -----------------------------------------------------
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

    # Standardfelterne vælges automatisk af rapportmotoren:
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
    # Her tilføjes rapportens beregnede kategori og
    # de relevante værdier fra data.box.
    "select_fields": [
        # -----------------------------------------------------
        # AFLEDT KATEGORI: BESKED
        # -----------------------------------------------------
        {
            "name": "besked",

            # Kategoriseringen bruger denne prioritet:
            #
            # 1. Sendt til manuel behandling
            #
            # 2. Både intern kontaktperson og organisation
            #    oprettet
            #
            # 3. Kun intern kontaktperson oprettet
            #
            # 4. Kun organisation oprettet
            #
            # CASE stopper ved det første match.
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
                    THEN 'Sendt til manuel behandling'

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

        # -----------------------------------------------------
        # CPR FRA DATA.BOX
        # -----------------------------------------------------
        {
            "name": "cpr",
            "sql": (
                "w.data::jsonb "
                "#>> %(cpr_path)s"
            ),
        },

        # -----------------------------------------------------
        # NAVN FRA DATA.BOX
        # -----------------------------------------------------
        {
            "name": "navn",
            "sql": (
                "w.data::jsonb "
                "#>> %(navn_path)s"
            ),
        },

        # -----------------------------------------------------
        # ADRESSE FRA DATA.BOX
        # -----------------------------------------------------
        {
            "name": "adresse",
            "sql": (
                "w.data::jsonb "
                "#>> %(adresse_path)s"
            ),
        },

        # -----------------------------------------------------
        # HUSNUMMER FRA DATA.BOX
        # -----------------------------------------------------
        {
            "name": "husnummer",
            "sql": (
                "w.data::jsonb "
                "#>> %(husnummer_path)s"
            ),
        },

        # -----------------------------------------------------
        # POSTNUMMER FRA DATA.BOX
        # -----------------------------------------------------
        {
            "name": "postnummer",
            "sql": (
                "w.data::jsonb "
                "#>> %(postnummer_path)s"
            ),
        },

        # -----------------------------------------------------
        # QUEUE-ÅRSAG FRA DATA.BOX
        # -----------------------------------------------------
        {
            "name": "queue_aarsag",
            "sql": (
                "w.data::jsonb "
                "#>> %(queue_aarsag_path)s"
            ),
        },

        # -----------------------------------------------------
        # ALDERSREGEL-ÅRSAG FRA DATA.BOX
        # -----------------------------------------------------
        {
            "name": "aldersregel_aarsag",
            "sql": (
                "w.data::jsonb "
                "#>> %(aldersregel_aarsag_path)s"
            ),
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

    # Kolonnerne står i den rækkefølge, de skal vises i Excel.
    #
    # source refererer enten til:
    #
    # 1. Et standardfelt fra rapportmotoren.
    #
    # 2. name fra select_fields ovenfor.
    #
    # Besked indeholder én af:
    #
    #     Sendt til manuel behandling
    #
    #     Intern kontaktperson oprettet og
    #     Organisation oprettet
    #
    #     Intern kontaktperson oprettet
    #
    #     Organisation oprettet
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
            "header": "Besked",
            "source": "besked",
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
    ],
}