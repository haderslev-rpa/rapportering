from __future__ import annotations
from datetime import datetime
from psycopg2.extras import RealDictCursor
from q_haderslev_vbo.automation_server.ats_database_connection import get_connection


def resolve_queue_ids(queue_names: set[str]) -> dict[str, int]:
    if not queue_names or any(not str(name).strip() for name in queue_names):
        raise ValueError("Queue-navne må ikke være tomme.")
    connection=None
    try:
        connection=get_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT id, name FROM public.workqueue WHERE lower(name) = ANY(%s) ORDER BY id", ([n.casefold() for n in queue_names],))
            rows=[dict(row) for row in cursor.fetchall()]
    finally:
        if connection is not None: connection.close()
    by_name={}
    for row in rows:
        key=str(row["name"]).casefold()
        if key in by_name:
            raise RuntimeError(f"Flere Automation Server-queues hedder {row['name']!r}.")
        by_name[key]=int(row["id"])
    missing=sorted(name for name in queue_names if name.casefold() not in by_name)
    if missing: raise RuntimeError(f"Aktive queue-navne blev ikke fundet i Automation Server: {missing}")
    return {name:by_name[name.casefold()] for name in queue_names}


def fetch_completed_workitems(queue_ids: dict[str,int], start_utc: datetime, end_utc_exclusive: datetime) -> list[dict]:
    id_to_name={value:key for key,value in queue_ids.items()}
    connection=None
    try:
        connection=get_connection()
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT id, reference, data, workqueue_id, updated_at
                FROM public.workitem
                WHERE workqueue_id = ANY(%s)
                  AND status::text = 'COMPLETED'
                  AND updated_at >= %s::timestamp
                  AND updated_at < %s::timestamp
                ORDER BY updated_at, id
            """, (list(id_to_name), start_utc, end_utc_exclusive))
            rows=[dict(row) for row in cursor.fetchall()]
    finally:
        if connection is not None: connection.close()
    for row in rows: row["queue_name"]=id_to_name[int(row["workqueue_id"])]
    return rows
