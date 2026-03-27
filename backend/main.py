import io
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

import document_handler

load_dotenv()

app = FastAPI(title="Plagiarism Remover API")

# In production set ALLOWED_ORIGINS to your Netlify URL, e.g.:
# ALLOWED_ORIGINS=https://your-app.netlify.app
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",")] if _raw_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Serve bundled frontend (used in local/single-server mode)
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

EXTENSION_MAP  = {".docx": "docx", ".pdf": "pdf", ".txt": "txt"}
CONTENT_TYPES  = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf":  "application/pdf",
    "txt":  "text/plain; charset=utf-8",
}

# Groq models available on free tier
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
    return {
        "groq": "configured",
        "models": sorted(ALLOWED_MODELS),
    }


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
            result  = document_handler.process_txt(content, model)
            out_ext = ".txt"
        elif file_type == "docx":
            result  = document_handler.process_docx(content, model)
            out_ext = ".docx"
        else:  # pdf
            result  = document_handler.process_pdf(content, model)
            out_ext = ".pdf" if result[:4] == b"%PDF" else ".docx"
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

    stem         = Path(filename).stem
    out_filename = f"{stem}_paraphrased{out_ext}"
    content_type = CONTENT_TYPES.get(out_ext.lstrip("."), "application/octet-stream")

    return Response(
        content=result,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{out_filename}"',
            "X-Output-Filename":   out_filename,
        },
    )
