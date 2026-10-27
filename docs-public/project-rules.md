# Project rules: cvwrite3
<!-- scaffolder-Opus5.5-agent, 2026-10-26 (kit retrofit). The owner changes this file. -->

## Back end
Stack file: `docs/rules/stacks/python.md`. FastAPI (ASGI) on the server's own Python, PostgreSQL with its own non-superuser role, and a separate worker process for the AI calls and the PDF render. PDFs are stored on disk under the app's directory.

## Screens
Something else: server-rendered HTML from Jinja templates and plain HTML forms. One small stylesheet (`app/static/calm.css`) and self-hosted fonts. No JavaScript framework and no build step; one small script (`app/static/upload.js`). English first; the privacy notice and consent screen also in Bahasa Malaysia.

## Tests
`python -m unittest discover tests` (the standard library's runner, not pytest), on real PostgreSQL. The render tests need Chrome and poppler. CI installs both and runs them with `CVWRITE_REQUIRE_RENDER=1`, so a missing or broken tool fails the run instead of skipping; they also run at the deploy runbook's render check.

## PDF render
Headless Chrome (Chromium on the server, its path from an environment variable), with self-hosted fonts. A render's page count, fonts and text hash are checked against a known fingerprint after each deploy.

## AI calls
Plain Messages API calls with no tools. The ad is passed as delimited data, never as instructions. Contact details are taken out before any call and merged back only after it.
