# Commands for the AI Agent

- Always enter planning mode before implementing a task, wait for approval before
  writing code
- After completing each task, summarize what you changed and update the tasks section
- Work on one task at a time and stop and ask me to review and commit the work

## Tasks

- [x] Write a simple Flask program which pulls a user's XBox achievements from the
      OpenXBL API and displays them.

## Completed

### Task 1: Flask Xbox Achievements App

Created a Flask web app that fetches Xbox achievements from the OpenXBL API:

- **`app.py`** — Flask app with `/` (XUID input form) and `/achievements/<xuid>` (calls OpenXBL, renders results) routes
- **`templates/index.html`** — Landing page with dark-themed XUID input form and flash message support
- **`templates/achievements.html`** — Renders per-game achievement lists with images, descriptions, gamerscore, and unlock status
- **`requirements.txt`** — `flask`, `requests`, `python-dotenv`
- **`.env.example`** — Documents the required `OPENXBL_API_KEY` env var
- **`.gitignore`** — Standard Python/Flask ignores
