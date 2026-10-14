from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import threading
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter
from typing import Any, Generator

from crisperwhisper import CrisperWhisperModel
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = PROJECT_ROOT
STATIC_DIR = PROJECT_ROOT / "app" / "static"
DATABASE_PATH = PROJECT_ROOT / "reports.db"
MAX_AUDIO_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm", ".mp4"}
LONG_PAUSE_SECONDS = 1.0
FILLER_TAGS = {"um", "uh", "er", "erm", "hmm", "mm", "ah"}
FILLER_PHRASES = {("you", "know"), ("i", "mean"), ("kind", "of"), ("sort", "of")}
LOGGER = logging.getLogger("crisper")
_model: CrisperWhisperModel | None = None
_model_lock = threading.Lock()

app = FastAPI(title="Crisper Speech Coach", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@contextmanager
def connect_database() -> Generator[sqlite3.Connection, None, None]:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database() -> None:
    with connect_database() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                report_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS audio_cache (hash TEXT PRIMARY KEY, report_id TEXT NOT NULL)"
        )


@app.on_event("startup")
def on_startup() -> None:
    initialize_database()


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def get_model() -> CrisperWhisperModel:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = CrisperWhisperModel("small", backend="transformers")
    return _model


def clean_word(word: str) -> str:
    return re.sub(r"[^a-z0-9']", "", word.lower())


def format_clock(seconds: float) -> str:
    minutes, remainder = divmod(max(0, int(seconds)), 60)
    return f"{minutes:02d}:{remainder:02d}"


def analyze_transcription(result: Any) -> dict[str, Any]:
    words = result.words or []
    spoken_words = [
        (clean_word(word.word.strip()), word.start, word.end)
        for word in words
        if not (word.word.startswith("[") and word.word.endswith("]"))
        and clean_word(word.word)
        and word.start is not None
        and word.end is not None
    ]
    if not spoken_words:
        raise HTTPException(
            status_code=422,
            detail="No clear speech was detected. Try a recording with audible speech.",
        )

    fillers = Counter(
        clean_word(word.word)
        for word in words
        if word.word.startswith("[")
        and word.word.endswith("]")
        and clean_word(word.word) in FILLER_TAGS
    )
    for index in range(len(spoken_words) - 1):
        phrase = (spoken_words[index][0], spoken_words[index + 1][0])
        if phrase in FILLER_PHRASES:
            fillers[" ".join(phrase)] += 1

    repeated_words = Counter(
        f"{spoken_words[index][0]} {spoken_words[index][0]}"
        for index in range(len(spoken_words) - 1)
        if spoken_words[index][0] == spoken_words[index + 1][0]
    )
    repeated_phrases = Counter(
        f"{spoken_words[index][0]} {spoken_words[index + 1][0]}"
        for index in range(len(spoken_words) - 3)
        if (spoken_words[index][0], spoken_words[index + 1][0])
        == (spoken_words[index + 2][0], spoken_words[index + 3][0])
    )
    long_pauses = [
        {
            "start": float(words[index].end),
            "end": float(words[index + 1].start),
            "duration_seconds": round(
                float(words[index + 1].start) - float(words[index].end), 1
            ),
        }
        for index in range(len(words) - 1)
        if words[index].end is not None
        and words[index + 1].start is not None
        and words[index + 1].start - words[index].end >= LONG_PAUSE_SECONDS
    ]

    duration = max(float(result.duration), 0.0)
    minutes = duration / 60
    word_count = len(spoken_words)
    wpm = round(word_count / minutes) if minutes > 0 else 0
    filler_count = sum(fillers.values())
    repeated_word_count = sum(repeated_words.values())
    repeated_phrase_count = sum(repeated_phrases.values())
    issue_rate = (filler_count + repeated_word_count + repeated_phrase_count) / max(
        minutes, 1 / 60
    )
    score = max(
        0,
        min(
            100,
            round(
                100
                - issue_rate * 4
                - max(0, len(long_pauses) - 2) * 2
                - (8 if wpm and (wpm < 110 or wpm > 160) else 0)
            ),
        ),
    )

    if issue_rate < 2:
        feedback = ["Your speech demonstrates excellent fluency."]
    elif issue_rate < 5:
        feedback = ["Your speech demonstrates good overall fluency."]
    else:
        feedback = ["Your speech will benefit from a little more fluency practice."]
    if filler_count >= 3:
        feedback.append("Try replacing frequent filler words with a short, calm pause.")
    if repeated_word_count + repeated_phrase_count >= 3:
        feedback.append("A brief pause to organize your thoughts can reduce repetitions.")
    if len(long_pauses) >= 5:
        feedback.append("Practice transitions between points to make long pauses smoother.")
    if wpm < 110:
        feedback.append("Your pace is on the slower side; try a slightly quicker delivery.")
    elif wpm > 160:
        feedback.append("Your pace is quick; slow down a little to help listeners follow.")
    else:
        feedback.append("Your speaking pace is in a comfortable range.")

    return {
        "transcript": result.text.strip(),
        "duration_seconds": round(duration, 1),
        "duration_display": format_clock(duration),
        "total_words": word_count,
        "words_per_minute": wpm,
        "fluency_score": score,
        "filler_count": filler_count,
        "repeated_word_count": repeated_word_count,
        "repeated_phrase_count": repeated_phrase_count,
        "long_pause_count": len(long_pauses),
        "fillers": [
            {"text": phrase, "count": count}
            for phrase, count in fillers.most_common(8)
        ],
        "repetitions": [
            {"text": phrase, "count": count}
            for phrase, count in (repeated_words + repeated_phrases).most_common(8)
        ],
        "long_pauses": [
            {
                **pause,
                "start_display": f"{int(pause['start'] // 60):02d}:{pause['start'] % 60:04.1f}",
                "end_display": f"{int(pause['end'] // 60):02d}:{pause['end'] % 60:04.1f}",
            }
            for pause in long_pauses[:10]
        ],
        "feedback": feedback,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def save_report(report: dict[str, Any]) -> None:
    with connect_database() as connection:
        connection.execute(
            "INSERT INTO reports (id, created_at, report_json) VALUES (?, ?, ?)",
            (report["id"], report["created_at"], json.dumps(report)),
        )


@app.post("/api/analyze")
def analyze_audio(file: UploadFile = File(...)) -> dict[str, Any]:
    request_started = perf_counter()
    model_seconds = 0.0
    transcription_seconds = 0.0
    analysis_seconds = 0.0
    database_seconds = 0.0

    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported audio format. Use WAV, MP3, M4A, OGG, FLAC, or WebM.",
        )

    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            prefix="crisper-", suffix=extension, delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            size = 0
            hasher = hashlib.sha256()
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_AUDIO_BYTES:
                    raise HTTPException(
                        status_code=413, detail="Audio files must be 25 MB or smaller."
                    )
                hasher.update(chunk)
                temporary_file.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="The uploaded audio file is empty.")

        digest = hasher.hexdigest()
        with connect_database() as connection:
            cached = connection.execute(
                "SELECT r.report_json FROM audio_cache a JOIN reports r ON r.id = a.report_id WHERE a.hash = ?",
                (digest,),
            ).fetchone()
        if cached is not None:
            return json.loads(cached["report_json"])

        model_started = perf_counter()
        model = get_model()
        model_seconds = perf_counter() - model_started

        transcription_started = perf_counter()
        result = model.transcribe(str(temporary_path), language="en", word_timestamps=True)
        transcription_seconds = perf_counter() - transcription_started

        analysis_started = perf_counter()
        report = analyze_transcription(result)
        analysis_seconds = perf_counter() - analysis_started

        report["id"] = uuid.uuid4().hex
        database_started = perf_counter()
        save_report(report)
        with connect_database() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO audio_cache (hash, report_id) VALUES (?, ?)",
                (digest, report["id"]),
            )
        database_seconds = perf_counter() - database_started
        return report
    except HTTPException:
        raise
    except Exception as exc:
        LOGGER.exception("Audio analysis failed")
        raise HTTPException(
            status_code=500,
            detail="Audio analysis failed. Check that the file is playable and review the backend logs.",
        ) from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        file.file.close()
        LOGGER.info(
            "Analysis timing (seconds): total=%.3f model_load=%.3f "
            "transcription=%.3f report_analysis=%.3f sqlite_save=%.3f",
            perf_counter() - request_started,
            model_seconds,
            transcription_seconds,
            analysis_seconds,
            database_seconds,
        )


