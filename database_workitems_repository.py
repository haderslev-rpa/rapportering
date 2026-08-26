# database_workitems_repository.py

from database_connection import get_connection


STANDARD_SELECT_FIELDS = [
    ("id", "w.id"),
    ("reference", "w.reference"),
    ("status", "w.status"),
    ("message", "w.message"),
    ("created_at", "w.created_at"),
    ("updated_at", "w.updated_at"),
    ("started_at", "w.started_at"),
    ("queue_name", "q.name"),
    ("data", "w.data"),
]


def get_database_time_minus_seconds(seconds=5):
    """
    Henter database-tid minus det angivne antal sekunder.

    Output:
        datetime:
            Database-tid med sikkerhedsbuffer.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                clock_timestamp()
                - (%s * interval '1 second')
                AS rapportering_end;
            """,
            (seconds,),
        )

        return cursor.fetchone()[0]

    finally:
        cursor.close()
        conn.close()


def count_workitems_for_report(
    kilde_queue,
    status_filter,
    time_field,
    rapportering_start,
    rapportering_end,
    extra_where_sql="",
    sql_parameters=None,
):
    """
    Tæller workitems med den faste grund-query og rapportens
    ekstra WHERE-filter.

    Output:
        int:
            Antal rows, som matcher rapporten.
    """

    _validate_time_field(time_field)

    where_sql, query_parameters = _build_where_parts(
        kilde_queue=kilde_queue,
        status_filter=status_filter,
        time_field=time_field,
        rapportering_start=rapportering_start,
        rapportering_end=rapportering_end,
        extra_where_sql=extra_where_sql,
        sql_parameters=sql_parameters,
    )

    query = f"""
    SELECT COUNT(*)
    FROM workitem w
    JOIN workqueue q
      ON w.workqueue_id = q.id
    {where_sql};
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            query,
            query_parameters,
        )

        return int(cursor.fetchone()[0])

    finally:
        cursor.close()
        conn.close()


def fetch_workitems_for_report(
    kilde_queue,
    status_filter,
    time_field,
    rapportering_start,
    rapportering_end,
    extra_where_sql="",
    sql_parameters=None,
    select_fields=None,
):
    """
    Henter workitems med standardfelter og rapportens
    ekstra select_fields.

    Output:
        list:
            Liste med dictionaries.

            Eksempel:
                [
                    {
                        "id": 123,
                        "reference": "ABC",
                        "status": "COMPLETED",
                        "message": "Manuel",
                        "created_at": datetime(...),
                        "manuel_behandling_aarsag": "...",
                    }
                ]
    """

    _validate_time_field(time_field)

    if select_fields is None:
        select_fields = []

    select_sql = _build_select_sql(
        select_fields
    )

    where_sql, query_parameters = _build_where_parts(
        kilde_queue=kilde_queue,
        status_filter=status_filter,
        time_field=time_field,
        rapportering_start=rapportering_start,
        rapportering_end=rapportering_end,
        extra_where_sql=extra_where_sql,
        sql_parameters=sql_parameters,
    )

    query = f"""
    SELECT
        {select_sql}
    FROM workitem w
    JOIN workqueue q
      ON w.workqueue_id = q.id
    {where_sql}
    ORDER BY w.{time_field}, w.id;
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            query,
            query_parameters,
        )

        column_names = [
            description[0]
            for description in cursor.description
        ]

        rows = cursor.fetchall()

        return [
            dict(zip(column_names, row))
            for row in rows
        ]

    finally:
        cursor.close()
        conn.close()


def find_last_rapportering_end(rapport_id):
    """
    Finder det seneste rapportering_end for samme rapport_id.

    Output:
        str:
            Seneste rapportering_end.

        None:
            Hvis der ikke findes historik.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                w.data -> 'box'
                       ->> 'rapportering_end'
            FROM workitem w
            JOIN workqueue q
              ON w.workqueue_id = q.id
            WHERE q.name = 'rapportering'
              AND w.data -> 'box'
                         ->> 'rapport_id' = %s
              AND w.data -> 'box'
                         ->> 'rapportering_end'
                         IS NOT NULL
            ORDER BY w.updated_at DESC, w.id DESC
            LIMIT 1;
            """,
            (rapport_id,),
        )

        row = cursor.fetchone()

        if not row:
            return None

        return row[0]

    finally:
        cursor.close()
        conn.close()


def find_last_mail_sendt_timestamp(rapport_id):
    """
    Finder seneste mail_sendt_tidspunkt for rapporten.

    Output:
        str:
            Seneste mail_sendt_tidspunkt.

        None:
            Hvis rapporten endnu ikke har sendt mail.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                w.data -> 'box'
                       ->> 'mail_sendt_tidspunkt'
            FROM workitem w
            JOIN workqueue q
              ON w.workqueue_id = q.id
            WHERE q.name = 'rapportering'
              AND w.data -> 'box'
                         ->> 'rapport_id' = %s
              AND w.data -> 'box'
                         ->> 'mail_sendt' = 'true'
              AND w.data -> 'box'
                         ->> 'mail_sendt_tidspunkt'
                         IS NOT NULL
            ORDER BY w.updated_at DESC, w.id DESC
            LIMIT 1;
            """,
            (rapport_id,),
        )

        row = cursor.fetchone()

        if not row:
            return None

        return row[0]

    finally:
        cursor.close()
        conn.close()


