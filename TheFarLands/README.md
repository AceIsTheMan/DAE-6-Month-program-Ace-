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

Optional: the Mail app's Social composer can search real GIFs via Tenor.
Without a key it just shows "no GIFs found" and everything else still
works fine. Get a free key at https://tenor.com/gifapi, then:

```
export TENOR_API_KEY=your-key-here
python3 manage.py runserver
```

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
- `/mail/` — internal site mail: Inbox/Sent/Updates/Social/Reports, reached
  via the envelope icon in the nav (hidden for guest accounts) - this is
  in-site messaging stored in the database, not real email
- `/settings/` — placeholder settings page (gear icon), nothing configurable yet
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
- `forum/` — forum app: Director broadcast posts, reactions, comments
- `mail/` — internal mail app: DMs, group chats, Director Updates/Directives,
  moderation Reports (Director/Admin only)
- `tfl_site/` — Django project settings and URL routing
- `media/` — user-uploaded content (profile pictures)
- `db.sqlite3` — local dev database (not shared — everyone gets their own
  via `migrate`)

See [CHANGELOG.md](CHANGELOG.md) for the pass-by-pass history of what's
been built.

## Recent updates (most recent first)

- Report comments: a comment thread on moderation Reports, with a
  "3 dots" per-comment options menu.
- Mail search: search box in `/mail/` to find conversations/messages.
- Mentioning `@all` and individual users in mail/forum text.
- Friend requests added to mail.
- Featured projects section (forum) reviewed/restyled twice.
- Moderation: mutes, bans, moderation history, and a full Reports +
  punishment-record system (Director/Admin only).
- Direct messages, forum comment section with styling.
- Profile status field.

Full pass-by-pass detail lives in [CHANGELOG.md](CHANGELOG.md).

## Managing the project — commands you'll actually use

```
cd TheFarLands                        # always run manage.py from here
pip3 install -r requirements.txt      # install/refresh dependencies
python3 manage.py migrate             # apply pending DB migrations
python3 manage.py makemigrations      # after changing a models.py — review the file before applying it
python3 manage.py runserver           # run the dev server at 127.0.0.1:8000
python3 manage.py createsuperuser     # create an admin login for /admin/
python3 manage.py shell               # Django shell for one-off DB queries
```

## ⚠️ Caution — things NOT to touch without care

- **`db.sqlite3`** — the live local database. Don't delete or overwrite it
  casually; you'll lose every local account, message, report, and forum
  post. It's tracked in git here, so if you break it, `git checkout --
  db.sqlite3` can restore the last committed copy — but that also throws
  away anything you did since the last commit.
- **`*/migrations/*.py`** — never hand-edit an existing (already-committed)
  migration file, and never delete one that's already been applied on a
  shared/committed database. Doing so desyncs the migration history from
  the actual table schema and can corrupt `db.sqlite3` in a way that's
  hard to undo. If a model changes, run `makemigrations` to generate a
  *new* file instead.
- **`tfl_site/settings.py`** — `SECRET_KEY` is a Django "insecure" dev key
  and `DEBUG = True`. Fine for local dev, but never ship this file as-is
  to anything public-facing. `ALLOWED_HOSTS` is locked to
  `127.0.0.1`/`localhost` on purpose.
- **`TENOR_API_KEY`** — read from an environment variable, not hardcoded.
  Don't paste a real key directly into `settings.py` or commit one.
- **`media/`** — real user-uploaded profile pictures. Don't bulk-delete;
  broken references show up as missing images on live profiles.
- **Moderation / Report / ban code (`mail/models.py`,
  `mail/views.py` moderation views)** — these enforce who can mute/ban/see
  reports (Director/Admin only). Loosening these checks is a permissions
  bug, not a style choice — be careful changing them.
- **The old frontend copy** under
  `../python_1/The Far Lands_Vol2/View point/` — don't run a server from
  there or point Live Server at it (see below); it's disconnected from the
  database entirely and any "login" there is fake.

## Git workflow (do this every time)

```
git status                    # see what changed before touching anything
git add .
git commit -m "description of what changed"
git push --all
```

Run `git status` first, always — it's the cheap check that stops you from
committing something you didn't mean to (like an unexpected file) or
missing something you did. Since `db.sqlite3` is tracked, `git status`
after working locally will usually show it as modified — that's normal
and expected to be committed along with code changes.

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
