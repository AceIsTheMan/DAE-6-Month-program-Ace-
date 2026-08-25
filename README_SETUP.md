# The Far Lands — backend setup

Django backend for The Far Lands, with the site's real landing page
(`TFL_index.html`, now `home.html`) served through Django too, so login
state is real instead of guessed. Run everything from a terminal, from this
folder (`DAE_6_Month_program_ACE`).

**Important:** always `cd` into this exact folder before running
`manage.py` commands. There's an old, unused copy of the frontend under
`python_1/The Far Lands_Vol2/View point/` — don't run a server from there,
and don't point tools like VS Code's "Live Server" extension at anything in
that folder. It doesn't talk to the database or know about logins at all;
it's kept only as a reference copy.

## First-time setup

```
pip3 install -r requirements.txt
python3 manage.py migrate
python3 manage.py runserver
```

**If you already had this project set up before today**, just run
`python3 manage.py migrate` again — recent passes added new fields to user
profiles and each one needs a migration to reach your database.

Then open **http://127.0.0.1:8000/** — that's the real Far Lands site now
(rules gate, banners, video cards, the works), with LOGIN / REGISTER in the
nav when you're logged out.

- `/` — the main site (public)
- `/register/` — create a full account (username, email, password)
- `/guest/` — create a temporary "Hacker" guest account (username + password
  only, no email)
- `/login/` — log in (same form for both account types)
- `/profile/` — your profile: photo, rank, alias, bio, all in one page, with
  an inline "// EDIT PROFILE" section (profile picture, alias, bio,
  `[ SAVE ]` button) right on the page
- `/profile/<username>/` — view someone else's profile (read-only)
- `/admin/` — Django admin (run `python3 manage.py createsuperuser` first)

## What's new in this pass: guest ("Hacker") accounts

- The login page now has a **"Continue as a Guest"** link, leading to
  `/guest/` — a shorter signup that only asks for a codename and a
  password, no email.
- Guest accounts show up on their profile as **HACKER** instead of AGENT,
  and their profile shows a **"Trial: N days left"** field.
- Guest accounts **can't set a profile picture** — that part of the edit
  form is hidden for them, and blocked on the server side too, not just
  in the page.
- Guest accounts **expire after 7 days.** Once a guest's trial is up, the
  account (and everything on it) gets deleted automatically the next time
  anyone loads any page on the site — there's nothing to run manually for
  this to happen.

## From earlier passes

- **"PROFILE" and "MY PROFILE" are one button and one page.** `/profile/`
  shows your username, rank, alias, the year you joined, and your bio, with
  the editable fields tucked under a collapsible "// EDIT PROFILE" section
  and a `[ SAVE ]` button.
- **The real site is the Django home page.** `TFL_index.html`,
  `TFL_styles.css`, `TFL.js`, and all the videos/images live in
  `accounts/static/accounts/` and `accounts/templates/home.html`, served at
  `/`. This was necessary for the nav to actually know whether you're
  logged in — a standalone local file and a separate Django server can't
  reliably share login state, but a page served by Django itself can just
  check `{% if user.is_authenticated %}`.
- **Nav reacts to login state.** Logged out: LOGIN / REGISTER. Logged in:
  PROFILE / LOGOUT — the HOME / UPDATES / SOCIALS tabs are always there
  either way so you can keep exploring.
- **Login and registration both land you back on the home page**, not a
  bare profile-editing screen.
- **Show/hide password toggle** (`[ SHOW ]` / `[ HIDE ]`) on every password
  field.
- **Logout asks "Are you sure you WANT to logout?"** before it actually
  logs you out.

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
