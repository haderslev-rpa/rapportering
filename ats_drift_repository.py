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

    VISNING I EXCEL
    ================

    Sessions vises som:

        completed/total

    total betyder i denne rapport:

        completed + failed

    Andre sessionstatusser tæller ikke med.

    Eksempel:

        2 COMPLETED
        1 FAILED
        1 anden sessionstatus

    Excel viser:

        2/3

    Den anden sessionstatus medregnes ikke.

    Dermed kan antal failed altid beregnes sådan:

        total - completed = failed

    Eksempel:

        2/3

        3 - 2 = 1 failed session


    SESSIONSTATUSSER
    =================

    Følgende status tæller i completed:

        COMPLETED

    Følgende status tæller i total, men ikke i completed:

        FAILED

    Alle andre statusser ignoreres, eksempelvis:

        RUNNING
        PENDING
        NEW
        CANCELLED
        STOPPED
        ERROR
        NULL

    Bemærk:

        Hvis databasen bruger en anden enum-værdi end FAILED
        for fejlede sessions, skal værdien tilføjes eksplicit.


    TIDSMODEL
    =========

    session.updated_at har PostgreSQL-typen:

        timestamp without time zone

    Værdierne er gemt som dansk lokalt klokkeslæt.

    Eksempel:

        2026-09-01 06:25:00

    Værdien skal fortolkes som:

        06:25 dansk tid

    report_now kommer fra:

        SELECT clock_timestamp();

    report_now er et entydigt tidspunkt med tidszone.

    Derfor konverteres session.updated_at sådan:

        s.updated_at
        AT TIME ZONE 'Europe/Copenhagen'

    Eksempel i dansk sommertid:

        Gemte updated_at:
            2026-09-01 06:25:00

        Fortolket som dansk tid:
            2026-09-01 06:25:00+02:00

        Samme tidspunkt i UTC:
            2026-09-01 04:25:00+00:00

    Konverteringen tager automatisk højde for:

        dansk sommertid
        dansk vintertid


    TIDSVINDUER
    ===========

    Tidsvinduerne er kumulative:

        24 timer
        48 timer
        72 timer
        7 dage
        14 dage
        30 dage
        40 dage

    En session fra de seneste 12 timer kan derfor tælle med i:

        S 24
        S 48
        S 72
        S 7 d
        S 14 d
        S 30 d
        S 40 d


    Input:
        report_now:
            Ét fælles tidszonebevidst referenceøjeblik fra
            PostgreSQL.

            Værdien kommer fra:

                SELECT clock_timestamp();


    Output:
        dict:

        {
            process_id: {
                "completed_24h": 2,
                "total_24h": 2,

                "completed_48h": 3,
                "total_48h": 4,

                "completed_72h": 6,
                "total_72h": 7,

                "completed_7d": 14,
                "total_7d": 15,

                "completed_14d": 33,
                "total_14d": 34,

                "completed_30d": 82,
                "total_30d": 102,

                "completed_40d": 109,
                "total_40d": 129,
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

                    -- -----------------------------------------
                    -- DANSK LOKALTID TIL ENTYDIGT TIDSPUNKT
                    -- -----------------------------------------
                    (
                        s.updated_at
                        AT TIME ZONE 'Europe/Copenhagen'
                    ) AS updated_at_utc,

                    -- -----------------------------------------
                    -- NORMALISER SESSIONSTATUS
                    -- -----------------------------------------
                    --
                    -- Sessionstatus er en PostgreSQL enum.
                    -- Derfor konverteres status først til tekst.
                    --
                    -- Eksempler:
                    --
                    --     Completed   -> COMPLETED
                    --     completed   -> COMPLETED
                    --     In progress -> IN_PROGRESS
                    --     In-progress -> IN_PROGRESS
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

                WHERE
                    -- -----------------------------------------
                    -- MAKSIMAL RAPPORTPERIODE: 40 DAGE
                    -- -----------------------------------------
                    (
                        s.updated_at
                        AT TIME ZONE 'Europe/Copenhagen'
                    ) > (
                        %(report_now)s
                        - INTERVAL '40 days'
                    )

                    AND (
                        s.updated_at
                        AT TIME ZONE 'Europe/Copenhagen'
                    ) <= %(report_now)s

                    AND COALESCE(
                        s.deleted,
                        FALSE
                    ) = FALSE
            )

            SELECT
                process_id,

                -- =============================================
                -- SENESTE 24 TIMER
                -- =============================================

                -- Tæller kun COMPLETED.
                COUNT(*) FILTER (
                    WHERE
                        updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '24 hours'
                        )

                        AND normalized_status = 'COMPLETED'
                ) AS completed_24h,

                -- Total er kun COMPLETED + FAILED.
                COUNT(*) FILTER (
                    WHERE
                        updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '24 hours'
                        )

                        AND normalized_status IN (
                            'COMPLETED',
                            'FAILED'
                        )
                ) AS total_24h,

                -- =============================================
                -- SENESTE 48 TIMER
                -- =============================================

                COUNT(*) FILTER (
                    WHERE
                        updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '48 hours'
                        )

                        AND normalized_status = 'COMPLETED'
                ) AS completed_48h,

                COUNT(*) FILTER (
                    WHERE
                        updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '48 hours'
                        )

                        AND normalized_status IN (
                            'COMPLETED',
                            'FAILED'
                        )
                ) AS total_48h,

                -- =============================================
                -- SENESTE 72 TIMER
                -- =============================================

                COUNT(*) FILTER (
                    WHERE
                        updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '72 hours'
                        )

                        AND normalized_status = 'COMPLETED'
                ) AS completed_72h,

                COUNT(*) FILTER (
                    WHERE
                        updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '72 hours'
                        )

                        AND normalized_status IN (
                            'COMPLETED',
                            'FAILED'
                        )
                ) AS total_72h,

                -- =============================================
                -- SENESTE 7 DAGE
                -- =============================================

                COUNT(*) FILTER (
                    WHERE
                        updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '7 days'
                        )

                        AND normalized_status = 'COMPLETED'
                ) AS completed_7d,

                COUNT(*) FILTER (
                    WHERE
                        updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '7 days'
                        )

                        AND normalized_status IN (
                            'COMPLETED',
                            'FAILED'
                        )
                ) AS total_7d,

                -- =============================================
                -- SENESTE 14 DAGE
                -- =============================================

                COUNT(*) FILTER (
                    WHERE
                        updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '14 days'
                        )

                        AND normalized_status = 'COMPLETED'
                ) AS completed_14d,

                COUNT(*) FILTER (
                    WHERE
                        updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '14 days'
                        )

                        AND normalized_status IN (
                            'COMPLETED',
                            'FAILED'
                        )
                ) AS total_14d,

                -- =============================================
                -- SENESTE 30 DAGE
                -- =============================================

                COUNT(*) FILTER (
                    WHERE
                        updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '30 days'
                        )

                        AND normalized_status = 'COMPLETED'
                ) AS completed_30d,

                COUNT(*) FILTER (
                    WHERE
                        updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '30 days'
                        )

                        AND normalized_status IN (
                            'COMPLETED',
                            'FAILED'
                        )
                ) AS total_30d,

                -- =============================================
                -- SENESTE 40 DAGE
                -- =============================================

                -- CTE'en er allerede begrænset til 40 dage.
                COUNT(*) FILTER (
                    WHERE normalized_status = 'COMPLETED'
                ) AS completed_40d,

                -- Total er fortsat kun COMPLETED + FAILED.
                COUNT(*) FILTER (
                    WHERE normalized_status IN (
                        'COMPLETED',
                        'FAILED'
                    )
                ) AS total_40d

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

    Workitems tælles på:

        workitem.updated_at

    TIDSMODEL
    =========

    workitem.updated_at har PostgreSQL-typen:

        timestamp without time zone

    Værdierne er gemt som dansk lokalt klokkeslæt.

    Eksempel:

        2026-09-01 06:25:00

    SQL skal derfor fortolke feltet som dansk tid:

        w.updated_at
        AT TIME ZONE 'Europe/Copenhagen'

    Resultatet bliver et entydigt timestamp with time zone,
    som kan sammenlignes korrekt med report_now.

    Konverteringen håndterer automatisk både:

        dansk sommertid
        dansk vintertid

    STATUSSER
    =========

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

    Status normaliseres, så eksempelvis:

        IN PROGRESS
        IN-PROGRESS
        IN_PROGRESS

    alle bliver:

        IN_PROGRESS

    DELTE WORKQUEUES
    =================

    Workitems er forbundet med workqueue_id og ikke direkte
    med process_id.

    Hvis flere processer bruger samme workqueue_id, får
    processerne derfor de samme workitem-tal.

    Sessionstallene er stadig særskilte, fordi sessions er
    forbundet direkte med process_id.

    Input:
        report_now:
            Ét fælles tidszonebevidst referenceøjeblik fra
            PostgreSQL.

    Output:
        dict:

        {
            workqueue_id: {
                "completed_24h": 5,
                "completed_48h": 10,
                "completed_72h": 15,
                "completed_7d": 30,
                "completed_14d": 60,
                "completed_30d": 100,
                "completed_40d": 125,

                "failed_24h": 1,
                "failed_48h": 2,
                "failed_72h": 2,
                "failed_7d": 4,
                "failed_14d": 5,
                "failed_30d": 8,
                "failed_40d": 10,

                "in_progress_40d": 2,
                "new_40d": 3,
                "pending_user_40d": 1,
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

                    -- -----------------------------------------
                    -- DANSK LOKALTID TIL ENTYDIGT TIDSPUNKT
                    -- -----------------------------------------
                    --
                    -- w.updated_at er timestamp without time zone
                    -- og indeholder dansk lokalt klokkeslæt.
                    (
                        w.updated_at
                        AT TIME ZONE 'Europe/Copenhagen'
                    ) AS updated_at_utc,

                    -- -----------------------------------------
                    -- NORMALISER WORKITEMSTATUS
                    -- -----------------------------------------
                    --
                    -- status kan være en PostgreSQL enum.
                    -- Derfor konverteres den først til tekst.
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

                WHERE
                    -- Begræns CTE'en til de seneste 40 dage.
                    (
                        w.updated_at
                        AT TIME ZONE 'Europe/Copenhagen'
                    ) > (
                        %(report_now)s
                        - INTERVAL '40 days'
                    )

                    AND (
                        w.updated_at
                        AT TIME ZONE 'Europe/Copenhagen'
                    ) <= %(report_now)s
            )

            SELECT
                workqueue_id,

                -- =============================================
                -- COMPLETED, 24 TIMER
                -- =============================================
                COUNT(*) FILTER (
                    WHERE
                        normalized_status = 'COMPLETED'

                        AND updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '24 hours'
                        )
                ) AS completed_24h,

                -- =============================================
                -- COMPLETED, 48 TIMER
                -- =============================================
                COUNT(*) FILTER (
                    WHERE
                        normalized_status = 'COMPLETED'

                        AND updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '48 hours'
                        )
                ) AS completed_48h,

                -- =============================================
                -- COMPLETED, 72 TIMER
                -- =============================================
                COUNT(*) FILTER (
                    WHERE
                        normalized_status = 'COMPLETED'

                        AND updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '72 hours'
                        )
                ) AS completed_72h,

                -- =============================================
                -- COMPLETED, 7 DAGE
                -- =============================================
                COUNT(*) FILTER (
                    WHERE
                        normalized_status = 'COMPLETED'

                        AND updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '7 days'
                        )
                ) AS completed_7d,

                -- =============================================
                -- COMPLETED, 14 DAGE
                -- =============================================
                COUNT(*) FILTER (
                    WHERE
                        normalized_status = 'COMPLETED'

                        AND updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '14 days'
                        )
                ) AS completed_14d,

                -- =============================================
                -- COMPLETED, 30 DAGE
                -- =============================================
                COUNT(*) FILTER (
                    WHERE
                        normalized_status = 'COMPLETED'

                        AND updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '30 days'
                        )
                ) AS completed_30d,

                -- =============================================
                -- COMPLETED, 40 DAGE
                -- =============================================
                --
                -- CTE'en indeholder allerede kun 40 dage.
                COUNT(*) FILTER (
                    WHERE normalized_status = 'COMPLETED'
                ) AS completed_40d,

                -- =============================================
                -- FAILED, 24 TIMER
                -- =============================================
                COUNT(*) FILTER (
                    WHERE
                        normalized_status = 'FAILED'

                        AND updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '24 hours'
                        )
                ) AS failed_24h,

                -- =============================================
                -- FAILED, 48 TIMER
                -- =============================================
                COUNT(*) FILTER (
                    WHERE
                        normalized_status = 'FAILED'

                        AND updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '48 hours'
                        )
                ) AS failed_48h,

                -- =============================================
                -- FAILED, 72 TIMER
                -- =============================================
                COUNT(*) FILTER (
                    WHERE
                        normalized_status = 'FAILED'

                        AND updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '72 hours'
                        )
                ) AS failed_72h,

                -- =============================================
                -- FAILED, 7 DAGE
                -- =============================================
                COUNT(*) FILTER (
                    WHERE
                        normalized_status = 'FAILED'

                        AND updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '7 days'
                        )
                ) AS failed_7d,

                -- =============================================
                -- FAILED, 14 DAGE
                -- =============================================
                COUNT(*) FILTER (
                    WHERE
                        normalized_status = 'FAILED'

                        AND updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '14 days'
                        )
                ) AS failed_14d,

                -- =============================================
                -- FAILED, 30 DAGE
                -- =============================================
                COUNT(*) FILTER (
                    WHERE
                        normalized_status = 'FAILED'

                        AND updated_at_utc > (
                            %(report_now)s
                            - INTERVAL '30 days'
                        )
                ) AS failed_30d,

                -- =============================================
                -- FAILED, 40 DAGE
                -- =============================================
                COUNT(*) FILTER (
                    WHERE normalized_status = 'FAILED'
                ) AS failed_40d,

                -- =============================================
                -- IN PROGRESS, 40 DAGE
                -- =============================================
                COUNT(*) FILTER (
                    WHERE normalized_status IN (
                        'IN_PROGRESS',
                        'IN_PROCESS',
                        'PROCESSING'
                    )
                ) AS in_progress_40d,

                -- =============================================
                -- NEW, 40 DAGE
                -- =============================================
                COUNT(*) FILTER (
                    WHERE normalized_status = 'NEW'
                ) AS new_40d,

                -- =============================================
                -- PENDING USER, 40 DAGE
                -- =============================================
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