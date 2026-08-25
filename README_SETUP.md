# The Far Lands — backend setup

Django backend for The Far Lands, with the site's real landing page
(`TFL_index.html`, now `home.html`) served through Django too, so login
state is real instead of guessed. Run everything from a terminal, from this
folder (`DAE_6_Month_program_ACE`).

## First-time setup

```
pip3 install -r requirements.txt
python3 manage.py migrate
python3 manage.py runserver
```

**If you already had this project set up before today**, just run
`python3 manage.py migrate` again — this pass added a new `alias` field to
user profiles and it needs one more migration to reach your database.

Then open **http://127.0.0.1:8000/** — that's the real Far Lands site now
(rules gate, banners, video cards, the works), with LOGIN / REGISTER in the
nav when you're logged out.

- `/` — the main site (public)
- `/register/` — create an account
- `/login/` — log in
- `/profile/` — your profile: photo, rank, alias, bio, all in one page, with
  an inline "// EDIT PROFILE" section (profile picture, alias, bio,
  `[ SAVE ]` button) right on the page
- `/profile/<username>/` — view someone else's profile (read-only)
- `/admin/` — Django admin (run `python3 manage.py createsuperuser` first)

## What's new in this pass

- **"PROFILE" and "MY PROFILE" are now one button and one page.** There used
  to be two: a "PROFILE" tab on the home page (just a JS mockup — nothing
  you typed there was ever saved) and a separate "MY PROFILE" page that was
  the real thing. Now there's a single "PROFILE" link in the nav, pointing
  at the real page, which shows your username, rank, alias, the year you
  joined, and your bio, with the editable fields (profile picture, alias,
  bio) tucked under a collapsible "// EDIT PROFILE" section and a `[ SAVE ]`
  button. Alias is now a real, saved field (it wasn't before).
- The old mockup's STATUS toggle and Subscribers/Videos/Views stats were
  dropped rather than carried over — they were placeholder numbers with
  nothing behind them, and STATUS would have clashed with Django's real
  active/inactive account state.

## From the previous pass

- **The real site is the Django home page.** `TFL_index.html`,
  `TFL_styles.css`, `TFL.js`, and all the videos/images live in
  `accounts/static/accounts/` and `accounts/templates/home.html`, served at
  `/`. This was necessary for the nav to actually know whether you're
  logged in — a standalone local file and a separate Django server can't
  reliably share login state, but a page served by Django itself can just
  check `{% if user.is_authenticated %}`. The original file is kept at
  `_pre_fix_backup/TFL_index_original.html` for reference.
- **Nav reacts to login state.** Logged out: LOGIN / REGISTER. Logged in:
  PROFILE / LOGOUT — the HOME / UPDATES / SOCIALS tabs are always there
  either way so you can keep exploring.
- **Login and registration both land you back on the home page**, not a
  bare profile-editing screen — you can go to your profile whenever you
  want from the nav.
- **Show/hide password toggle** (`[ SHOW ]` / `[ HIDE ]`) on every password
  field, on both the login and register forms.
- **Logout asks "Are you sure you WANT to logout?"** before it actually
  logs you out, everywhere there's a logout button.

## What was wrong originally (pass 1)

- `manage.py` had been moved away from `tfl_site/` (the settings module it
  needs to import) — fixed, back at the project root.
- No real Django app, no `AUTH_USER_MODEL`, and no registration/login/logout
  code at all — all fixed; see `accounts/`.
- `profile.html` extended a `base.html` that didn't exist — fixed.
- Invalid `MAILERS` setting (should've been `EMAIL_BACKEND`) — fixed.

Superseded originals live in `_pre_fix_backup/` rather than being deleted:
the old loose `urls.py`/`views.py`, the standalone `TFL_index_original.html`
and `TFL_original.js`, and the now-unused `profile_edit_deprecated.html`.

## Not touched

The separate Jekyll portfolio project under `docs/` is unrelated to this and
untouched. A few small things flagged in earlier chats and still open:
Card 1/Card 2's duplicate lightbox-button bug in the video grid, the banner
`<img>` placement, and the Twitter/X social link still pointing at `#`.
Ask any time and I'll take those on.
