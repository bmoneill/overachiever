# Commands for the AI Agent

- Always enter planning mode before implementing a task, wait for approval before
  writing code
- After completing each task, summarize what you changed and update the tasks section
- Work on one task at a time and stop and ask me to review and commit the work

## Tasks

- [x] Write a simple Flask program which pulls a user's XBox achievements from the
      OpenXBL API and displays them.
- [x] Displaying achievements currently does not work. To make this easier,
      entering the XUID should display a list of games which the player owns,
      the number of achievements the player has obtained, and the total number
      of achievements. Clicking on the game should display a list of achievements
      which the player does have, including the name and description, and a list
      of achievements which the player does not have, also including the name and
      description.

## Completed

### Task 1: Flask Xbox Achievements App

Created a Flask web app that fetches Xbox achievements from the OpenXBL API:

- **`app.py`** — Flask app with `/` (XUID input form) and `/achievements/<xuid>` (calls OpenXBL, renders results) routes
- **`templates/index.html`** — Landing page with dark-themed XUID input form and flash message support
- **`templates/achievements.html`** — Renders per-game achievement lists with images, descriptions, gamerscore, and unlock status
- **`requirements.txt`** — `flask`, `requests`, `python-dotenv`
- **`.env.example`** — Documents the required `OPENXBL_API_KEY` env var
- **`.gitignore`** — Standard Python/Flask ignores

### Task 2: Game List + Per-Game Achievement Detail

Replaced the broken single-page achievements view with a two-step flow:

- **`app.py`** — Updated base URL to `https://api.xbl.io` (canonical per OpenAPI spec); extracted shared `xbl_get()` helper that unwraps the `{content, code}` response envelope; replaced old `/achievements/<xuid>` route with `/games/<xuid>` (game list) and `/games/<xuid>/<title_id>` (per-game achievements); index form now redirects to `/games/<xuid>`
- **`templates/games.html`** — NEW: Grid of clickable game cards showing title image, name, "X / Y achievements", and a green progress bar. Each card links to the per-game detail page
- **`templates/game_achievements.html`** — NEW: Shows achievements split into "Unlocked" (green border, unlock date) and "Locked" (grey, dimmed) sections, each with name, description, icon, and gamerscore
- **`templates/achievements.html`** — DELETED: replaced by the two new templates