def _build_select_sql(select_fields):
    """
    Bygger SELECT-felterne.

    Output:
        str:
            Kommasepareret SELECT-liste med standardfelter
            og rapportens ekstra felter.
    """

    select_parts = []

    for name, sql_expression in STANDARD_SELECT_FIELDS:
        select_parts.append(
            f"{sql_expression} AS {name}"
        )

    for field in select_fields:
        name = field["name"]
        sql_expression = field["sql"].strip()

        _validate_identifier(name)
        _validate_sql_fragment(
            sql_expression,
            label=f"select field {name}",
        )

        select_parts.append(
            f"{sql_expression} AS {name}"
        )

    return ",\n        ".join(select_parts)

def _build_where_parts(
    kilde_queue,
    status_filter,
    time_field,
    rapportering_start,
    rapportering_end,
    extra_where_sql,
    sql_parameters,
):
    """
    Bygger den faste sikre WHERE-del plus rapportens ekstra filter.

    DATABASEENS TIDSMODEL
    =====================

    Workitem-tabellens tidsfelter er:

        created_at
        updated_at
        started_at

    Felterne har PostgreSQL-typen:

        timestamp without time zone

    Værdierne er gemt som dansk lokalt klokkeslæt.

    Eksempel:

        w.updated_at:
            2026-08-26 11:26:40

    Værdien har ingen tidszoneinformation i selve kolonnen,
    men klokkeslættet skal forstås som:

        Europe/Copenhagen

    Rapportens tekniske periodefelter er derimod UTC-baserede:

        rapportering_start
        rapportering_end

    Eksempel:

        rapportering_end:
            2026-08-26 09:29:13+00:00

    Derfor må databasefeltet ikke sammenlignes direkte med
    rapporteringsgrænserne.

    Forkert sammenligning:

        w.updated_at <= rapportering_end

    Dette kan sammenligne:

        11:26 <= 09:29

    selv om klokkeslættene i virkeligheden repræsenterer:

        11:26 dansk tid
        =
        09:26 UTC

    Korrekt sammenligning:

        (
            w.updated_at
            AT TIME ZONE 'Europe/Copenhagen'
        ) <= rapportering_end

    PostgreSQL fortolker dermed det gemte klokkeslæt som
    dansk tid og konverterer værdien til et entydigt
    timestamp with time zone.

    Eksempel:

        Gemte værdi:
            2026-08-26 11:26:40

        Fortolket som dansk sommertid:
            2026-08-26 11:26:40+02:00

        Samme tidspunkt i UTC:
            2026-08-26 09:26:40+00:00

    Denne konvertering håndterer både dansk sommertid
    og dansk vintertid via tidszonen:

        Europe/Copenhagen

    FAST SIKKER GRUND-QUERY
    =======================

    Funktionen tilføjer altid disse filtre:

        1. q.name matcher kilde_queue

        2. w.status matcher status_filter

        3. Det valgte time_field ligger efter
           rapportering_start

        4. Det valgte time_field ligger før eller lig med
           rapportering_end

    Rapportens extra_where_sql kan kun tilføje flere
    AND-betingelser.

    VIGTIGT
    =======

    time_field sættes ind i SQL som et kolonnenavn.

    Derfor valideres feltet først med:

        _validate_time_field()

    De øvrige værdier sendes som psycopg2-parametre og
    sættes ikke direkte ind med f-strings.

    Input:
        kilde_queue:
            Det præcise navn fra workqueue.name.

        status_filter:
            Den ønskede workitem-status.

            Eksempel:
                COMPLETED

        time_field:
            Et af de tilladte tidsfelter:

                created_at
                updated_at
                started_at

        rapportering_start:
            Teknisk starttidspunkt for rapportperioden.

        rapportering_end:
            Teknisk sluttidspunkt for rapportperioden.

        extra_where_sql:
            Rapportens ekstra SQL-filter.

            Skal være tom tekst eller begynde med AND.

        sql_parameters:
            Dictionary med rapportens parameteriserede
            SQL-værdier.

    Output:
        tuple:

            (
                where_sql,
                query_parameters,
            )

        where_sql:
            Den komplette WHERE-del.

        query_parameters:
            Dictionary med både rapportmotorens faste
            parametre og rapportens egne parametre.
    """

    # ---------------------------------------------------------
    # VALIDÉR TIDSFELT
    # ---------------------------------------------------------
    #
    # time_field indsættes som kolonnenavn i SQL og skal
    # derfor være på rapportmotorens faste tilladelsesliste.
    _validate_time_field(
        time_field
    )

    # ---------------------------------------------------------
    # NORMALISÉR SQL-PARAMETRE
    # ---------------------------------------------------------
    if sql_parameters is None:
        sql_parameters = {}

    if not isinstance(
        sql_parameters,
        dict,
    ):
        raise ValueError(
            "sql_parameters skal være en dict"
        )

    # Lav en kopi, så rapportens oprindelige dictionary
    # ikke bliver ændret.
    query_parameters = dict(
        sql_parameters
    )

    # ---------------------------------------------------------
    # BESKYT RAPPORTMOTORENS INTERNE PARAMETERNAVNE
    # ---------------------------------------------------------
    reserved_parameter_names = {
        "base_kilde_queue",
        "base_status_filter",
        "base_rapportering_start",
        "base_rapportering_end",
    }

    conflicts = (
        reserved_parameter_names
        & set(query_parameters.keys())
    )

    if conflicts:
        raise ValueError(
            "sql_parameters bruger reserverede navne: "
            f"{sorted(conflicts)}"
        )

    # ---------------------------------------------------------
    # TILFØJ RAPPORTMOTORENS FASTE PARAMETRE
    # ---------------------------------------------------------
    query_parameters.update(
        {
            "base_kilde_queue": kilde_queue,
            "base_status_filter": status_filter,
            "base_rapportering_start": (
                rapportering_start
            ),
            "base_rapportering_end": (
                rapportering_end
            ),
        }
    )

    # ---------------------------------------------------------
    # BYG DEN FASTE SIKRE WHERE-DEL
    # ---------------------------------------------------------
    #
    # Workitemets time_field er timestamp without time zone
    # og indeholder dansk lokalt klokkeslæt.
    #
    # AT TIME ZONE 'Europe/Copenhagen' fortolker værdien
    # som dansk tid og returnerer et entydigt tidspunkt,
    # som kan sammenlignes korrekt med rapporteringsvinduets
    # UTC-værdier.
    #
    # Dette fungerer automatisk ved både:
    #
    #     sommertid, UTC+02:00
    #     vintertid, UTC+01:00
    where_sql = f"""
    WHERE q.name = %(base_kilde_queue)s

      AND w.status = %(base_status_filter)s

      AND (
            w.{time_field}
            AT TIME ZONE 'Europe/Copenhagen'
          ) > %(base_rapportering_start)s

      AND (
            w.{time_field}
            AT TIME ZONE 'Europe/Copenhagen'
          ) <= %(base_rapportering_end)s
    """

    # ---------------------------------------------------------
    # TILFØJ RAPPORTENS EKSTRA WHERE-FILTER
    # ---------------------------------------------------------
    cleaned_extra_where_sql = (
        extra_where_sql
        or ""
    ).strip()

    if cleaned_extra_where_sql:
        _validate_extra_where_sql(
            cleaned_extra_where_sql
        )

        where_sql += (
            "\n      "
            + cleaned_extra_where_sql
        )

    return (
        where_sql,
        query_parameters,
    )

