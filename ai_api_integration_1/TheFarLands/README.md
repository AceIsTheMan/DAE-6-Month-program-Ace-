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

Sending a GIF in the Mail app's Social composer doesn't need any API key
or setup: attach a `.gif` file with `[ ATTACH ]` like any other image, or
paste a GIF/image link (from Tenor's site, Giphy, wherever) straight into
the message text — it auto-embeds as an inline preview when the message
renders (see `forum/sanitize.py::embed_image_links`). There used to be an
in-app GIF search button backed by Tenor's API, then GIPHY's, but Google
discontinued the Tenor API on 2026-06-30 and the picker was dropped
rather than chase a second dead provider — no third-party GIF service is
wired in anymore.

## Pages / routes

- `/` — the main site (public)
- `/register/` — create a full account (username, email, password) — you'll
  need to click a verification link before you can log in, see below
  (code: `accounts/views.py`, `accounts/forms.py` 👍)
- `/guest/` — create a temporary "Hacker" guest account (username + password
  only, no email, no verification step, expires after 7 days)
  (code: `accounts/views.py` 👍)
- `/login/` — log in (same form for both account types)
  (code: `accounts/views.py` 👍)
- `/profile/` — your profile: photo, rank, alias, bio, with an inline
  "// EDIT PROFILE" section
  (code: `accounts/views.py`, `accounts/models.py` 👍)
- `/profile/<username>/` — view someone else's profile (read-only)
  (code: `accounts/views.py` 👍)
- `/mail/` — internal site mail: Inbox/Sent/Updates/Social/Reports, reached
  via the envelope icon in the nav (hidden for guest accounts) - this is
  in-site messaging stored in the database, not real email
- `/settings/` — gear icon page, tabbed:
  - **Settings** — every account's own personal settings, with its own
    row of sub-tabs:
    - **Profile** — the same photo/alias/bio/status form as `/profile/`'s
      "// EDIT PROFILE" section, reused via a shared include
      (`accounts/templates/_profile_edit_panel.html`)
    - **Blocked** — every account you've blocked, with an Unblock button
    - **Notifications** — on/off for the unread-mail badge (envelope nav
      icon + Mail sidebar counts) — off doesn't stop mail from arriving,
      it just stops surfacing that badge
    - **Cutscenes** — Always/10-Minute Cooldown/Never for the Mail tab's
      boot-up terminal splash, plus a separate on/off for "C1" (see
      below)
  - **Dashboard** (Admin/Director only) — account totals, open Report
    count, a by-username search showing warn/mute/ban counts, and the
    expired guest-account archive
  - **Chat Logs**, **Admin Logs**, **All Users** (Director only) —
    soft-deleted post/comment/message recovery (Re-Send/Purge), an
    audit trail of Admin-role actions, and a full account table
  - every gated tab is checked server-side, not just hidden by the tab
    UI (code: `accounts/views.py::settings_view` 👍)
- `/admin/` — Django admin (run `python3 manage.py createsuperuser` first)

## Cutscenes

Three unrelated families of retro-terminal splash screen, all purely
cosmetic:

- **Mail boot-up terminal** — plays when you click the "Mail" nav icon's
  "Mail" dropdown item specifically (not from clicking around inside Mail
  itself). Frequency is a per-account setting under Settings → Cutscenes.
  (code: `mail/templates/mail/index.html`, `accounts/templates/
  _nav_mail_icons.html` 👍)
- **"C1"** — a secret, site-wide easter egg, unrelated to Mail. Plays
  automatically on a 1-in-100 chance every time you switch back to the
  browser tab: red terminal text types out, then the lore-code flood
  (agents/hackers, rumors of a King, the Creator, factions, brainwashed
  militias, corruption) reads left-aligned down the screen before cutting
  instantly to green. A Director can also trigger it on demand by typing
  `!cmd_C1` into any text field or textarea anywhere on the site. Toggle
  it off entirely under Settings → Cutscenes → "C1" — off means neither
  trigger plays, cheat code included.
  (code: `accounts/templates/_secret_cutscene.html` 👍)
- **Role-based create/login cutscenes** — six scenes, each tied to a real
  account event and each independently Director-previewable on demand via
  its own cheat code (typed into any text field or textarea anywhere on
  the site, same as "C1"'s). The real trigger for a "_create" one only
  ever fires once, on that account's first successful login ever (see
  `CustomUser.has_completed_first_login`); every login after that gets
  the matching "_login" scene instead. Admin/Director have no "_create"
  scene (those roles are only ever reached by promotion, never public
  self-registration), so every one of their logins is a "_login". Shares
  its typing/dot-loading/glitch/color-cycle engine with "C1"
  (`accounts/templates/_cutscene_engine.html`).
  - `!cmd_CAgent` — a brand-new Agent account's first login (plays once
    the "BE ADVISED" rules gate is agreed to and dismissed)
  - `!cmd_CAgentLogin` — an Agent's regular (non-first) login
  - `!cmd_CGuest` — a brand-new Guest ("Hacker") account's first login
  - `!cmd_CGuestLogin` — a Guest's regular login, including the real
    computed "days:hours:minutes" left on their trial
    (`CustomUser.guest_expires_at`)
  - `!cmd_CAdminLogin` — an Admin's login, including a simulated Director
    chat interruption with the real Director's profile picture
  - `!cmd_CDirector` — the Director's own login
  - (code: `accounts/templates/_role_cutscenes.html`, `accounts.signals.
    queue_role_cutscene_on_login`, `accounts.views.home_view` 👍)
  - `!cmd_?` — not a cutscene: a Director-only, 10-second, display-only
    panel that dims the page and lists every cheat code above with what
    it does, for review

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
  (`accounts/static/accounts/`, `accounts/templates/`) — all account
  coding lives here: `models.py` (CustomUser), `views.py`, `forms.py`,
  `signals.py`, `middleware.py` 👍
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

- Six role-based create/login terminal cutscenes (Agent/Guest/Admin/
  Director), each with a real account-event trigger and a Director-only
  preview cheat code, plus a `!cmd_?` review panel listing every cheat
  code. See "Cutscenes" above.
- Settings tab built out: Profile/Blocked/Notifications/Cutscenes
  sub-tabs for every account, plus "C1" — a secret, site-wide easter-egg
  cutscene (1/100 chance on switching back to the browser tab, or a
  Director-only `!cmd_C1` cheat code), with its own off toggle. See
  "Cutscenes" above.
- Mail tab boot-up terminal splash (plays from the nav's "Mail" link),
  Mail sidebar unread badges broken down per category, Sent tab scoped
  to Draft-composed messages only, "Load More" pagination for Sent.
- Query optimization pass across Mail: fixed an N+1 in the unread-badge
  notification count and in the Social sidebar's DM-partner lookup.
- Dropped the Tenor/GIPHY GIF-search picker from Mail's Social composer
  (Google discontinued the Tenor API on 2026-06-30). GIFs now go through
  the existing attachment field or a plain link pasted into the message
  text, auto-embedded as an inline preview.
- Dashboard settings tab: Admin/Director-only moderator tools behind
  `/settings/?tab=dashboard` (and Director-only Chat Logs/Admin Logs/All
  Users tabs) — account search, expired-guest archive, soft-delete
  recovery, admin activity audit trail.
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
