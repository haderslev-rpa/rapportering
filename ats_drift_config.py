# ats_drift_config.py

"""
KONFIGURATION TIL ATS-DRIFTSRAPPORT
===================================

ATS-driftsrapporten er en selvstændig rapport, som startes med:

    --ats-drift

Rapporten bruger ikke den almindelige rapportmotor og opretter
ikke et rapportering-item.

Rapporten:

1. Henter alle aktive processer fra process-tabellen.
2. Fjerner processer, som står i excluded_process_names.
3. Henter sessions for hver resterende proces.
4. Henter workitem-tal via processens workqueue_id.
5. Henter aktive triggers.
6. Sorterer processerne efter kørselsfrekvens.
7. Opretter en Excel-fil.
8. Sender Excel-filen med q-outlook-api.

TIDSVINDUER
===========

Alle tidsvinduer er kumulative.

Eksempel:

    S 24:
        Sessions opdateret inden for de seneste 24 timer.

    S 48:
        Sessions opdateret inden for de seneste 48 timer.

En session fra de seneste 12 timer tæller derfor med i både:

    S 24
    S 48
    S 72
    S 7d
    S 14d
    S 30d
    S 40d

Samme princip bruges til completed og failed workitems.

UDELAD PROCESSER
================

Listen excluded_process_names indeholder processer, som aldrig
skal vises i ATS-driftsrapporten.

Eksempel:

    "excluded_process_names": [
        "Test1",
        "ats-playwright-test",
    ]

Sammenligningen:

    - ignorerer store og små bogstaver
    - ignorerer mellemrum før og efter navnet

Disse navne bliver derfor betragtet som ens:

    Test1
    test1
    TEST1
    " Test1 "

Navnet skal ellers være et præcist procesnavn.

Hvis flere processer skal udelades i fremtiden, tilføjes de blot:

    "excluded_process_names": [
        "Test1",
        "ats-playwright-test",
        "en-anden-proces",
    ]

En udeladt proces:

    - kommer ikke med som række i Excel
    - påvirker ikke antallet af rapporterede processer
    - indgår ikke i kontrollen for delte workqueues

WEEKEND OG HELLIGDAGE
=====================

skip_weekends=True:
    Rapporten sendes ikke lørdag eller søndag.

skip_public_holidays=False:
    Danske helligdage kontrolleres ikke i første version.
"""


ATS_DRIFT_CONFIG = {
    # ---------------------------------------------------------
    # RAPPORT
    # ---------------------------------------------------------
    "report_name": "ATS driftrapport",

    "excel_file_prefix": "ATS_driftrapport",

    "output_folder": "tests_local",

    # Maksimal historik i rapporten.
    "history_days": 40,

    # ---------------------------------------------------------
    # PROCESSER DER IKKE SKAL MED
    # ---------------------------------------------------------
    #
    # Tilføj flere procesnavne her, hvis de aldrig skal vises
    # i ATS-driftsrapporten.
    #
    # Sammenligningen er case-insensitive:
    #     Test1 = test1 = TEST1
    "excluded_process_names": [
        "Test1",
        "ats-playwright-test",
    ],

    # ---------------------------------------------------------
    # KALENDER
    # ---------------------------------------------------------
    "skip_weekends": True,

    # Ikke implementeret/aktiveret i første version.
    "skip_public_holidays": False,

    # ---------------------------------------------------------
    # MAIL
    # ---------------------------------------------------------
    "sender_mail": "robot-data@haderslev.dk",

    "to": [
        "automatisering@haderslev.dk",
    ],

    "cc": [],

    "bcc": [],

    "mail_subject": "ATS driftrapport",

    "mail_body": (
        "Hej\n\n"
        "Vedhæftet er den daglige ATS-driftsrapport.\n\n"
        "Rapporten viser sessions og workitem-statusser "
        "for de seneste 40 dage.\n"
        "Rapport dannet: {created_at_dk}\n\n"
        "Sessions vises som completed/total.\n\n"
        "Venlig hilsen\n"
        "Robotten"
    ),

    "save_to_sent_items": True,
}


