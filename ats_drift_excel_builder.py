# ats_drift_excel_builder.py

"""
EXCEL-BUILDER TIL ATS-DRIFTSRAPPORT
===================================

Excel-arket har to overskriftsrækker.

RÆKKE 1
=======

Række 1 indeholder de overordnede grupper:

    Session completed/total
    Completed
    Failed
    In progress
    New
    Pending user

Hver gruppe har sin egen farve.

RÆKKE 2
=======

De første kolonner er:

    A = CRON
    B = Hvor ofte
    C = Processnavn

Derefter kommer:

    S 24
    S 48
    ...
    P 40 d

DATA
====

Række 3 og frem indeholder én række pr. proces.

Sessions vises som:

    completed/total

Eksempel:

    24/30

KOLONNEBREDDER
==============

CRON, Hvor ofte og Processnavn har kontrollerede bredder.

Session-, completed-, failed- og statuskolonner får automatisk
bredde ud fra:

    overskriftens længde
    den længste synlige værdi i kolonnen

Dette svarer omtrent til Excels automatiske kolonnebredde.

Der bruges samtidig:

    minimumsbredde
    maksimumsbredde

så kolonnerne hverken bliver for smalle eller urimeligt brede.
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import (
    Alignment,
    Border,
    Font,
    PatternFill,
    Side,
)
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import (
    Table,
    TableStyleInfo,
)

from time_helper import (
    now_danish_filename_string,
)


# =============================================================
# KOLONNER
# =============================================================

COLUMN_DEFINITIONS = [
    # ---------------------------------------------------------
    # FASTE OPLYSNINGER
    # ---------------------------------------------------------
    ("CRON", "cron_text"),
    ("Hvor ofte", "frequency_text"),
    ("Processnavn", "process_name"),

    # ---------------------------------------------------------
    # SESSION COMPLETED/TOTAL
    # ---------------------------------------------------------
    ("S 24", "session_24h"),
    ("S 48", "session_48h"),
    ("S 72", "session_72h"),
    ("S 7 d", "session_7d"),
    ("S 14 d", "session_14d"),
    ("S 30d", "session_30d"),
    ("S 40d", "session_40d"),

    # ---------------------------------------------------------
    # COMPLETED WORKITEMS
    # ---------------------------------------------------------
    ("C 24", "completed_24h"),
    ("C 48", "completed_48h"),
    ("C 72", "completed_72h"),
    ("C 7d", "completed_7d"),
    ("C 14d", "completed_14d"),
    ("C 30d", "completed_30d"),
    ("C 40d", "completed_40d"),

    # ---------------------------------------------------------
    # FAILED WORKITEMS
    # ---------------------------------------------------------
    ("F 24", "failed_24h"),
    ("F 48", "failed_48h"),
    ("F 72", "failed_72h"),
    ("F 7d", "failed_7d"),
    ("F 14d", "failed_14d"),
    ("F 30d", "failed_30d"),
    ("F 40d", "failed_40d"),

    # ---------------------------------------------------------
    # ØVRIGE STATUSSER
    # ---------------------------------------------------------
    ("I 40 d", "in_progress_40d"),
    ("N 40 d", "new_40d"),
    ("P 40 d", "pending_user_40d"),
]


# =============================================================
# FARVER
# =============================================================

COLOR_GENERAL = "0B5A7A"
COLOR_SESSIONS = "4472C4"
COLOR_COMPLETED = "70AD47"
COLOR_FAILED = "C00000"
COLOR_IN_PROGRESS = "ED7D31"
COLOR_NEW = "5B9BD5"
COLOR_PENDING_USER = "7030A0"

COLOR_DATA_ALTERNATING = "DDEBF7"
COLOR_BORDER = "A6A6A6"
COLOR_WHITE = "FFFFFF"


# =============================================================
# GRUPPER
# =============================================================

GROUP_DEFINITIONS = [
    {
        "title": "Session completed/total",
        "start_column": 4,
        "end_column": 10,
        "color": COLOR_SESSIONS,
    },
    {
        "title": "Completed",
        "start_column": 11,
        "end_column": 17,
        "color": COLOR_COMPLETED,
    },
    {
        "title": "Failed",
        "start_column": 18,
        "end_column": 24,
        "color": COLOR_FAILED,
    },
    {
        "title": "In progress",
        "start_column": 25,
        "end_column": 25,
        "color": COLOR_IN_PROGRESS,
    },
    {
        "title": "New",
        "start_column": 26,
        "end_column": 26,
        "color": COLOR_NEW,
    },
    {
        "title": "Pending user",
        "start_column": 27,
        "end_column": 27,
        "color": COLOR_PENDING_USER,
    },
]


def create_ats_drift_excel(
    rows,
    output_folder,
    excel_file_prefix,
):
    """
    Opretter ATS-driftsrapporten som Excel-fil.

    Input:
        rows:
            Liste med én dictionary pr. proces.

        output_folder:
            Mappe til Excel-filen.

        excel_file_prefix:
            Første del af filnavnet.

    Output:
        pathlib.Path:
            Stien til den oprettede Excel-fil.

            Eksempel:

                tests_local/
                ATS_driftrapport_25-08-2026_15-30-00.xlsx
    """

    output_path = Path(
        output_folder
    )

    output_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = now_danish_filename_string()

    file_path = output_path / (
        f"{excel_file_prefix}_{timestamp}.xlsx"
    )

    workbook = Workbook()

    worksheet = workbook.active
    worksheet.title = "ATS driftrapport"

    # ---------------------------------------------------------
    # GRUNDSTIL
    # ---------------------------------------------------------
    white_bold_font = Font(
        color=COLOR_WHITE,
        bold=True,
    )

    thin_border_side = Side(
        style="thin",
        color=COLOR_BORDER,
    )

    cell_border = Border(
        left=thin_border_side,
        right=thin_border_side,
        top=thin_border_side,
        bottom=thin_border_side,
    )

    center_alignment = Alignment(
        horizontal="center",
        vertical="center",
    )

    left_alignment = Alignment(
        horizontal="left",
        vertical="center",
    )

    wrap_left_alignment = Alignment(
        horizontal="left",
        vertical="center",
        wrap_text=True,
    )

    alternating_data_fill = PatternFill(
        fill_type="solid",
        fgColor=COLOR_DATA_ALTERNATING,
    )

    general_header_fill = PatternFill(
        fill_type="solid",
        fgColor=COLOR_GENERAL,
    )

    # ---------------------------------------------------------
    # RÆKKE 1, DE TRE FØRSTE KOLONNER
    # ---------------------------------------------------------
    for column_index in range(
        1,
        4,
    ):
        cell = worksheet.cell(
            row=1,
            column=column_index,
        )

        cell.fill = general_header_fill
        cell.border = cell_border

    # ---------------------------------------------------------
    # RÆKKE 1, GRUPPEOVERSKRIFTER
    # ---------------------------------------------------------
    for group in GROUP_DEFINITIONS:
        start_column = group[
            "start_column"
        ]

        end_column = group[
            "end_column"
        ]

        group_color = group[
            "color"
        ]

        group_fill = PatternFill(
            fill_type="solid",
            fgColor=group_color,
        )

        if start_column != end_column:
            worksheet.merge_cells(
                start_row=1,
                start_column=start_column,
                end_row=1,
                end_column=end_column,
            )

        group_cell = worksheet.cell(
            row=1,
            column=start_column,
            value=group["title"],
        )

        group_cell.fill = group_fill
        group_cell.font = white_bold_font
        group_cell.alignment = center_alignment
        group_cell.border = cell_border

        for column_index in range(
            start_column,
            end_column + 1,
        ):
            cell = worksheet.cell(
                row=1,
                column=column_index,
            )

            cell.fill = group_fill
            cell.border = cell_border

    # ---------------------------------------------------------
    # RÆKKE 2, KOLONNEOVERSKRIFTER
    # ---------------------------------------------------------
    for column_index, (
        header,
        _source,
    ) in enumerate(
        COLUMN_DEFINITIONS,
        start=1,
    ):
        cell = worksheet.cell(
            row=2,
            column=column_index,
            value=header,
        )

        header_color = _get_header_color(
            column_index
        )

        cell.fill = PatternFill(
            fill_type="solid",
            fgColor=header_color,
        )

        cell.font = white_bold_font
        cell.alignment = center_alignment
        cell.border = cell_border

    # ---------------------------------------------------------
    # DATA
    # ---------------------------------------------------------
    for row_index, row_data in enumerate(
        rows,
        start=3,
    ):
        for column_index, (
            _header,
            source,
        ) in enumerate(
            COLUMN_DEFINITIONS,
            start=1,
        ):
            value = row_data.get(
                source
            )

            # De første tre kolonner er tekst.
            if column_index <= 3:
                if value is None:
                    value = ""

            # De øvrige kolonner er tal eller sessionstekst.
            else:
                if value is None:
                    value = 0

            cell = worksheet.cell(
                row=row_index,
                column=column_index,
                value=value,
            )

            cell.border = cell_border

            if row_index % 2 == 1:
                cell.fill = alternating_data_fill

            if column_index == 1:
                # CRON kan indeholde flere linjer.
                cell.alignment = wrap_left_alignment

            elif column_index == 2:
                # Hvor ofte.
                cell.alignment = left_alignment

            elif column_index == 3:
                # Processnavn.
                cell.alignment = left_alignment

            else:
                cell.alignment = center_alignment

    # ---------------------------------------------------------
    # FILTER OG EXCEL-TABEL
    # ---------------------------------------------------------
    if rows:
        last_column_letter = get_column_letter(
            len(COLUMN_DEFINITIONS)
        )

        last_row = len(rows) + 2

        table_reference = (
            f"A2:"
            f"{last_column_letter}"
            f"{last_row}"
        )

        table = Table(
            displayName="ATSDriftrapport",
            ref=table_reference,
        )

        table_style = TableStyleInfo(
            name="TableStyleMedium2",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=False,
            showColumnStripes=False,
        )

        table.tableStyleInfo = table_style

        worksheet.add_table(
            table
        )

    # ---------------------------------------------------------
    # VISNING
    # ---------------------------------------------------------
    worksheet.freeze_panes = "D3"

    worksheet.row_dimensions[1].height = 25
    worksheet.row_dimensions[2].height = 25

    # De tre første kolonner får kontrollerede bredder.
    worksheet.column_dimensions["A"].width = 24
    worksheet.column_dimensions["B"].width = 16
    worksheet.column_dimensions["C"].width = 34

    # Sessions får automatisk bredde, fordi værdier som
    # 9222/9446 kan være længere end kolonneoverskriften.
    _autofit_columns(
        worksheet=worksheet,
        start_column=4,
        end_column=10,
        minimum_width=7,
        maximum_width=14,
        extra_padding=2,
    )

    # Completed får automatisk den mindst mulige bredde,
    # hvor både overskrift og største tal stadig kan ses.
    _autofit_columns(
        worksheet=worksheet,
        start_column=11,
        end_column=17,
        minimum_width=6,
        maximum_width=12,
        extra_padding=2,
    )

    # Failed får samme automatiske tilpasning.
    _autofit_columns(
        worksheet=worksheet,
        start_column=18,
        end_column=24,
        minimum_width=6,
        maximum_width=12,
        extra_padding=2,
    )

    # In progress, New og Pending user tilpasses også.
    _autofit_columns(
        worksheet=worksheet,
        start_column=25,
        end_column=27,
        minimum_width=7,
        maximum_width=14,
        extra_padding=2,
    )

    worksheet.sheet_view.showGridLines = False

    workbook.save(
        file_path
    )

    return file_path


def _get_header_color(column_index):
    """
    Finder farven til en kolonneoverskrift i række 2.

    Input:
        column_index:
            Excel-kolonnens nummer.

            Eksempel:

                1 = A
                2 = B
                3 = C
                4 = D

    Output:
        str:
            RGB-farve uden #.

            Eksempel:

                "4472C4"
    """

    if column_index <= 3:
        return COLOR_GENERAL

    for group in GROUP_DEFINITIONS:
        if (
            group["start_column"]
            <= column_index
            <= group["end_column"]
        ):
            return group["color"]

    return COLOR_GENERAL


def _autofit_columns(
    worksheet,
    start_column,
    end_column,
    minimum_width=6,
    maximum_width=20,
    extra_padding=2,
):
    """
    Tilpasser kolonnebredder efter det synlige indhold.

    Funktionen svarer omtrent til at dobbeltklikke på
    kolonnegrænsen i Excel.

    Input:
        worksheet:
            Excel-arket.

        start_column:
            Første kolonnenummer, som skal tilpasses.

        end_column:
            Sidste kolonnenummer, som skal tilpasses.

        minimum_width:
            Mindste tilladte kolonnebredde.

        maximum_width:
            Største tilladte kolonnebredde.

        extra_padding:
            Ekstra luft efter den længste værdi.

    Output:
        None.

    Bemærkning:
        Den flettede gruppeoverskrift i række 1 ignoreres.

        Bredden beregnes ud fra:
            række 2, kolonneoverskrift
            række 3 og frem, data
    """

    for column_index in range(
        start_column,
        end_column + 1,
    ):
        maximum_content_length = 0

        # Række 1 springes over, fordi gruppeoverskrifterne
        # er flettede og ellers ville gøre kolonnerne for brede.
        for row_index in range(
            2,
            worksheet.max_row + 1,
        ):
            cell_value = worksheet.cell(
                row=row_index,
                column=column_index,
            ).value

            if cell_value is None:
                continue

            # Ved eventuelle linjeskift måles den længste linje.
            text_lines = str(
                cell_value
            ).splitlines()

            if not text_lines:
                continue

            longest_line_length = max(
                len(line)
                for line in text_lines
            )

            maximum_content_length = max(
                maximum_content_length,
                longest_line_length,
            )

        calculated_width = (
            maximum_content_length
            + extra_padding
        )

        calculated_width = max(
            calculated_width,
            minimum_width,
        )

        calculated_width = min(
            calculated_width,
            maximum_width,
        )

        column_letter = get_column_letter(
            column_index
        )

        worksheet.column_dimensions[
            column_letter
        ].width = calculated_width