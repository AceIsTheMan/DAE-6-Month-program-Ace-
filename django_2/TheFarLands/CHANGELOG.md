# Changelog

Pass-by-pass history of changes to The Far Lands backend, most recent
first. See [README.md](README.md) for current setup and usage.

## Forum tab

- New `forum` app added with a placeholder landing page for what will
  become a community forum. No models yet — this app is a stub future
  passes will build on.

## Email verification + the rules gate after login

- **Registering (not guest) now requires email verification before you can
  log in.** After `/register/`, you land on a "check your email" page
  instead of being logged straight in. A real-looking email gets sent with
  a one-time verification link.
- **No real email sending is set up yet** (no Gmail/SMTP configured), so in
  dev mode that email is printed to the terminal where `manage.py
  runserver` is running instead of actually being emailed — the
  "check your email" page tells you this too. Look in that terminal for a
  line starting with `Subject: Verify your Far Lands account` and copy the
  link underneath it into your browser.
- Clicking the link marks the account verified and shows a confirmation
  page; from there, log in normally at `/login/`.
- Trying to log in before clicking the link shows a clear
  "you need to verify your email first" message instead of a confusing
  wrong-password error.
- **Guest ("Hacker") accounts are unaffected** — they still skip all of
  this and log in immediately, per the original request.
- **The "BE ADVISED" rules popup now shows again right after you log in**,
  even in a browser tab that already dismissed it earlier as an anonymous
  visitor. It still won't nag you on every ordinary refresh/re-visit
  outside of a fresh login — just that one page load right after signing
  in (regular or guest).

## Guest ("Hacker") accounts

- The login page has a **"Continue as a Guest"** link, leading to
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

## Earlier passes

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

## Pass 1 — initial fixes

What was wrong originally:

- `manage.py` had been moved away from `tfl_site/` (the settings module it
  needs to import) — fixed, back at the project root.
- No real Django app, no `AUTH_USER_MODEL`, and no registration/login/logout
  code at all — all fixed; see `accounts/`.
- `profile.html` extended a `base.html` that didn't exist — fixed.
- Invalid `MAILERS` setting (should've been `EMAIL_BACKEND`) — fixed.

Superseded originals live in `../_pre_fix_backup/` (one level up) rather
than being deleted: the old loose `urls.py`/`views.py`, the standalone
`TFL_index_original.html` and `TFL_original.js`, and the now-unused
`profile_edit_deprecated.html`.

## Open items

A few small things flagged in earlier chats about the website itself are
still open: Card 1/Card 2's duplicate lightbox-button bug in the video
grid, the banner `<img>` placement, and the Twitter/X social link still
pointing at `#`.
