from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

import main


class SpeechAnalysisApiTests(unittest.TestCase):
    def test_counts_repeated_phrases(self) -> None:
        words = [
            SimpleNamespace(word=word, start=index * 0.4, end=index * 0.4 + 0.3)
            for index, word in enumerate(("we", "go", "we", "go", "forward"))
        ]
        result = SimpleNamespace(text="We go, we go forward.", duration=3.0, words=words)

        report = main.analyze_transcription(result)

        self.assertEqual(report["repeated_phrase_count"], 1)
        self.assertEqual(report["repetitions"], [{"text": "we go", "count": 1}])

    def test_analyze_saves_report_and_lists_history(self) -> None:
        words = [
            SimpleNamespace(word="Hello", start=0.0, end=0.5),
            SimpleNamespace(word="[um]", start=0.6, end=0.9),
            SimpleNamespace(word="there.", start=2.0, end=2.5),
        ]
        model = Mock()
        model.transcribe.return_value = SimpleNamespace(
            text="Hello um there.",
            duration=4.0,
            words=words,
        )
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "reports.db"
            with patch.object(main, "DATABASE_PATH", database_path), patch.object(
                main, "get_model", return_value=model
            ), TestClient(main.app) as client:
                response = client.post(
                    "/api/analyze",
                    files={"file": ("practice.wav", b"sample audio", "audio/wav")},
                )

                self.assertEqual(response.status_code, 200)
                report = response.json()
                self.assertEqual(report["total_words"], 2)
                self.assertEqual(report["filler_count"], 1)
                self.assertEqual(report["long_pause_count"], 1)
                self.assertEqual(report["duration_display"], "00:04")
                model.transcribe.assert_called_once()

                history = client.get("/api/reports")
                self.assertEqual(history.status_code, 200)
                self.assertEqual(history.json()[0]["id"], report["id"])

                saved_report = client.get(f"/api/reports/{report['id']}")
                self.assertEqual(saved_report.status_code, 200)
                self.assertEqual(saved_report.json()["transcript"], "Hello um there.")

    def test_frontend_analyze_route_returns_requested_response_shape(self) -> None:
        model = Mock()
        model.transcribe.return_value = SimpleNamespace(
            text="Hello there.",
            duration=2.0,
            words=[
                SimpleNamespace(word="Hello", start=0.0, end=0.6),
                SimpleNamespace(word="there.", start=0.7, end=1.2),
            ],
        )
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(main, "DATABASE_PATH", Path(directory) / "reports.db"), patch.object(
                main, "get_model", return_value=model
            ), TestClient(main.app) as client:
                response = client.post(
                    "/analyze",
                    files={"file": ("practice.wav", b"sample audio", "audio/wav")},
                )

        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["duration_text"], "00:02")
        self.assertEqual(report["wpm"], 60)
        self.assertEqual(report["fillers"], {})
        self.assertEqual(report["repetitions"], {})
        self.assertEqual(report["transcript"], "Hello there.")

    def test_rejects_unsupported_audio_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(main, "DATABASE_PATH", Path(directory) / "reports.db"), TestClient(
                main.app
            ) as client:
                response = client.post(
                    "/api/analyze",
                    files={"file": ("notes.txt", b"not audio", "text/plain")},
                )

        self.assertEqual(response.status_code, 415)
        self.assertIn("Unsupported audio format", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