@app.post("/analyze")
def analyze_audio_for_frontend(file: UploadFile = File(...)) -> dict[str, Any]:
    report = analyze_audio(file)
    return {
        "duration_seconds": report["duration_seconds"],
        "duration_text": report["duration_display"],
        "total_words": report["total_words"],
        "wpm": report["words_per_minute"],
        "filler_count": report["filler_count"],
        "fillers": {
            item["text"]: item["count"] for item in report["fillers"]
        },
        "repeated_word_count": report["repeated_word_count"],
        "repeated_phrase_count": report["repeated_phrase_count"],
        "repetitions": {
            item["text"]: item["count"] for item in report["repetitions"]
        },
        "long_pauses": report["long_pauses"],
        "feedback": " ".join(report["feedback"]),
        "transcript": report["transcript"],
    }


@app.get("/api/reports")
def list_reports() -> list[dict[str, Any]]:
    with connect_database() as connection:
        rows = connection.execute(
            "SELECT report_json FROM reports ORDER BY created_at DESC LIMIT 12"
        ).fetchall()
    reports = [json.loads(row["report_json"]) for row in rows]
    return [
        {
            key: report[key]
            for key in (
                "id",
                "created_at",
                "duration_display",
                "fluency_score",
                "words_per_minute",
                "total_words",
            )
        }
        for report in reports
    ]


@app.get("/api/reports/{report_id}")
def get_report(report_id: str) -> dict[str, Any]:
    with connect_database() as connection:
        row = connection.execute(
            "SELECT report_json FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return json.loads(row["report_json"])
