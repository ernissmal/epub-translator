from __future__ import annotations

import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from epub_translator import LLM, SubmitKind, translate

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
DATA_DIR = Path(os.getenv("EPUB_TRANSLATOR_DATA_DIR", "/tmp/epub-translator"))
MAX_UPLOAD_BYTES = int(os.getenv("EPUB_TRANSLATOR_MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))


@dataclass
class Job:
    id: str
    filename: str
    target_language: str
    mode: str
    status: str = "queued"
    progress: float = 0.0
    message: str = "Waiting to start"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    output_path: str | None = None


app = FastAPI(title="Books Translator", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
jobs: dict[str, Job] = {}
jobs_lock = threading.Lock()


def _settings() -> dict[str, str]:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return {
        "key": key,
        "url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "model": os.getenv("EPUB_TRANSLATOR_MODEL", "gpt-4o-mini"),
        "fill_model": os.getenv("EPUB_TRANSLATOR_FILL_MODEL", ""),
        "token_encoding": os.getenv("EPUB_TRANSLATOR_TOKEN_ENCODING", "o200k_base"),
    }


def _build_llms(job_id: str) -> tuple[LLM, LLM]:
    settings = _settings()
    common: dict[str, Any] = {
        "key": settings["key"],
        "url": settings["url"],
        "token_encoding": settings["token_encoding"],
        "cache_path": DATA_DIR / job_id / "cache",
        "log_dir_path": DATA_DIR / job_id / "logs",
        "retry_times": int(os.getenv("EPUB_TRANSLATOR_RETRY_TIMES", "5")),
    }
    translation_llm = LLM(model=settings["model"], **common)
    fill_llm = LLM(model=settings["fill_model"] or settings["model"], **common)
    return translation_llm, fill_llm


def _update_job(job_id: str, **changes: Any) -> None:
    with jobs_lock:
        job = jobs.get(job_id)
        if job:
            for key, value in changes.items():
                setattr(job, key, value)


def _run_translation(job_id: str, source_path: Path, target_path: Path, target_language: str, mode: str, prompt: str) -> None:
    try:
        _update_job(job_id, status="running", message="Preparing your book")
        translation_llm, fill_llm = _build_llms(job_id)

        def on_progress(progress: float) -> None:
            _update_job(job_id, progress=round(progress * 100, 1), message="Translating chapters")

        def on_fill_failed(event: Any) -> None:
            if event.over_maximum_retries:
                _update_job(job_id, message="Continuing after a recoverable formatting issue")

        submit = SubmitKind.REPLACE if mode == "replace" else SubmitKind.APPEND_BLOCK
        translate(
            source_path=source_path,
            target_path=target_path,
            target_language=target_language,
            submit=submit,
            user_prompt=prompt.strip() or None,
            concurrency=int(os.getenv("EPUB_TRANSLATOR_CONCURRENCY", "2")),
            translation_llm=translation_llm,
            fill_llm=fill_llm,
            on_progress=on_progress,
            on_fill_failed=on_fill_failed,
        )
        _update_job(job_id, status="complete", progress=100, message="Your translated EPUB is ready", output_path=str(target_path))
    except Exception as error:
        _update_job(job_id, status="error", message=str(error)[:500])


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/terms", response_class=HTMLResponse)
async def terms() -> str:
    return (STATIC_DIR / "terms.html").read_text(encoding="utf-8")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "books-translator"}


@app.post("/api/jobs")
async def create_job(
    file: UploadFile = File(...),
    target_language: str = Form(...),
    mode: str = Form("bilingual"),
    prompt: str = Form(""),
    terms_accepted: bool = Form(False),
) -> dict[str, Any]:
    if not terms_accepted:
        raise HTTPException(status_code=400, detail="You must accept the Terms of Service before uploading a book.")
    if not file.filename or not file.filename.lower().endswith(".epub"):
        raise HTTPException(status_code=400, detail="Please upload an EPUB file.")
    if mode not in {"bilingual", "replace"}:
        raise HTTPException(status_code=400, detail="Unsupported translation mode.")
    if not target_language.strip() or len(target_language) > 80:
        raise HTTPException(status_code=400, detail="Choose a target language.")

    job_id = uuid.uuid4().hex
    job_dir = DATA_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    source_path = job_dir / "source.epub"
    target_path = job_dir / "translated.epub"
    written = 0
    with source_path.open("wb") as destination:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                source_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="This EPUB is larger than the configured upload limit.")
            destination.write(chunk)

    job = Job(id=job_id, filename=file.filename, target_language=target_language.strip(), mode=mode)
    with jobs_lock:
        jobs[job_id] = job
    threading.Thread(
        target=_run_translation,
        args=(job_id, source_path, target_path, job.target_language, mode, prompt),
        daemon=True,
        name=f"translation-{job_id[:8]}",
    ).start()
    return {"job": asdict(job)}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Translation job not found.")
        return {"job": asdict(job)}


@app.get("/api/jobs/{job_id}/download")
async def download_job(job_id: str) -> FileResponse:
    with jobs_lock:
        job = jobs.get(job_id)
        if not job or job.status != "complete" or not job.output_path:
            raise HTTPException(status_code=404, detail="The translated EPUB is not ready.")
    return FileResponse(job.output_path, media_type="application/epub+zip", filename=f"{Path(job.filename).stem}-translated.epub")
