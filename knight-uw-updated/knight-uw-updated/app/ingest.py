"""Read uploaded files, classify them and build the attachment inventory (deterministic)."""
import csv
import io
import re
from dataclasses import dataclass, field
from typing import Optional

EXPECTED_HEADER = ["vehicle_id", "vin", "year", "make", "model"]
LOSS_TITLE = re.compile(r"loss\s+runs?|loss\s+history|loss\s+experience", re.I)
LOSS_FILENAME = re.compile(r"loss|claims?[_ -]?hist", re.I)


@dataclass
class Doc:
    name: str
    size: int
    kind: str                       # EMAIL | APPLICATION | LOSS_RUNS | OTHER_PDF | VEHICLE_SCHEDULE | UNSUPPORTED
    readable: bool = True
    note: str = ""
    text: str = ""                  # full text (email body or all PDF pages)
    pages: list = field(default_factory=list)
    potential_loss_runs: bool = False
    csv_count: Optional[int] = None
    csv_error: Optional[str] = None
    csv_ids: list = field(default_factory=list)

    def inventory(self) -> dict:
        return {"filename": self.name, "size_bytes": self.size, "type": self.kind,
                "readable": self.readable, "note": self.note}


def _read_pdf(name: str, data: bytes) -> Doc:
    import pdfplumber  # imported lazily so non-PDF paths and tests stay light
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [(p.extract_text() or "").strip() for p in pdf.pages]
    except Exception as e:  # corrupt / encrypted / not a PDF
        return Doc(name, len(data), "OTHER_PDF", readable=False, note=f"PDF could not be read ({type(e).__name__})",
                   potential_loss_runs=bool(LOSS_FILENAME.search(name)))
    text = "\n".join(pages).strip()
    if not text:
        return Doc(name, len(data), "OTHER_PDF", readable=False, pages=pages,
                   note="PDF has no selectable text (scanned PDFs / OCR are out of scope)",
                   potential_loss_runs=bool(LOSS_FILENAME.search(name)))
    head = " ".join(text.splitlines()[:3])  # classify on the document title, not on passing mentions
    if LOSS_TITLE.search(head):
        kind, note = "LOSS_RUNS", "Classified as loss runs / loss history report from its title"
    elif re.search(r"application", head, re.I):
        kind, note = "APPLICATION", "Classified as application from its title"
    else:
        kind, note = "OTHER_PDF", "Readable PDF, not recognised as application or loss runs"
    return Doc(name, len(data), kind, pages=pages, text=text, note=note,
               potential_loss_runs=(kind == "OTHER_PDF" and bool(LOSS_FILENAME.search(name))))


def _read_csv(name: str, data: bytes) -> Doc:
    doc = Doc(name, len(data), "VEHICLE_SCHEDULE")
    try:
        rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"), newline="")))
    except (UnicodeDecodeError, csv.Error) as e:
        doc.readable, doc.csv_error = False, f"CSV could not be parsed ({type(e).__name__})"
        doc.note = doc.csv_error
        return doc
    if not rows:
        doc.readable, doc.csv_error = False, "CSV is empty (no header row)"
        doc.note = doc.csv_error
        return doc
    header = [c.strip().lower() for c in rows[0]]
    if header != EXPECTED_HEADER:
        doc.readable = False
        doc.csv_error = f"Unexpected header {rows[0]!r}; expected {','.join(EXPECTED_HEADER)}"
        doc.note = doc.csv_error
        return doc
    data_rows = [r for r in rows[1:] if any(c.strip() for c in r)]  # nonblank records only
    doc.csv_count = len(data_rows)
    doc.csv_ids = [r[0].strip() for r in data_rows if r]
    doc.note = f"{doc.csv_count} nonblank data rows (header excluded)"
    return doc


def ingest(files: list, email_text: str = "") -> list:
    """files: list of (filename, bytes). email_text: pasted broker email (optional)."""
    docs = []
    if email_text and email_text.strip():
        t = email_text.strip()
        docs.append(Doc("pasted_broker_email.txt", len(t.encode()), "EMAIL", text=t, pages=[t],
                        note="Pasted email text"))
    for name, data in files:
        low = name.lower()
        if low.endswith(".pdf"):
            docs.append(_read_pdf(name, data))
        elif low.endswith(".csv"):
            docs.append(_read_csv(name, data))
        elif low.endswith((".txt", ".eml")):
            t = data.decode("utf-8", errors="replace").strip()
            docs.append(Doc(name, len(data), "EMAIL", text=t, pages=[t], readable=bool(t),
                            note="Email text" if t else "Empty file"))
        else:
            docs.append(Doc(name, len(data), "UNSUPPORTED", readable=False, note="Unsupported file type; ignored"))
    return docs
