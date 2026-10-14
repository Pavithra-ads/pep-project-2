from pathlib import Path
p = Path("main.py")
s = p.read_text(encoding="utf-8")
reps = [
    ("import json\n", "import hashlib\nimport json\n"),
    ('            """\n        )\n\n\n@app.on_event("startup")',
     '            """\n        )\n        connection.execute(\n            "CREATE TABLE IF NOT EXISTS audio_cache (hash TEXT PRIMARY KEY, report_id TEXT NOT NULL)"\n        )\n\n\n@app.on_event("startup")'),
    ("            size = 0\n", "            size = 0\n            hasher = hashlib.sha256()\n"),
    ("                temporary_file.write(chunk)\n", "                hasher.update(chunk)\n                temporary_file.write(chunk)\n"),
    ("        model_started = perf_counter()\n",
     '        digest = hasher.hexdigest()\n        with connect_database() as connection:\n            cached = connection.execute(\n                "SELECT r.report_json FROM audio_cache a JOIN reports r ON r.id = a.report_id WHERE a.hash = ?",\n                (digest,),\n            ).fetchone()\n        if cached is not None:\n            return json.loads(cached["report_json"])\n\n        model_started = perf_counter()\n'),
    ("        save_report(report)\n        database_seconds = perf_counter() - database_started\n",
     '        save_report(report)\n        with connect_database() as connection:\n            connection.execute(\n                "INSERT OR REPLACE INTO audio_cache (hash, report_id) VALUES (?, ?)",\n                (digest, report["id"]),\n            )\n        database_seconds = perf_counter() - database_started\n'),
]
for a, b in reps:
    assert s.count(a) == 1, "not found or duplicated: " + a
    s = s.replace(a, b)
p.write_text(s, encoding="utf-8")
print("patched")
