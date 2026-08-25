# ats_drift_repository.py

"""
DATABASEADGANG TIL ATS-DRIFTSRAPPORT
====================================

TABELLER
=======

process
    Én række pr. Automation Server-proces.

    Relevante felter:
        id
        name
        description
        workqueue_id
        deleted

session
    Én række pr. proceskørsel.

    Sammenhæng:
        session.process_id = process.id

    Relevante felter:
        process_id
        status
        updated_at

workqueue
    Én række pr. workqueue.

    Sammenhæng:
        process.workqueue_id = workqueue.id

workitem
    Én række pr. workitem.

    Sammenhæng:
        workitem.workqueue_id = workqueue.id

    Relevante felter:
        workqueue_id
        status
        updated_at

trigger
    Proces-, cron-, workqueue- og datotriggers.

    Sammenhæng:
        trigger.process_id = process.id

VIGTIGT OM DELTE WORKQUEUES
===========================

Et workitem har workqueue_id, men ikke process_id.

Hvis to processer bruger samme workqueue_id:

    Process A -> workqueue 2
    Process B -> workqueue 2

så får begge processer de samme workitem-tal.

Sessions tælles fortsat separat pr. process_id.
"""

from database_connection import get_connection


WINDOWS = {
    "24h": "24 hours",
    "48h": "48 hours",
    "72h": "72 hours",
    "7d": "7 days",
    "14d": "14 days",
    "30d": "30 days",
    "40d": "40 days",
}


