# klein-cvwrite3

One ad in, one CV out. A whitelisted web app at cvwrite3.puascari.com to test demand for the cvwrite skill.

Scope, chunks and rules: [brief.md](brief.md).

## Develop (Mac)
```
uv venv -p 3.10 .venv && uv pip install -p .venv/bin/python -r requirements-dev.txt
.venv/bin/python -m unittest discover tests
.venv/bin/python scripts/dev.py    # http://localhost:8766/dev/login
```
Python 3.10 matches sk24. Tests and `scripts/dev.py` start a throwaway local Postgres; nothing is installed system-wide. Settings: [env.example](env.example).
