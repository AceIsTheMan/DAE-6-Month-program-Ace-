"""
AI fallback for the David/F.R.E.D. site assistant widget
(accounts/templates/_ai_assistant_widget.html). The scripted Q&A in
accounts.assistant_content always gets first shot; ai_reply() is only
meant to be tried when match_question() finds nothing.

ai_reply() returns None for anything that isn't a usable AI answer -
provider switched off, bad persona, empty/too-long message, or (for
now) no provider wired up yet. The widget treats {'reply': None} as
"use the generic placeholder lines", so returning None is always safe.
"""

# 'none' = AI off, the site behaves exactly like the scripted-only version.
AI_PROVIDER = 'none'

MAX_MESSAGE_LENGTH = 500


def ai_reply(persona, message):
    if AI_PROVIDER == 'none':
        return None
    if persona not in ('fred', 'david'):
        return None
    message = (message or '').strip()
    if not message or len(message) > MAX_MESSAGE_LENGTH:
        return None
    # Provider call goes here (Step 4).
    return None

# 'none' = AI off the site behaves exactly like the scripted-only version
# Other values: 'ollama', 'free_api'.
AI_PROVIDER = 'none'

MAX_MESSAGE_LENGTH = 500
REQUEST_TIMEOUT_SECONDS = 8

# Step 3: one system prompt per persona (voice+ what the site is + rules).
PERSONA_PROMPT = {
    'david: TODO: David's voice and rules",
    'fred: "TODO: F.R.E.D.'s voice and rules",
}
