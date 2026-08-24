# The Far Lands — backend setup

This is the real Django backend for user registration/login/profile, wired up
and tested. Everything below is run from a terminal, from this folder
(`DAE_6_Month_program_ACE`).

## First-time setup

```
pip3 install -r requirements.txt
python3 manage.py migrate
python3 manage.py runserver
```

Then open **http://127.0.0.1:8000/register/** to create an account.

- `/register/` — create an account (username, email, password, agree-to-rules)
- `/login/` — log in
- `/profile/` — your own profile (bio, rank, profile picture)
- `/profile/edit/` — edit your bio / picture
- `/profile/<username>/` — view someone else's profile
- `/` — redirects to your profile if logged in, otherwise to login
- `/admin/` — Django admin (run `python3 manage.py createsuperuser` first)

## What changed / what was wrong

The project previously couldn't run at all:

- `manage.py` had been moved into `python_1/The Far Lands_Vol2/View point/`,
  three folders away from `tfl_site/` (the settings module it needs to
  import) — it now lives here at the project root, next to `tfl_site/`,
  where it was originally created.
- There was no real Django **app** — `models.py`, `views.py`, `urls.py`, and
  `templates/profile.html` were loose files with no `__init__.py`,
  `apps.py`, or migrations, and were never added to `INSTALLED_APPS`. They're
  now a proper app at `accounts/`.
- `AUTH_USER_MODEL` was never set, so Django would have silently used its own
  default `User` model instead of your `CustomUser` (bio/rank/profile
  picture) — now set correctly in `tfl_site/settings.py`.
- There was **no registration, login, or logout code at all** — only a
  profile page that required already being logged in, with no way to ever
  get logged in. `accounts/forms.py` and `accounts/views.py` now have a real
  registration form (with duplicate-username/email checks and password
  validation), plus login/logout wired to Django's built-in auth views.
- `profile.html` extended a `base.html` that didn't exist anywhere, so it
  would have failed with `TemplateDoesNotExist`. `accounts/templates/base.html`
  now exists, styled to match the site's red/black terminal theme (same CSS
  variables and fonts as `TFL_index.html`).
- The `MAILERS` setting in `settings.py` wasn't a real Django setting
  (should have been `EMAIL_BACKEND`) — fixed, using the console backend for
  local dev.

Your original loose `urls.py` and `views.py` (the ones that only had the
profile page, nothing else) were moved to `_pre_fix_backup/` rather than
deleted, in case you want to compare. `models.py` and `templates/profile.html`
were moved as-is into `accounts/` since their content didn't need to change.

## Not touched

`python_1/The Far Lands_Vol2/View point/` (the static `TFL_index.html`
landing page, its CSS/JS, and all videos/images) is untouched — it's a
separate static front-end, not wired into this Django backend. A few things
your earlier chat flagged as still open there and not addressed in this pass:
Card 1/Card 2's duplicate lightbox-button bug, the banner `<img>` placement,
`TFL_styles.css` being unlinked (and safe to leave that way — its rules
don't match anything real in the page and would fight the inline theme if
linked), and the alias-field/stats-grid edits. Ask any time and I'll take
those on too.
