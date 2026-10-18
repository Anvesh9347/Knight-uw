"""Labeled-value parsing must not mistake prose for a labeled value."""
from app.extract import _labeled_values
from app.ingest import Doc


def _doc(kind, text):
    return Doc("x", len(text), kind, text=text, pages=[text])


def test_email_prose_is_not_a_labeled_value():
    assert _labeled_values(_doc("EMAIL", "Operations are mostly local"), "operations_description") == []


def test_email_colon_form_and_pdf_table_form_still_parse():
    assert _labeled_values(_doc("EMAIL", "Operations: Local delivery."), "operations_description")[0][0] == "Local delivery."
    assert _labeled_values(_doc("APPLICATION", "Operations description Local delivery"),
                           "operations_description")[0][0] == "Local delivery"
