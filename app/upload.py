"""Reads an uploaded master CV to plain text: .md, .txt, .pdf (pdftotext) or .docx (python-docx).

Limits: 2 MB per file; a .docx may unzip to at most 20 MB in at most 500 parts, so a "zip bomb" can't
blow up memory. The old .doc format isn't accepted. The text is shown back to the user before saving.
"""
import io
import subprocess
import tempfile
import zipfile
from pathlib import Path

MAX_BYTES = 2 * 1024 * 1024
MAX_UNZIPPED = 20 * 1024 * 1024
MAX_PARTS = 500
MAX_CHARS = 60_000


class UploadError(ValueError):
    """The message is shown to the user."""


def read(filename, data):
    ext = Path(filename or "").suffix.lower()
    if len(data) > MAX_BYTES:
        raise UploadError("That file is over 2 MB. Try a smaller one.")
    if not data:
        raise UploadError("That file is empty.")
    if ext in (".md", ".txt"):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("cp1252", errors="replace")
    elif ext == ".pdf":
        text = _pdf(data)
    elif ext == ".docx":
        text = _docx(data)
    elif ext == ".doc":
        raise UploadError("Old .doc files don't work. Save it as .docx or PDF and upload that.")
    else:
        raise UploadError("Use a .docx, .pdf, .md or .txt file.")
    text = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")).strip()
    if len(text) < 200:
        raise UploadError("We could read almost no text from that file. If it's a scanned PDF, upload a .docx or text version.")
    if len(text) > MAX_CHARS:
        raise UploadError("That CV is very long. Keep the master CV under about 8,000 words.")
    return text


def _pdf(data):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        try:
            r = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            raise UploadError("We couldn't read that PDF. Try a .docx or text version.") from None
    if r.returncode != 0:
        raise UploadError("We couldn't read that PDF. Try a .docx or text version.")
    return r.stdout


def _docx(data):
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        infos = z.infolist()
    except zipfile.BadZipFile:
        raise UploadError("That .docx file looks damaged. Try saving it again.") from None
    if len(infos) > MAX_PARTS or sum(i.file_size for i in infos) > MAX_UNZIPPED:
        raise UploadError("That .docx file is too large inside. Try a PDF instead.")
    import docx  # loaded only on upload (+7 MB)
    try:
        doc = docx.Document(io.BytesIO(data))
    except Exception:  # python-docx raises several types for bad files
        raise UploadError("We couldn't read that .docx file. Try a PDF instead.") from None
    lines = []
    for block in doc.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            lines.append("".join(t.text or "" for t in block.iter() if t.tag.endswith("}t")))
        elif tag == "tbl":
            for row in block.iter():
                if row.tag.endswith("}tr"):
                    cells = []
                    for cell in row:
                        if cell.tag.endswith("}tc"):
                            cells.append(" ".join("".join(t.text or "" for t in p.iter() if t.tag.endswith("}t"))
                                                  for p in cell.iter() if p.tag.endswith("}p")).strip())
                    lines.append(" | ".join(c for c in cells if c))
    return "\n".join(lines)
