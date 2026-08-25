# This folder is not the live site

`TFL_index.html` used to live here and could be opened directly (or through
tools like VS Code's "Live Server") to preview the front end on its own.
That's what caused a lot of confusion — this copy doesn't share login state
with the real app and doesn't get any of the ongoing fixes.

**The real site now lives in the Django project at the top of this repo.**
To view it:

```
cd "/Users/Adult/Desktop/DAE_6_Month_program_ACE"
python3 manage.py runserver
```

Then open **http://127.0.0.1:8000/** in your browser. Do not open any
`.html` file in this folder directly, and don't point Live Server (or
anything else) at it — it's kept only for reference, in `_pre_fix_backup/`.
