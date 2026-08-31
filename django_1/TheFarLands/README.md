# The Far Lands — backend

Django backend for The Far Lands: a media/community site for an upcoming
Roblox RPG project. The site's real landing page (`home.html`), login,
registration, guest accounts, and profile pages are all served through
Django, so login state is real instead of guessed by a static page.

**Always `cd` into this exact folder (`TheFarLands`) before running any
`manage.py` command.**

## Setup

```
pip3 install -r requirements.txt
python3 manage.py migrate
python3 manage.py runserver
```

Then open **http://127.0.0.1:8000/**.

If you already had this project set up before and just pulled new changes,
re-run `python3 manage.py migrate` — new passes sometimes add fields to the
user model, and each one needs a migration applied to your local database.

## Pages / routes

- `/` — the main site (public)
- `/register/` — create a full account (username, email, password) — you'll
  need to click a verification link before you can log in, see below
- `/guest/` — create a temporary "Hacker" guest account (username + password
  only, no email, no verification step, expires after 7 days)
- `/login/` — log in (same form for both account types)
- `/profile/` — your profile: photo, rank, alias, bio, with an inline
  "// EDIT PROFILE" section
- `/profile/<username>/` — view someone else's profile (read-only)
- `/admin/` — Django admin (run `python3 manage.py createsuperuser` first)

## Email verification

No real email sending is configured yet (no Gmail/SMTP), so in dev mode the
verification email is printed to the terminal running `manage.py
runserver` instead of actually being sent. Look for a line starting with
`Subject: Verify your Far Lands account` and open the link underneath it in
your browser. Guest ("Hacker") accounts skip this entirely and log in
immediately.

## Project layout

- `accounts/` — custom user model, auth (register/login/guest/verify),
  profile pages, and the real site's landing page + static assets
  (`accounts/static/accounts/`, `accounts/templates/`)
- `forum/` — forum app (placeholder landing page so far, no models yet)
- `tfl_site/` — Django project settings and URL routing
- `media/` — user-uploaded content (profile pictures)
- `db.sqlite3` — local dev database (not shared — everyone gets their own
  via `migrate`)

See [CHANGELOG.md](CHANGELOG.md) for the pass-by-pass history of what's
been built.

## Not touched

Everything else in `DAE_6_Month_program_ACE` (the folder one level up) —
course exercise folders (`design_1`, `django_1`, `figma_1`,
`javascript_1`, `logic_1`, `prompt_engineering_1`, `semester_2`, `unix_1`,
`unix_2`, `version_control_1`), `old_project/`, and the separate Jekyll
portfolio under `docs/` — is unrelated to this project and untouched.

There's also an old, unused copy of the frontend under
`../python_1/The Far Lands_Vol2/View point/` (one level up). It doesn't
talk to the database or know about logins at all; don't run a server from
there, and don't point tools like VS Code's "Live Server" extension at
anything in that folder. It's kept only as a reference copy.
