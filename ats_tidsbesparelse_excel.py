from __future__ import annotations
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter
from ats_tidsbesparelse_config import ATS_TIDSBESPARELSE_CONFIG

COLUMNS=("Er sumlinje","Rækketype","Detailniveau","Datoperspektiv","Måned","Queue Name","Resultat",
"Matchregel-ID","Matchtype","Matchende tags","Rå tags","Antal items","Itemmarkør","Minutter pr. item",
"Faste minutter pr. måned","Besparede minutter","Besparede timer")

def create_excel(rows: list[dict], period_text: str) -> Path:
    folder=Path(ATS_TIDSBESPARELSE_CONFIG["output_folder"]); folder.mkdir(parents=True,exist_ok=True)
    path=folder/f"{ATS_TIDSBESPARELSE_CONFIG['excel_file_prefix']}_{period_text.replace(' ','_')}.xlsx"
    wb=Workbook(); ws=wb.active; ws.title="ATS"
    ws.append(COLUMNS)
    for row in rows: ws.append([row[name] for name in COLUMNS])
    header=ws[1]
    for cell in header:
        cell.fill=PatternFill("solid",fgColor="17365D"); cell.font=Font(color="FFFFFF",bold=True)
        cell.alignment=Alignment(wrap_text=True,vertical="top")
    ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
    if rows:
        table=Table(displayName="ATS_TidsbesparelseTable",ref=ws.dimensions)
        table.tableStyleInfo=TableStyleInfo(name="TableStyleMedium2",showRowStripes=True,showColumnStripes=False)
        ws.add_table(table)
    for row in range(2,ws.max_row+1): ws.cell(row,5).number_format="dd-mm-yyyy"
    for col in range(14,18):
        for row in range(2,ws.max_row+1): ws.cell(row,col).number_format="0.00"
    widths={1:12,2:12,3:24,4:18,5:13,6:34,7:34,8:38,9:18,10:42,11:55,12:13,13:13,14:18,15:24,16:22,17:18}
    for col,width in widths.items(): ws.column_dimensions[get_column_letter(col)].width=width
    for row in ws.iter_rows(min_row=2):
        for cell in row: cell.alignment=Alignment(wrap_text=True,vertical="top")
    wb.save(path); return path
