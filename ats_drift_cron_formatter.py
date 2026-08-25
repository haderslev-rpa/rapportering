# ats_drift_cron_formatter.py

"""
CRON-OVERSÆTTELSE TIL ATS-DRIFTSRAPPORT
=======================================

Formålet er ikke at oversætte alle tænkelige cron-udtryk
helt præcist.

Formålet er at vise en kort og menneskelig cirka-beskrivelse:

    Time
    Daglig
    Uge
    Måned
    Måned (3)
    Queue
    Datostyret

Den tekniske cron vises stadig i kolonnen CRON, så den
oprindelige information ikke går tabt.

Cron-formatet forventes at have fem felter:

    minut time dag_i_måned måned ugedag

Eksempler:

    */5 * * * *
        Time

    0 7,12 * * *
        Daglig

    1 9 * * 1
        Uge

    1 9 10 * *
        Måned

    1 9 10 */3 *
        Måned (3)

Hvis en proces ikke har nogen aktiv trigger:

    CRON:
        blank

    Hvor ofte:
        blank

Hvis processen har en WORKQUEUE-trigger, men ingen cron-trigger:

    CRON:
        blank

    Hvor ofte:
        Queue
"""


def describe_triggers(triggers):
    """
    Bygger CRON-tekst og menneskelig beskrivelse.

    Input:
        triggers:
            Liste med trigger-dictionaries.

            Eksempel:

            [
                {
                    "trigger_id": 3,
                    "type": "CRON",
                    "cron": "0 7,12 * * *",
                    "parameters": "--queue",
                }
            ]

    Output:
        dict:

        Ved cron-trigger:

            {
                "cron_text": "0 7,12 * * *",
                "frequency_text": "Daglig",
            }

        Ved workqueue-trigger:

            {
                "cron_text": "",
                "frequency_text": "Queue",
            }

        Uden aktiv trigger:

            {
                "cron_text": "",
                "frequency_text": "",
            }
    """

    # ---------------------------------------------------------
    # INGEN AKTIVE TRIGGERS
    # ---------------------------------------------------------
    if not triggers:
        return {
            "cron_text": "",
            "frequency_text": "",
        }

    # ---------------------------------------------------------
    # CRON-TRIGGERS
    # ---------------------------------------------------------
    cron_triggers = [
        trigger
        for trigger in triggers
        if str(
            trigger.get("type") or ""
        ).upper() == "CRON"
        and str(
            trigger.get("cron") or ""
        ).strip()
    ]

    if cron_triggers:
        cron_values = []
        descriptions = []

        for trigger in cron_triggers:
            cron_text = str(
                trigger.get("cron") or ""
            ).strip()

            if cron_text not in cron_values:
                cron_values.append(cron_text)

            description = describe_cron(
                cron_text
            )

            if description not in descriptions:
                descriptions.append(
                    description
                )

        return {
            "cron_text": "\n".join(
                cron_values
            ),
            "frequency_text": "\n".join(
                descriptions
            ),
        }

    # ---------------------------------------------------------
    # WORKQUEUE-TRIGGER
    # ---------------------------------------------------------
    has_workqueue_trigger = any(
        str(
            trigger.get("type") or ""
        ).upper() == "WORKQUEUE"
        for trigger in triggers
    )

    if has_workqueue_trigger:
        return {
            "cron_text": "",
            "frequency_text": "Queue",
        }

    # ---------------------------------------------------------
    # DATE-TRIGGER
    # ---------------------------------------------------------
    has_date_trigger = any(
        str(
            trigger.get("type") or ""
        ).upper() == "DATE"
        for trigger in triggers
    )

    if has_date_trigger:
        return {
            "cron_text": "",
            "frequency_text": "Datostyret",
        }

    # ---------------------------------------------------------
    # UKENDT ELLER IKKE AKTIV TRIGGERTYPE
    # ---------------------------------------------------------
    return {
        "cron_text": "",
        "frequency_text": "",
    }


def describe_cron(cron_text):
    """
    Oversætter et fem-felts cron-udtryk cirka.

    Input:
        cron_text:
            Eksempel:

                "0 7,12 * * *"

    Output:
        str:

            "Time"
            "Daglig"
            "Uge"
            "Måned"
            "Måned (3)"
            "Specialplan"

    Oversættelsen er bevidst cirka.

    Eksempel:

        0 7,12 * * *

    bliver blot:

        Daglig
    """

    parts = str(
        cron_text or ""
    ).strip().split()

    if len(parts) != 5:
        return "Specialplan"

    minute_field = parts[0]
    hour_field = parts[1]
    day_of_month_field = parts[2]
    month_field = parts[3]
    day_of_week_field = parts[4]

    # ---------------------------------------------------------
    # HVER N. MÅNED
    # ---------------------------------------------------------
    month_interval = _extract_step(
        month_field
    )

    if (
        month_interval is not None
        and month_interval > 1
    ):
        return f"Måned ({month_interval})"

    # Bestemt måned eller bestemt dag i måneden.
    if (
        month_field != "*"
        or day_of_month_field != "*"
    ):
        return "Måned"

    # ---------------------------------------------------------
    # BESTEMTE UGEDAGE
    # ---------------------------------------------------------
    if day_of_week_field != "*":
        return "Uge"

    # ---------------------------------------------------------
    # HVER TIME ELLER FLERE GANGE PR. TIME
    # ---------------------------------------------------------
    if hour_field == "*":
        return "Time"

    # ---------------------------------------------------------
    # FASTE TIDER HVER DAG
    # ---------------------------------------------------------
    if hour_field != "*":
        return "Daglig"

    # ---------------------------------------------------------
    # FALLBACK
    # ---------------------------------------------------------
    if minute_field:
        return "Specialplan"

    return "Specialplan"


def _extract_step(field_value):
    """
    Finder step-værdien fra eksempelvis */3.

    Input:
        field_value:
            Eksempel:

                "*/3"

    Output:
        int:
            Eksempel:

                3

        None:
            Hvis feltet ikke er et step-udtryk.
    """

    text = str(
        field_value or ""
    ).strip()

    if not text.startswith("*/"):
        return None

    step_text = text[2:]

    try:
        return int(
            step_text
        )

    except ValueError:
        return None