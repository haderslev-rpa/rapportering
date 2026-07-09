# database_connection.py

import psycopg2

from credentials_ats_database import get_database_settings


def get_connection():
    """
    Opretter forbindelse til PostgreSQL.

    funktion (genbrugelig kodeblok)

    Database-settings er allerede cachet i credentials_ats_database.py.
    """

    settings = get_database_settings()

    conn = psycopg2.connect(
        host=settings["host"],
        port=settings["port"],
        database=settings["database"],
        user=settings["user"],
        password=settings["password"],
    )

    return conn
