# Speak with Ikigai

A local public-speaking coach built with FastAPI and CrisperWhisper. It analyzes uploaded or recorded speech, detects filler words, repeated phrases, long pauses, and speaking rate, then returns a simple fluency score and coaching feedback.

## Features

- Upload audio files or record directly in the browser
- Local speech transcription with CrisperWhisper
- Fluency analysis for filler words, repetitions, long pauses, and speaking pace
- SQLite report history and cached audio analysis results
- Static frontend served locally from the app package

## Tech stack

- Python 3.10+
- FastAPI
- Uvicorn
- CrisperWhisper
- SQLite
- HTML/CSS/JavaScript frontend

## Project structure

```text
crisper_test/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application and analysis logic
│   └── static/
│       ├── analyze.html
│       ├── index.html
│       ├── script.js
│       └── style.css
├── data/
│   └── audio/
│       └── audio.mp3         # sample audio file
├── tests/
│   ├── test_app.py
│   ├── test_crisper.py
│   └── test_speed2.py
├── .venv/                    # local virtual environment
├── crisper_env/              # optional local environment
├── main.py                   # compatibility wrapper for imports / old startup
├── README.md
├── reports.db                # SQLite report database
├── requirements.txt
├── patch_cache.py            # helper script
└── ...
```

## Setup

From the project root, create and activate a virtual environment, then install the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If you are already using a local environment such as `crisper_env`, activate that instead.

## Run the app

Start the backend from the project root:

```powershell
python -m uvicorn app.main:app --reload
```

The project also includes a compatibility wrapper, so older startup patterns still work:

```powershell
python -m uvicorn main:app --reload
```

Open this in the browser:

```text
http://127.0.0.1:8000
```

The first run may take longer while the model downloads and loads. After that, analyses are much faster.

## Supported audio formats

The app accepts these file types:

- WAV
- MP3
- M4A
- OGG
- FLAC
- WebM
- MP4

Maximum upload size: 25 MB.

## API endpoints

- `GET /` — landing page
- `GET /api/health` — health check
- `POST /api/analyze` — upload audio and receive a detailed report
- `POST /analyze` — frontend-friendly response format
- `GET /api/reports` — recent saved report summaries
- `GET /api/reports/{report_id}` — single report lookup

## Report storage

Saved analysis results are stored in the root-level SQLite database:

```text
reports.db
```

The app also caches audio hash lookups to avoid reprocessing identical uploads.

## Notes

- Transcription runs locally with CrisperWhisper; no external speech API is used.
- Browser microphone recording works on localhost or HTTPS.
- Clear audio with audible speech gives the most reliable results.

## Troubleshooting

If the app does not start:

1. Confirm you are using Python 3.10+
2. Ensure the dependencies in `requirements.txt` are installed
3. Make sure the working directory is the project root before starting uvicorn
4. Check the terminal output for model download or import issues

## License

This project is for local development and demo use unless otherwise specified by the owner.
