import io
import zipfile

from app.services.ai_service import AIService


def test_extract_xlsx_text_reads_shared_and_inline_cells():
    shared_strings = """<?xml version="1.0" encoding="UTF-8"?>
    <sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
      <si><t>Nama Task</t></si><si><t>Pondasi</t></si>
    </sst>"""
    sheet = """<?xml version="1.0" encoding="UTF-8"?>
    <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
      <sheetData>
        <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="inlineStr"><is><t>Progress</t></is></c></row>
        <row r="2"><c r="A2" t="s"><v>1</v></c><c r="B2"><v>45</v></c></row>
      </sheetData>
    </worksheet>"""
    workbook = io.BytesIO()
    with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr("xl/sharedStrings.xml", shared_strings)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)

    extracted = AIService._extract_document_text(workbook.getvalue(), "progress.xlsx")

    assert "Nama Task\tProgress" in extracted
    assert "Pondasi\t45" in extracted