def _validate_time_field(time_field):
    """
    Tillader kun kendte tidskolonner.

    Output:
        None ved gyldigt felt.
    """

    allowed = {
        "created_at",
        "updated_at",
        "started_at",
    }

    if time_field not in allowed:
        raise ValueError(
            f"Ugyldigt time_field: {time_field}. "
            f"Tilladte værdier: {sorted(allowed)}"
        )


def _validate_identifier(value):
    """
    Validerer et SQL-alias.

    Output:
        None ved gyldigt navn.
    """

    if not isinstance(value, str) or not value:
        raise ValueError(
            "SQL-identifikator mangler"
        )

    if value[0].isdigit():
        raise ValueError(
            f"SQL-identifikator må ikke starte "
            f"med et tal: {value}"
        )

    if not value.replace("_", "").isalnum():
        raise ValueError(
            f"Ugyldig SQL-identifikator: {value}"
        )


def _validate_sql_fragment(
    sql_fragment,
    label,
):
    """
    Udfører en enkel sikkerhedskontrol af SQL fra Git-config.

    Output:
        None ved gyldigt fragment.
    """

    if not isinstance(sql_fragment, str):
        raise ValueError(
            f"{label} skal være tekst"
        )

    if not sql_fragment.strip():
        raise ValueError(
            f"{label} er tom"
        )

    if ";" in sql_fragment:
        raise ValueError(
            f"{label} må ikke indeholde semikolon"
        )


def _validate_extra_where_sql(extra_where_sql):
    """
    Kontrollerer rapportens ekstra WHERE-del.

    Output:
        None ved gyldigt fragment.
    """

    _validate_sql_fragment(
        extra_where_sql,
        label="extra_where_sql",
    )

    if not extra_where_sql.upper().startswith("AND "):
        raise ValueError(
            "extra_where_sql skal begynde med AND"
        )