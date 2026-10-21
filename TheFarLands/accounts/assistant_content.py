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
wording/voice), an optional 'guest_tail' per persona for the one line
that should only show up for a guest/no-account asker, and an optional
'max_length' - caps how long the typed message can be for this entry to
match at all. Needed for short/common triggers like "hi" or "hey",
which would otherwise match as a substring of an unrelated longer
message ("hi, how do I block someone" containing "hi"). See
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
    {
        'id': 'can_i_delete_comment',
        'triggers': [
            'can i delete my comment',
            'can i delete my post',
            'how do i delete my comment',
            'how do i delete my post',
            'can i delete a comment',
            'how to delete my comment',
            'how to delete a comment',
            'can i remove my comment',
        ],
        'david': [
            "Yep! Just find the 3-dot menu on your comment or post and hit delete. Woof! Easy to clean up after yourself!",
            "You can delete your own comments anytime from that little menu on them. Woof! Posts are Director-only though, so that part's not on you!",
            "There's a delete option right on your comments - just look for the 3 dots. Woof! Gone in a click!",
            "Your own comments, sure, delete whenever! Just use the menu on the comment itself. Woof! Posting's Director-only, but your comments are all yours to manage!",
        ],
        'fred': [
            "Your own comments, yes - 3-dot menu, delete. Posts are Director-only, so that's not available to you.",
            "Comments you've written can be deleted from their menu. Posting itself is Director-only, separate matter.",
            "Delete option's on the comment's menu. Works for your own comments only. Posts aren't something you can remove - Director-only content.",
            "Yes, for comments. 3 dots, delete, done. Posts are a different story - Director-only, can't touch those.",
        ],
    },
    {
        'id': 'how_do_i_report',
        'triggers': [
            'how do i report a message',
            'how do i report someone',
            'how to report a message',
            'how to report someone',
            'can i report a message',
            'how do i report',
            'how to report',
            'how do i report a user',
        ],
        'david': [
            "There's a report option on any message - just find the 3-dot menu and hit report! Woof! We take that stuff seriously, don't worry!",
            "You can report any message straight from its menu. Woof! If something's not right, flag it and the team will look into it!",
            "Look for the 3 dots on the message and choose report. Woof! Thanks for keeping things safe around here!",
            "Reporting's built right into Mail - 3-dot menu, report, done. Woof! Never hesitate to use it if you need to!",
        ],
        'fred': [
            "3-dot menu on the message, report option. It goes to the moderation queue from there.",
            "Report option is on every message's menu. Flagged items go to Admin/Director review.",
            "Use the message's 3-dot menu to report it. Handled by moderation after that - no further action needed from you.",
            "Report from the message menu. It's logged and reviewed. Use it when something's actually wrong, not casually.",
        ],
    },
    {
        'id': 'why_no_vip_tab',
        'triggers': [
            'why dont i see the vip tab',
            'why can i not see the vip tab',
            'where is the vip tab',
            'i dont have a vip tab',
            'why is there no vip tab',
            'how do i get the vip tab',
            'why dont i have vip tab',
            'vip tab missing',
            'why is there no vip settings',
        ],
        'david': [
            "That tab only shows up once you've got active VIP! Head to the Store and grab a membership, and it'll appear right away. Woof! Hope to see you in there soon!",
            "VIP tab's hidden until you actually have VIP active. Grab it from the Store and it pops right up! Woof! Worth checking out!",
            "You'll need an active VIP membership for that tab to show. Store's got monthly and annual options! Woof! Totally your call though!",
            "That one only appears for VIP members. Visit the Store if you want in - it shows up the second you're active! Woof!",
        ],
        'fred': [
            "VIP tab only appears with an active VIP membership. Get one in the Store. It'll show immediately after.",
            "That's gated behind VIP status. No membership, no tab. Store has the options if you want it.",
            "Requires active VIP. Purchase one in the Store - tab appears right away, no delay.",
            "VIP tab is conditional on VIP status. Not active, not visible. Check the Store if that's something you want.",
        ],
    },
    {
        'id': 'role_hierarchy',
        'triggers': [
            "what's the difference between hacker agent admin and director",
            'whats the difference between the roles',
            'what are the different roles',
            'what are the account types',
            'what are the account roles',
            'what is a hacker account',
            'what is an agent account',
            'what is an admin account',
            'what is a director account',
            'what roles are there',
            'whats the role hierarchy',
        ],
        'david': [
            "Hacker's a 7-day guest trial, Agent's a regular full account, Admin helps moderate, and Director runs the whole show! Woof! Most folks start as Agent once they sign up properly!",
            "There's a ladder: Hacker (guest trial), Agent (regular account), Admin (moderation), Director (the big boss). Woof! Everyone starts around Agent level once they're official!",
            "Hacker's just a trial run, Agent's everyone's normal account, Admin keeps things in order, and Director's at the top. Woof! Hope you stick around past the Hacker stage!",
            "Four tiers: Hacker, Agent, Admin, Director, lowest to highest. Agent's the standard account once you're not a guest anymore. Woof! Pretty simple once you see it laid out!",
        ],
        'fred': [
            "Four roles, ascending: Hacker (guest trial, 7 days), Agent (standard account), Admin (moderation access), Director (full control). Most users are Agent-level.",
            "Hacker is a temporary guest account. Agent is standard. Admin moderates. Director has final authority. That's the hierarchy.",
            "Ranked lowest to highest: Hacker, Agent, Admin, Director. A regular registered account is Agent. Everything above that is granted, not self-selected.",
            "Hacker: guest trial. Agent: standard account. Admin: moderation tools. Director: top authority. Hierarchy's fixed.",
        ],
    },
    {
        'id': 'how_forum_search_works',
        'triggers': [
            'how do i search',
            'how does search work',
            'is there a search feature',
            'how do i find a post',
            'how do i search the forum',
            'how do i look for posts',
            'how do i find posts',
            'how do i search for something',
        ],
        'david': [
            "Just type keywords into the search bar up top and hit search! You can even filter by date posted. Woof! Great for finding old stuff!",
            "There's a search bar right on the Forum page - type what you're looking for, pick a date range if you want. Woof! Pretty handy!",
            "Search box up top, type your keywords, optionally narrow it by date. Woof! Finds posts fast!",
            "You can search the Forum by keyword and even a date range if you remember roughly when something was posted. Woof! Clear button's right there too if you want to start over!",
        ],
        'fred': [
            "Keyword search bar on the Forum page. Optional date range filter. Straightforward.",
            "Type keywords into the search bar. Date filters are available if you need to narrow it down.",
            "Forum search: keywords plus optional date-from/date-to filters. Clear button resets it.",
            "Search bar, keywords, optional date range. That's the full extent of it.",
        ],
    },
    {
        'id': 'how_turn_off_notifications',
        'triggers': [
            'how do i turn off notifications',
            'how to turn off notifications',
            'how do i disable notifications',
            'how to disable notifications',
            'can i turn off notifications',
            'how do i stop notifications',
            'turn off notifications',
            'disable notifications',
        ],
        'david': [
            "Head to Settings, Notifications tab, and flip the switch! Your messages still come in either way, it just stops the little badge from showing. Woof! Totally up to you!",
            "There's a notifications toggle in Settings - turning it off just hides the badge, your mail still works the same. Woof! Peace and quiet if you want it!",
            "Settings > Notifications has an on/off switch for that. Woof! Doesn't affect your messages at all, just the little alert badge!",
            "You can turn that off in Settings under Notifications. Woof! Everything still arrives, you just won't see the badge pop up!",
        ],
        'fred': [
            "Settings, Notifications tab. One toggle. Turns off the badge only - messages still arrive and get tracked normally.",
            "Notifications toggle is in Settings. Disabling it hides the badge, nothing else changes.",
            "Settings > Notifications. Flip it off. Purely cosmetic - doesn't affect message delivery.",
            "One switch in Settings handles it. Badge only. Your mail keeps working the same either way.",
        ],
    },
    {
        'id': 'greeting',
        'max_length': 20,
        'triggers': [
            'hi',
            'hello',
            'hey',
            'sup',
            'yo',
            'greetings',
            'hiya',
            'hey there',
            'hello there',
        ],
        'david': [
            "Hey there! Woof! Great to see you, what can I help with?",
            "Hi! Woof woof! What's up?",
            "Hello! Woof! Good to have you here, need anything?",
            "Heya! Woof! What can I do for you today?",
            "Oh, hi! Roof! Didn't see you come in, what's going on?",
            "Hey hey! Bark! Always happy when someone stops by!",
            "Hello, hello! Woof! What brings you here today?",
            "Hi there! Tail's wagging, Woof! What do you need?",
        ],
        'fred': [
            "Acknowledged. What do you need?",
            "You're here. What can I do for you?",
            "Standing by. Go ahead.",
            "Status: ready. What's the question?",
            "Noted your arrival. Proceed.",
            "Channel open. What's this about?",
            "I'm listening. State your business.",
            "Confirmed, you're online. What do you need from me?",
        ],
    },
    {
        'id': 'how_add_friend',
        'triggers': [
            'how do i add a friend',
            'how to add a friend',
            'how do i send a friend request',
            'how to send a friend request',
            'can i add a friend',
            'how do i make friends',
            'how do i friend someone',
            'how to friend someone',
        ],
        'david': [
            "Send them a friend request right from their profile! Once they accept, you're all set. Woof! Making friends here is always a good time!",
            "Head to their profile and hit friend request - easy as that! Woof! Hope you two hit it off!",
            "There's a friend request button on every profile. Send it, wait for them to accept, done! Woof!",
            "Just visit their profile and send a request! Woof! Nothing better than growing your friend list around here!",
        ],
        'fred': [
            "Friend request button is on their profile. Send it, they accept, you're connected. That's the whole process.",
            "Go to their profile, send a friend request. Pending until they accept.",
            "Profile page has the option. One click to send, their call to accept.",
            "Send the request from their profile. Confirmation's on them, not you.",
        ],
    },
    {
        'id': 'how_check_balance',
        'triggers': [
            'how do i check my balance',
            'how do i check my token balance',
            'how do i check my cipher tokens',
            'where is my balance',
            'how many tokens do i have',
            'where can i see my tokens',
            'how do i see my currency',
            'check my balance',
        ],
        'david': [
            "It's right in the nav bar! Click the notification dropdown and you'll see your Currency listed there. Woof! Easy to keep an eye on!",
            "Check the nav notification dropdown - your balance shows up right there. Woof! Also visible on the Store page if you're shopping!",
            "Your balance is in the nav dropdown, and it shows up again on the Store page too. Woof! Always easy to find!",
            "Click the notification icon up top - your Cipher Token count is right there. Woof! No digging required!",
        ],
        'fred': [
            "Nav notification dropdown shows your balance. Also visible on the Store page.",
            "Check the nav dropdown. Balance is listed under Currency. Same number shows on the Store page.",
            "Your balance is tracked in the nav bar dropdown and on the Store page. Always current.",
            "Nav dropdown, Currency row. That's your balance, live.",
        ],
    },
    {
        'id': 'what_happens_trial_expires',
        'triggers': [
            'what happens when my guest trial expires',
            'what happens when my trial expires',
            'what happens after 7 days',
            'what happens to my hacker account',
            'does my account get deleted',
            'will my account be deleted',
            'what happens when my guest account expires',
            'what happens after my trial ends',
        ],
        'david': [
            "Your account gets deleted after the 7 days are up, but don't worry - a record of you sticking around gets kept! Make a full account before time runs out if you want to keep going! Woof!",
            "Once the trial ends, the guest account is removed. Upgrade to a real account before then if you want to stay! Woof! Hope you do!",
            "After 7 days, it's gone - that's just how guest trials work. Woof! Make an account anytime before that to keep your spot!",
            "The account gets cleaned up automatically once your week is over. Woof! Best to upgrade before the clock runs out!",
        ],
        'fred': [
            "Guest accounts are deleted automatically once the 7-day trial ends. A record is kept that you existed, nothing more. Upgrade before then if you want to keep anything.",
            "Trial expires, account's gone - no exceptions. Convert to a full account first if you intend to stay.",
            "After 7 days, deletion is automatic. Everything tied to the guest account goes with it. Act before the deadline.",
            "Expiration means removal. That's the deal with guest trials. Upgrade in time if you want continuity.",
        ],
    },
    {
        'id': 'mail_cutscene_frequency',
        'triggers': [
            'how often does the mail cutscene play',
            'how often does the cutscene play',
            'how do i turn off the cutscene',
            'how do i change cutscene settings',
            'what is the loading screen',
            'how often does the loading screen play',
            'can i turn off the loading screen',
            'how do i stop the cutscene',
            'cutscene settings',
            'loading screen settings',
        ],
        'david': [
            "You get to pick! Settings has options for every time, a 10 minute cooldown, or never at all. Woof! I kinda like watching it myself!",
            "Head to Settings > Cutscenes - you can set it to always play, cool down for 10 minutes between plays, or turn it off completely! Woof!",
            "It's adjustable in Settings! Every time, every 10 minutes, or off for good. Woof! Your call!",
            "Check Settings > Cutscenes for that - three options there, from always-on to never. Woof! Totally up to you!",
        ],
        'fred': [
            "Settings > Cutscenes. Three modes: every time, 10-minute cooldown, or never. Pick one.",
            "Configurable in Settings. Always, cooldown, or off. Your preference.",
            "Cutscene frequency is adjustable - every time, every 10 minutes, or disabled. Settings > Cutscenes.",
            "Three settings available: always, cooldown, never. Found under Settings > Cutscenes.",
        ],
    },
    {
        'id': 'director_tools_classified',
        'triggers': [
            'what can the director do that i cant',
            'what are the director only tools',
            'what are director only features',
            'can i access director tools',
            'what is director only access',
            'what can directors do',
            'director only features',
            'director tools',
        ],
        'david': [
            "That's a secret! Woof! Can't say more than that.",
            "Shh, that's classified. Woof! My lips are sealed!",
            "Can't tell you that one - top secret! Woof!",
            "That's need-to-know only, and you don't need to know! Woof!",
        ],
        'fred': [
            "Classified.",
            "That's a secret.",
            "Not cleared for that information.",
            "Classified. Don't ask again.",
        ],
    },
    {
        # No password-change/reset feature exists anywhere on the site
        # (verified - no Settings option, no forgot-password flow).
        # Deliberately a flat, identical, personality-free line for both
        # personas rather than the usual in-character variants - this
        # is a real gap being honestly disclosed, not something to spin.
        'id': 'how_change_password',
        'triggers': [
            'how do i change my password',
            'how to change my password',
            'how do i reset my password',
            'how to reset my password',
            'can i change my password',
            'where do i change my password',
            'how do i update my password',
            'how to update my password',
        ],
        'david': [
            "This feature is not up yet. We will do our best until further noticed.",
        ],
        'fred': [
            "This feature is not up yet. We will do our best until further noticed.",
        ],
    },
    {
        'id': 'vip_monthly_vs_annual',
        'triggers': [
            'whats the difference between vip monthly and annual',
            'should i get monthly or annual vip',
            'is annual vip cheaper',
            'vip monthly vs annual',
            'whats the price difference for vip',
            'how much is vip',
            'how much does vip cost',
        ],
        'david': [
            "Monthly's $5 for 30 days, annual's $20 for 365 days - annual works out way cheaper per day if you're sticking around! Woof! Either way you get the same perks!",
            "You can do $5 a month, or $20 for the whole year - annual saves you a bunch if you're staying awhile! Woof! Up to you!",
            "Monthly is $5/30 days, yearly is $20/365 days. Do the math and yearly wins if you're in it for the long haul! Woof!",
            "Five bucks gets you a month, twenty bucks gets you a whole year! Woof! Annual's the better deal by far!",
        ],
        'fred': [
            "Monthly: $5, 30 days. Annual: $20, 365 days. Annual's the better value if you're committing long-term. Same perks either way.",
            "Two options: $5 for 30 days, or $20 for 365 days. Annual costs less per day. Perks are identical.",
            "Pricing: $5/month, $20/year. Annual is the more efficient choice if you intend to stay VIP.",
            "$5 buys 30 days. $20 buys 365. Same benefits either way - annual is simply cheaper over time.",
        ],
    },
    {
        'id': 'guest_pfp_store_restriction',
        'triggers': [
            'can guests set a profile picture',
            'can guest accounts use the store',
            'can hacker accounts use the store',
            'can guests upload a profile picture',
            'can hacker accounts set a profile picture',
            'can guests buy from the store',
            'do guest accounts have store access',
        ],
        'david': [
            "Guest accounts can't do either one, sorry! Make a full account and both open right up. Woof! Totally worth it!",
            "Nope, not for guest accounts - no profile picture, no Store access. Woof! Upgrading unlocks both though!",
            "Both are off-limits for Hacker accounts I'm afraid! Woof! A full account gets you in though!",
            "Guests miss out on those two, unfortunately. Woof! Make a real account and you're good to go!",
        ],
        'fred': [
            "No to both - guest accounts can't set a profile picture or access the Store. Full account required for either.",
            "Negative on both. Profile pictures and the Store are blocked for guest accounts.",
            "Guest restriction: no profile picture, no Store access. Resolved by upgrading to a full account.",
            "Both features are gated behind a full account. Guest accounts don't qualify.",
        ],
    },
]


def _normalize(text):
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def _contains_word_sequence(haystack_words, needle_words):
    """True if needle_words appears as a contiguous run inside
    haystack_words. Word-level, not character-level - "hi" must not
    match inside "this" just because the letters happen to appear in
    that order (t-HI-s)."""
    n = len(needle_words)
    if n == 0 or n > len(haystack_words):
        return False
    return any(haystack_words[i:i + n] == needle_words for i in range(len(haystack_words) - n + 1))


def match_question(message):
    """Return the QA_ENTRIES entry that best matches the user's message,
    or None if nothing matches closely enough. Word-sequence match
    against an entry's trigger phrases only - deliberately simple, not
    fuzzy/keyword-scored, so it never confidently answers the wrong
    question."""
    normalized = _normalize(message)
    if not normalized:
        return None
    input_words = normalized.split()
    for entry in QA_ENTRIES:
        max_length = entry.get('max_length')
        if max_length and len(normalized) > max_length:
            continue
        for trigger in entry['triggers']:
            trigger_words = _normalize(trigger).split()
            if (
                input_words == trigger_words
                or _contains_word_sequence(input_words, trigger_words)
                or _contains_word_sequence(trigger_words, input_words)
            ):
                return entry
    return None
