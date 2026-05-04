"""Tests for CSV and Excel export utilities."""

from app.utils.export_csv import export_to_csv
from app.utils.export_excel import export_to_excel


def test_export_to_csv():
    data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
    columns = ["name", "age"]
    csv_str = export_to_csv(data, columns)
    assert "name,age" in csv_str
    assert "Alice,30" in csv_str


def test_export_to_excel():
    data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
    columns = ["name", "age"]
    excel_bytes = export_to_excel(data, columns)
    assert excel_bytes[:4] == b"PK\x03\x04"  # ZIP magic number for XLSX
