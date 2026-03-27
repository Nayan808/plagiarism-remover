import io
import os
import re
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from groq import Groq
from docx import Document
import fitz  # PyMuPDF
from pdf2docx import Converter
from mangum import Mangum

load_dotenv()

# ── Paraphraser ──────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a professional paraphrasing assistant. "
    "Rewrite the given text to make it completely unique and plagiarism-free "
    "while preserving the original meaning, tone, and technical accuracy. "
    "Do NOT add explanations, notes, or commentary. "
    "Return ONLY the rewritten text."
)


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY environment variable is not set. "
            "Get a free key at https://console.groq.com"
        )
    return Groq(api_key=api_key)


def paraphrase_text(text: str, model: str = "llama-3.1-8b-instant") -> str:
    text = text.strip()
    if not text or len(text) < 10:
        return text
    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Paraphrase this:\n\n{text}"},
        ],
        temperature=0.7,
        max_tokens=2048,
    )
    result = response.choices[0].message.content.strip()
    result = re.sub(r'^["\']|["\']$', "", result).strip()
    return result


# ── Document Handler ─────────────────────────────────────────────

def _get_para_full_text(para) -> str:
    return "".join(run.text for run in para.runs)


def _set_para_text_preserve_format(para, new_text: str):
    if not para.runs:
        para.text = new_text
        return
    para.runs[0].text = new_text
    for run in para.runs[1:]:
        run.text = ""


def process_txt(content: bytes, model: str) -> bytes:
    text = content.decode("utf-8", errors="ignore")
    paragraphs = text.split("\n")
    output_parts = []
    for para in paragraphs:
        if para.strip():
            output_parts.append(paraphrase_text(para, model))
        else:
            output_parts.append(para)
    return "\n".join(output_parts).encode("utf-8")


def process_docx(content: bytes, model: str) -> bytes:
    doc = Document(io.BytesIO(content))
    for para in doc.paragraphs:
        original = _get_para_full_text(para).strip()
        if original:
            _set_para_text_preserve_format(para, paraphrase_text(original, model))
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    original = _get_para_full_text(para).strip()
                    if original:
                        _set_para_text_preserve_format(para, paraphrase_text(original, model))
    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output.read()


def _docx_to_pdf(docx_path: str, tmpdir: str, pdf_out: str) -> bytes:
    import subprocess
    import shutil
    lo_path = shutil.which("soffice") or shutil.which("libreoffice")
    if lo_path:
        try:
            subprocess.run(
                [lo_path, "--headless", "--convert-to", "pdf", "--outdir", tmpdir, docx_path],
                check=True, capture_output=True, timeout=120,
            )
            out_pdf = os.path.join(tmpdir, Path(docx_path).stem + ".pdf")
            if os.path.exists(out_pdf):
                with open(out_pdf, "rb") as f:
                    return f.read()
        except Exception:
            pass
    with open(docx_path, "rb") as f:
        return f.read()


def process_pdf(content: bytes, model: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_in = os.path.join(tmpdir, "input.pdf")
        docx_converted = os.path.join(tmpdir, "converted.docx")
        docx_processed = os.path.join(tmpdir, "processed.docx")
        pdf_out = os.path.join(tmpdir, "output.pdf")
        with open(pdf_in, "wb") as f:
            f.write(content)
        cv = Converter(pdf_in)
        cv.convert(docx_converted, start=0, end=None)
        cv.close()
        with open(docx_converted, "rb") as f:
            docx_bytes = f.read()
        processed_bytes = process_docx(docx_bytes, model)
        with open(docx_processed, "wb") as f:
            f.write(processed_bytes)
        return _docx_to_pdf(docx_processed, tmpdir, pdf_out)


# ── FastAPI App ──────────────────────────────────────────────────

app = FastAPI(title="Plagiarism Remover API")

_raw_origins = os.environ.get("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",")] if _raw_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["X-Output-Filename"],
)

EXTENSION_MAP = {".docx": "docx", ".pdf": "pdf", ".txt": "txt"}
CONTENT_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf":  "application/pdf",
    "txt":  "text/plain; charset=utf-8",
}
ALLOWED_MODELS = {
    "llama-3.1-8b-instant",
    "llama-3.1-70b-versatile",
    "llama3-8b-8192",
    "mixtral-8x7b-32768",
}


@app.get("/")
def root():
    return {"status": "Plagiarism Remover API is running"}


@app.get("/health")
def health():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return {"groq": "missing", "error": "GROQ_API_KEY not set"}
    return {"groq": "configured", "models": sorted(ALLOWED_MODELS)}


@app.post("/process")
async def process_file(
    file: UploadFile = File(...),
    model: str = Form(default="llama-3.1-8b-instant"),
):
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    file_type = EXTENSION_MAP.get(ext)

    if not file_type:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Use .docx, .pdf, or .txt",
        )

    if model not in ALLOWED_MODELS:
        model = "llama-3.1-8b-instant"

    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 20 MB.")

    try:
        if file_type == "txt":
            result = process_txt(content, model)
            out_ext = ".txt"
        elif file_type == "docx":
            result = process_docx(content, model)
            out_ext = ".docx"
        else:
            result = process_pdf(content, model)
            out_ext = ".pdf" if result[:4] == b"%PDF" else ".docx"
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

    stem = Path(filename).stem
    out_filename = f"{stem}_paraphrased{out_ext}"
    content_type = CONTENT_TYPES.get(out_ext.lstrip("."), "application/octet-stream")

    return Response(
        content=result,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{out_filename}"',
            "X-Output-Filename": out_filename,
        },
    )


# Vercel serverless handler
handler = Mangum(app, lifespan="off")