def get_database_now():
    """
    Henter database-serverens aktuelle tidspunkt.

    Output:
        datetime:
            Ét fælles referenceøjeblik til hele rapporten.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT clock_timestamp();"
        )

        return cursor.fetchone()[0]

    finally:
        cursor.close()
        conn.close()


def fetch_active_processes():
    """
    Henter alle processer, som ikke er markeret slettet.

    Output:
        list:
            Liste med dictionaries:

            [
                {
                    "process_id": 1,
                    "process_name": "Test1",
                    "description": "...",
                    "workqueue_id": 1
                }
            ]
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                p.id AS process_id,
                p.name AS process_name,
                p.description,
                p.workqueue_id
            FROM process p
            WHERE COALESCE(p.deleted, FALSE) = FALSE
            ORDER BY LOWER(p.name), p.id;
            """
        )

        column_names = [
            description[0]
            for description in cursor.description
        ]

        return [
            dict(zip(column_names, row))
            for row in cursor.fetchall()
        ]

    finally:
        cursor.close()
        conn.close()


def fetch_session_counts(report_now):
    """
    Henter sessiontal pr. process_id.

    Sessions tælles på session.updated_at.

    Session-status er en PostgreSQL enum.
    Derfor konverteres status til tekst med:

        s.status::text

    før værdien normaliseres og sammenlignes.

    For hvert tidsvindue returneres:

        completed
        total

    Tidsvinduerne er kumulative:

        24 timer
        48 timer
        72 timer
        7 dage
        14 dage
        30 dage
        40 dage

    Output:
        dict:

        {
            process_id: {
                "completed_24h": 4,
                "total_24h": 5,
                "completed_48h": 8,
                "total_48h": 10,
                ...
            }
        }
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            WITH normalized_sessions AS (
                SELECT
                    s.process_id,
                    s.updated_at,

                    UPPER(
                        REPLACE(
                            REPLACE(
                                COALESCE(
                                    s.status::text,
                                    ''
                                ),
                                ' ',
                                '_'
                            ),
                            '-',
                            '_'
                        )
                    ) AS normalized_status

                FROM "session" s

                WHERE s.updated_at > %(report_now)s
                        - INTERVAL '40 days'
                  AND s.updated_at <= %(report_now)s
                  AND COALESCE(
                        s.deleted,
                        FALSE
                      ) = FALSE
            )

            SELECT
                process_id,

                COUNT(*) FILTER (
                    WHERE updated_at > %(report_now)s
                            - INTERVAL '24 hours'
                      AND normalized_status = 'COMPLETED'
                ) AS completed_24h,

                COUNT(*) FILTER (
                    WHERE updated_at > %(report_now)s
                            - INTERVAL '24 hours'
                ) AS total_24h,

                COUNT(*) FILTER (
                    WHERE updated_at > %(report_now)s
                            - INTERVAL '48 hours'
                      AND normalized_status = 'COMPLETED'
                ) AS completed_48h,

                COUNT(*) FILTER (
                    WHERE updated_at > %(report_now)s
                            - INTERVAL '48 hours'
                ) AS total_48h,

                COUNT(*) FILTER (
                    WHERE updated_at > %(report_now)s
                            - INTERVAL '72 hours'
                      AND normalized_status = 'COMPLETED'
                ) AS completed_72h,

                COUNT(*) FILTER (
                    WHERE updated_at > %(report_now)s
                            - INTERVAL '72 hours'
                ) AS total_72h,

                COUNT(*) FILTER (
                    WHERE updated_at > %(report_now)s
                            - INTERVAL '7 days'
                      AND normalized_status = 'COMPLETED'
                ) AS completed_7d,

                COUNT(*) FILTER (
                    WHERE updated_at > %(report_now)s
                            - INTERVAL '7 days'
                ) AS total_7d,

                COUNT(*) FILTER (
                    WHERE updated_at > %(report_now)s
                            - INTERVAL '14 days'
                      AND normalized_status = 'COMPLETED'
                ) AS completed_14d,

                COUNT(*) FILTER (
                    WHERE updated_at > %(report_now)s
                            - INTERVAL '14 days'
                ) AS total_14d,

                COUNT(*) FILTER (
                    WHERE updated_at > %(report_now)s
                            - INTERVAL '30 days'
                      AND normalized_status = 'COMPLETED'
                ) AS completed_30d,

                COUNT(*) FILTER (
                    WHERE updated_at > %(report_now)s
                            - INTERVAL '30 days'
                ) AS total_30d,

                COUNT(*) FILTER (
                    WHERE normalized_status = 'COMPLETED'
                ) AS completed_40d,

                COUNT(*) AS total_40d

            FROM normalized_sessions

            GROUP BY process_id;
            """,
            {
                "report_now": report_now,
            },
        )

        column_names = [
            description[0]
            for description in cursor.description
        ]

        result = {}

        for row in cursor.fetchall():
            row_data = dict(
                zip(
                    column_names,
                    row,
                )
            )

            process_id = row_data.pop(
                "process_id"
            )

            result[process_id] = row_data

        return result

    finally:
        cursor.close()
        conn.close()


def fetch_workitem_counts(report_now):
    """
    Henter workitem-tal pr. workqueue_id.

    Workitems tælles på workitem.updated_at.

    Workitem-status kan være en PostgreSQL enum.
    Derfor konverteres status til tekst med:

        w.status::text

    før værdien normaliseres og sammenlignes.

    Completed og failed tælles for:

        24 timer
        48 timer
        72 timer
        7 dage
        14 dage
        30 dage
        40 dage

    In progress, new og pending user tælles for:

        40 dage

    Hvis flere processer bruger samme workqueue_id,
    får processerne de samme workitem-tal.

    Output:
        dict:

        {
            workqueue_id: {
                "completed_24h": 5,
                "completed_40d": 100,
                "failed_24h": 1,
                "failed_40d": 4,
                "in_progress_40d": 2,
                "new_40d": 3,
                "pending_user_40d": 1
            }
        }
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            WITH normalized_workitems AS (
                SELECT
                    w.workqueue_id,
                    w.updated_at,

                    UPPER(
                        REPLACE(
                            REPLACE(
                                COALESCE(
                                    w.status::text,
                                    ''
                                ),
                                ' ',
                                '_'
                            ),
                            '-',
                            '_'
                        )
                    ) AS normalized_status

                FROM workitem w

                WHERE w.updated_at > %(report_now)s
                        - INTERVAL '40 days'
                  AND w.updated_at <= %(report_now)s
            )

            SELECT
                workqueue_id,

                COUNT(*) FILTER (
                    WHERE normalized_status = 'COMPLETED'
                      AND updated_at > %(report_now)s
                            - INTERVAL '24 hours'
                ) AS completed_24h,

                COUNT(*) FILTER (
                    WHERE normalized_status = 'COMPLETED'
                      AND updated_at > %(report_now)s
                            - INTERVAL '48 hours'
                ) AS completed_48h,

                COUNT(*) FILTER (
                    WHERE normalized_status = 'COMPLETED'
                      AND updated_at > %(report_now)s
                            - INTERVAL '72 hours'
                ) AS completed_72h,

                COUNT(*) FILTER (
                    WHERE normalized_status = 'COMPLETED'
                      AND updated_at > %(report_now)s
                            - INTERVAL '7 days'
                ) AS completed_7d,

                COUNT(*) FILTER (
                    WHERE normalized_status = 'COMPLETED'
                      AND updated_at > %(report_now)s
                            - INTERVAL '14 days'
                ) AS completed_14d,

                COUNT(*) FILTER (
                    WHERE normalized_status = 'COMPLETED'
                      AND updated_at > %(report_now)s
                            - INTERVAL '30 days'
                ) AS completed_30d,

                COUNT(*) FILTER (
                    WHERE normalized_status = 'COMPLETED'
                ) AS completed_40d,

                COUNT(*) FILTER (
                    WHERE normalized_status = 'FAILED'
                      AND updated_at > %(report_now)s
                            - INTERVAL '24 hours'
                ) AS failed_24h,

                COUNT(*) FILTER (
                    WHERE normalized_status = 'FAILED'
                      AND updated_at > %(report_now)s
                            - INTERVAL '48 hours'
                ) AS failed_48h,

                COUNT(*) FILTER (
                    WHERE normalized_status = 'FAILED'
                      AND updated_at > %(report_now)s
                            - INTERVAL '72 hours'
                ) AS failed_72h,

                COUNT(*) FILTER (
                    WHERE normalized_status = 'FAILED'
                      AND updated_at > %(report_now)s
                            - INTERVAL '7 days'
                ) AS failed_7d,

                COUNT(*) FILTER (
                    WHERE normalized_status = 'FAILED'
                      AND updated_at > %(report_now)s
                            - INTERVAL '14 days'
                ) AS failed_14d,

                COUNT(*) FILTER (
                    WHERE normalized_status = 'FAILED'
                      AND updated_at > %(report_now)s
                            - INTERVAL '30 days'
                ) AS failed_30d,

                COUNT(*) FILTER (
                    WHERE normalized_status = 'FAILED'
                ) AS failed_40d,

                COUNT(*) FILTER (
                    WHERE normalized_status IN (
                        'IN_PROGRESS',
                        'IN_PROCESS',
                        'PROCESSING'
                    )
                ) AS in_progress_40d,

                COUNT(*) FILTER (
                    WHERE normalized_status = 'NEW'
                ) AS new_40d,

                COUNT(*) FILTER (
                    WHERE normalized_status IN (
                        'PENDING_USER',
                        'PENDINGUSER'
                    )
                ) AS pending_user_40d

            FROM normalized_workitems

            GROUP BY workqueue_id;
            """,
            {
                "report_now": report_now,
            },
        )

        column_names = [
            description[0]
            for description in cursor.description
        ]

        result = {}

        for row in cursor.fetchall():
            row_data = dict(
                zip(
                    column_names,
                    row,
                )
            )

            workqueue_id = row_data.pop(
                "workqueue_id"
            )

            result[workqueue_id] = row_data

        return result

    finally:
        cursor.close()
        conn.close()


def fetch_active_triggers():
    """
    Henter aktive triggers grupperet pr. process_id.

    Null i enabled behandles som aktiv for at understøtte
    ældre trigger-rækker.

    Output:
        dict:
            {
                process_id: [
                    {
                        "trigger_id": 1,
                        "type": "CRON",
                        "cron": "0 7 * * *",
                        "parameters": "--queue"
                    }
                ]
            }
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                t.id AS trigger_id,
                t.process_id,
                t.type,
                t.cron,
                t.date,
                t.workqueue_id,
                t.parameters
            FROM "trigger" t
            WHERE COALESCE(t.deleted, FALSE) = FALSE
              AND COALESCE(t.enabled, TRUE) = TRUE
              AND t.process_id IS NOT NULL
            ORDER BY t.process_id, t.id;
            """
        )

        column_names = [
            description[0]
            for description in cursor.description
        ]

        triggers_by_process = {}

        for row in cursor.fetchall():
            trigger_data = dict(
                zip(column_names, row)
            )

            process_id = trigger_data.pop(
                "process_id"
            )

            triggers_by_process.setdefault(
                process_id,
                [],
            ).append(trigger_data)

        return triggers_by_process

    finally:
        cursor.close()
        conn.close()


def find_shared_workqueues(processes):
    """
    Finder workqueues som bruges af flere processer.

    Output:
        dict:
            {
                workqueue_id: [
                    "Proces A",
                    "Proces B"
                ]
            }

        Kun workqueues med mere end én proces returneres.
    """

    workqueue_processes = {}

    for process in processes:
        workqueue_id = process.get(
            "workqueue_id"
        )

        if workqueue_id is None:
            continue

        workqueue_processes.setdefault(
            workqueue_id,
            [],
        ).append(
            process.get("process_name")
        )

    return {
        workqueue_id: process_names
        for workqueue_id, process_names
        in workqueue_processes.items()
        if len(process_names) > 1
    }