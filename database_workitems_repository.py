# database_workitems_repository.py

from database_connection import get_connection


def get_database_time_minus_seconds(seconds=5):
    """
    Henter database-tid minus X sekunder.

    funktion (genbrugelig kodeblok)
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT clock_timestamp() - (%s * interval '1 second') AS rapportering_end;",
        (seconds,),
    )

    result = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return result


def count_workitems_for_report(
    kilde_queue,
    status_filter,
    time_field,
    rapportering_start,
    rapportering_end,
):
    """
    Tæller workitems i rapportperioden.

    funktion (genbrugelig kodeblok)
    """

    _validate_time_field(time_field)

    conn = get_connection()
    cursor = conn.cursor()

    query = f"""
    SELECT COUNT(*)
    FROM workitem w
    JOIN workqueue q ON w.workqueue_id = q.id
    WHERE q.name = %s
      AND w.status = %s
      AND w.{time_field} > %s
      AND w.{time_field} <= %s;
    """

    cursor.execute(
        query,
        (
            kilde_queue,
            status_filter,
            rapportering_start,
            rapportering_end,
        ),
    )

    count = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return int(count)


def fetch_workitems_for_report(
    kilde_queue,
    status_filter,
    time_field,
    rapportering_start,
    rapportering_end,
):
    """
    Henter workitems til Excel.

    funktion (genbrugelig kodeblok)
    """

    _validate_time_field(time_field)

    conn = get_connection()
    cursor = conn.cursor()

    query = f"""
    SELECT
        w.id,
        w.reference,
        w.status,
        w.message,
        w.created_at,
        w.updated_at,
        w.started_at,
        q.name AS queue_name,
        w.data
    FROM workitem w
    JOIN workqueue q ON w.workqueue_id = q.id
    WHERE q.name = %s
      AND w.status = %s
      AND w.{time_field} > %s
      AND w.{time_field} <= %s
    ORDER BY w.{time_field}, w.id;
    """

    cursor.execute(
        query,
        (
            kilde_queue,
            status_filter,
            rapportering_start,
            rapportering_end,
        ),
    )

    rows = cursor.fetchall()

    result = []
    for row in rows:
        result.append(
            {
                "id": row[0],
                "reference": row[1],
                "status": row[2],
                "message": row[3],
                "created_at": row[4],
                "updated_at": row[5],
                "started_at": row[6],
                "queue_name": row[7],
                "data": row[8] or {},
            }
        )

    cursor.close()
    conn.close()

    return result


def find_last_rapportering_end(rapport_id):
    """
    Finder seneste rapportering_end for samme rapport_id.

    funktion (genbrugelig kodeblok)
    """

    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT
        w.data -> 'box' ->> 'rapportering_end'
    FROM workitem w
    JOIN workqueue q ON w.workqueue_id = q.id
    WHERE q.name = 'rapportering'
      AND w.data -> 'box' ->> 'rapport_id' = %s
      AND w.data -> 'box' ->> 'rapportering_end' IS NOT NULL
    ORDER BY w.updated_at DESC, w.id DESC
    LIMIT 1;
    """

    cursor.execute(query, (rapport_id,))
    row = cursor.fetchone()

    cursor.close()
    conn.close()

    if not row:
        return None

    return row[0]


def find_last_mail_sendt_timestamp(rapport_id):
    """
    Finder tidspunkt for seneste rapport hvor mail_sendt=true.

    funktion (genbrugelig kodeblok)
    """

    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT
        w.data -> 'box' ->> 'mail_sendt_tidspunkt'
    FROM workitem w
    JOIN workqueue q ON w.workqueue_id = q.id
    WHERE q.name = 'rapportering'
      AND w.data -> 'box' ->> 'rapport_id' = %s
      AND w.data -> 'box' ->> 'mail_sendt' = 'true'
      AND w.data -> 'box' ->> 'mail_sendt_tidspunkt' IS NOT NULL
    ORDER BY w.updated_at DESC, w.id DESC
    LIMIT 1;
    """

    cursor.execute(query, (rapport_id,))
    row = cursor.fetchone()

    cursor.close()
    conn.close()

    if not row:
        return None

    return row[0]


def _validate_time_field(time_field):
    """
    Sikrer at time_field er tilladt.

    funktion (genbrugelig kodeblok)
    """

    allowed = ["created_at", "updated_at", "started_at"]

    if time_field not in allowed:
        raise ValueError(
            f"Ugyldigt time_field: {time_field}. Tilladte værdier: {allowed}"
        )