def validate_ats_drift_config():
    """
    Validerer konfigurationen.

    Output:
        None:
            Hvis konfigurationen er gyldig.

    Fejl:
        ValueError:
            Hvis nødvendige værdier mangler eller har
            en forkert datatype.
    """

    required_keys = [
        "report_name",
        "excel_file_prefix",
        "output_folder",
        "history_days",
        "excluded_process_names",
        "skip_weekends",
        "skip_public_holidays",
        "sender_mail",
        "to",
        "cc",
        "bcc",
        "mail_subject",
        "mail_body",
        "save_to_sent_items",
    ]

    for key in required_keys:
        if key not in ATS_DRIFT_CONFIG:
            raise ValueError(
                f"ATS_DRIFT_CONFIG mangler nøgle: {key}"
            )

    # ---------------------------------------------------------
    # HISTORIK
    # ---------------------------------------------------------
    history_days = ATS_DRIFT_CONFIG[
        "history_days"
    ]

    if not isinstance(
        history_days,
        int,
    ):
        raise ValueError(
            "history_days skal være et heltal"
        )

    if history_days <= 0:
        raise ValueError(
            "history_days skal være større end 0"
        )

    # ---------------------------------------------------------
    # UDELADTE PROCESSER
    # ---------------------------------------------------------
    excluded_process_names = ATS_DRIFT_CONFIG[
        "excluded_process_names"
    ]

    if not isinstance(
        excluded_process_names,
        list,
    ):
        raise ValueError(
            "excluded_process_names skal være en liste"
        )

    seen_excluded_names = set()

    for process_index, process_name in enumerate(
        excluded_process_names,
        start=1,
    ):
        if not isinstance(
            process_name,
            str,
        ):
            raise ValueError(
                "excluded_process_names indeholder en værdi, "
                f"som ikke er tekst på plads {process_index}"
            )

        normalized_name = _normalize_process_name(
            process_name
        )

        if not normalized_name:
            raise ValueError(
                "excluded_process_names indeholder et tomt "
                f"procesnavn på plads {process_index}"
            )

        if normalized_name in seen_excluded_names:
            raise ValueError(
                "Dublet fundet i excluded_process_names: "
                f"{process_name}"
            )

        seen_excluded_names.add(
            normalized_name
        )

    # ---------------------------------------------------------
    # BOOLEAN-INDSTILLINGER
    # ---------------------------------------------------------
    if not isinstance(
        ATS_DRIFT_CONFIG["skip_weekends"],
        bool,
    ):
        raise ValueError(
            "skip_weekends skal være True eller False"
        )

    if not isinstance(
        ATS_DRIFT_CONFIG[
            "skip_public_holidays"
        ],
        bool,
    ):
        raise ValueError(
            "skip_public_holidays skal være True eller False"
        )

    if not isinstance(
        ATS_DRIFT_CONFIG[
            "save_to_sent_items"
        ],
        bool,
    ):
        raise ValueError(
            "save_to_sent_items skal være True eller False"
        )

    # ---------------------------------------------------------
    # MAIL
    # ---------------------------------------------------------
    sender_mail = str(
        ATS_DRIFT_CONFIG["sender_mail"] or ""
    ).strip()

    if not sender_mail:
        raise ValueError(
            "sender_mail mangler i ATS_DRIFT_CONFIG"
        )

    for recipient_key in (
        "to",
        "cc",
        "bcc",
    ):
        recipients = ATS_DRIFT_CONFIG[
            recipient_key
        ]

        if not isinstance(
            recipients,
            list,
        ):
            raise ValueError(
                f"{recipient_key} skal være en liste"
            )

    recipients = (
        list(
            ATS_DRIFT_CONFIG.get("to") or []
        )
        + list(
            ATS_DRIFT_CONFIG.get("cc") or []
        )
        + list(
            ATS_DRIFT_CONFIG.get("bcc") or []
        )
    )

    if not recipients:
        raise ValueError(
            "ATS-driftsrapporten har ingen modtagere"
        )


def _normalize_process_name(process_name):
    """
    Normaliserer et procesnavn til sammenligning.

    Input:
        process_name:
            Eksempel:

                " Test1 "

    Output:
        str:
            Eksempel:

                "test1"

    casefold bruges, fordi funktionen er mere robust end
    lower ved sammenligning af tekst.
    """

    return str(
        process_name or ""
    ).strip().casefold()