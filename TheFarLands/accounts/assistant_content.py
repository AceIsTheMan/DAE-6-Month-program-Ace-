"""
Scripted Q&A content for the David/F.R.E.D. site assistant widget
(accounts/templates/_ai_assistant_widget.html). No real AI involved -
QA_ENTRIES is a hand-written list of common questions, each with a few
phrasings a user might actually type ('triggers') and a few differently-
worded answers per persona ('david'/'fred') so repeat questions don't
feel robotic. match_question() does simple phrase matching, not NLP -
good enough for a fixed set of known questions, not meant to handle
open-ended conversation.

Adding a new question: append an entry to QA_ENTRIES with a few trigger
phrasings, 3-4 answer variants per persona (same facts, different
wording/voice), and an optional 'guest_tail' per persona for the one
line that should only show up for a guest/no-account asker (see
match_question's caller in accounts.views.assistant_reply for how that
gets appended).
"""
import re

QA_ENTRIES = [
    {
        'id': 'what_is_far_lands',
        'triggers': [
            'what is the far lands',
            'what is this website',
            'what is this site',
            'what is this',
            'whats this',
            'whats this website',
            'whats this site',
            'what is this place',
            'whats this place',
            'what is far lands',
            'what is this app',
        ],
        'david': [
            "This site's where it all happens for The Far Lands - that's the actual game we're building, Woof! It's still cooking behind the scenes, so stick around, more's coming soon!",
            "We're the home base for The Far Lands, the game! You'll catch every update as it drops. Woof! It's still being built, but that just means more surprises later!",
            "Think of this as basecamp for The Far Lands - the game, not the site! It's still in the works, but Woof! getting closer every day!",
            "This website is all about The Far Lands, the game that's coming! Woof! It's still in development, but that's half the fun of being here early!",
        ],
        'fred': [
            "The Far Lands is a game. Still in development - nothing's live yet. This site is your access point for intel as it drops. Updates, previews, whatever's been cleared for release. Stay sharp.",
            "This site exists for one purpose: tracking The Far Lands, the game currently in development. You get access to updates and previews as they're cleared. Nothing's released yet. That will change.",
            "The Far Lands - a game, in active development. You're looking at its intelligence hub. Updates get cleared for release here. Patience required.",
            "This isn't the game. It's the staging ground for it. The Far Lands is still being built. You get every update the moment it's cleared. Stay tuned.",
        ],
        'guest_tail': {
            'david': "Make an account so you don't miss anything - Woof!",
            'fred': "Create an account for clearance to this intel.",
        },
    },
    {
        'id': 'how_do_i_block',
        'triggers': [
            'how do i block someone',
            'how do i block a user',
            'how to block someone',
            'how to block a user',
            'how do i block',
            'how to block',
            'can i block someone',
            'how do i block people',
        ],
        'david': [
            "Head to their profile and look for the block option! Once blocked, they can't message you, friend-request you, or find you in Mail search. Woof! Your space, your rules!",
            "There's a block button right on their profile's menu. After that, no more messages or friend requests from them, and they won't even see you in search. Woof! Easy peace of mind!",
            "Go to their profile, find the 3-dot menu, hit block. Woof! They're locked out of messaging and finding you after that - simple as that!",
            "You can block anyone straight from their profile. It stops their messages, friend requests, and search results involving you. Woof! Nobody should have to deal with someone they don't want around!",
        ],
        'fred': [
            "Block them from their profile's menu. After that: no messages, no friend requests, no appearing in their Mail search. Done.",
            "Profile page, 3-dot menu, block. It cuts off messaging, friend requests, and search visibility both ways. Effective immediately.",
            "Blocking is on their profile. Once active, they lose all contact channels to you. No further action needed on your end.",
            "Go to their profile, use the block option. Messaging, friend requests, search - all severed. Your call to reverse it later if you want.",
        ],
    },
    {
        'id': 'how_change_profile',
        'triggers': [
            'how do i change my profile picture',
            'how do i change my pfp',
            'how do i change my bio',
            'how do i change my profile',
            'how to change profile picture',
            'how to change my pfp',
            'how to change my bio',
            'how do i edit my profile',
            'how to edit my profile',
        ],
        'david': [
            "Head to Settings and look for Edit Profile! You can swap your picture and update your bio right there. Woof! Make it your own!",
            "It's all in Settings, under your profile - upload a new picture, write a new bio, whatever you like! Woof! Show off a little!",
            "Go to Settings, find the profile edit section, and you can change your picture and bio anytime. Woof! Easy as that!",
            "Settings has an Edit Profile spot for exactly that - new picture, new bio, update whenever you want. Woof! Love seeing people personalize their page!",
        ],
        'fred': [
            "Settings, Edit Profile. Picture and bio, both editable there. Update whenever you need.",
            "Go to Settings. Profile edit panel handles your picture and bio. Straightforward.",
            "Your profile picture and bio are both changeable in Settings. No restrictions on how often.",
            "Settings - Edit Profile. Swap the picture, rewrite the bio, done. Nothing complicated about it.",
        ],
    },
]


def _normalize(text):
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def match_question(message):
    """Return the QA_ENTRIES entry that best matches the user's message,
    or None if nothing matches closely enough. Exact/substring match
    against an entry's trigger phrases only - deliberately simple, not
    fuzzy/keyword-scored, so it never confidently answers the wrong
    question."""
    normalized = _normalize(message)
    if not normalized:
        return None
    for entry in QA_ENTRIES:
        for trigger in entry['triggers']:
            if normalized == trigger or trigger in normalized or normalized in trigger:
                return entry
    return None
