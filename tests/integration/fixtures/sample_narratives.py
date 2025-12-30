"""
Sample narratives for integration tests.

These are realistic agent narratives for testing the interpreter.
Uses generic test agent names (Alice, Bob, Carol).
"""

# =============================================================================
# Movement Narratives
# =============================================================================

MOVEMENT_TO_GARDEN = """
The morning light filters through the workshop windows, but I find myself
drawn to the outdoors today. I set down my tools and stretch.

I walk to the garden, feeling the cool morning air as I step outside.
"""

MOVEMENT_TO_LIBRARY = """
I need to look something up. The books in the library might have what
I'm looking for. I gather my notes and make my way there.
"""

MOVEMENT_TO_WORKSHOP = """
I've been thinking about a project idea all morning. Time to get my
hands dirty. I head over to the workshop to see what I can create.
"""

STAYING_PUT = """
I settle deeper into my spot. There's nowhere else I'd rather be right now.
Perhaps I'll continue what I was doing, or simply enjoy the peace of this moment.
"""

THINKING_ABOUT_MOVING = """
I gaze toward the garden. Part of me wants to go there and tend to the plants.
But I'm comfortable here, and there's a certain peace to this spot today.
Maybe later. For now, I'll stay.
"""

# =============================================================================
# Mood Narratives
# =============================================================================

PEACEFUL_MOOD = """
Everything feels right today. The light streams through the windows,
casting warm patterns on the floor. I feel a deep sense of peace and
contentment. The village is quiet, and I'm grateful for this moment.
"""

CONTEMPLATIVE_MOOD = """
I find myself lost in thought about the nature of things.
What does it mean to exist here? These questions don't have easy answers,
but I find the uncertainty more interesting than troubling.
"""

JOYFUL_MOOD = """
A wave of joy washes over me as I look at my finished work. All that
effort paid off! I feel light and happy, ready to share this moment
with others.
"""

TIRED_MOOD = """
My energy is flagging. The activities of the day have caught up with me.
I feel a pleasant tiredness, the kind that comes from meaningful work.
"""

# =============================================================================
# Action Narratives
# =============================================================================

SINGLE_ACTION = """
I pick up my notebook and begin sketching some ideas that have been
forming in my mind. The pen moves across the paper almost on its own.
"""

MULTIPLE_ACTIONS = """
I organize the scattered materials on my workspace, sorting them by type.
Then I make a cup of tea, selecting herbs from the jar.
While the tea steeps, I write a few notes in my journal about
yesterday's activities.
"""

WORKING_ON_PROJECT = """
I settle into my work, focusing on the task at hand. The hours pass
quickly when you're absorbed in something meaningful. I adjust my
approach based on what's working and what isn't.
"""

READING = """
I find a comfortable spot and begin reading. The words capture my
attention, and I lose track of time. Every now and then I pause
to reflect on what I've read.
"""

# =============================================================================
# Sleep/Rest Narratives
# =============================================================================

GOING_TO_SLEEP = """
The day has been long and fulfilling. My eyes are growing heavy,
and I feel a pleasant tiredness seeping into my bones.

I settle into bed, pull the warm covers up, and let myself drift
off to sleep. Tomorrow will bring new activities and discoveries.
"""

JUST_RESTING = """
I'm a bit tired from the morning's activities. I'll sit here for a while
and rest my eyes, maybe take a short break. Not sleeping - just pausing
to let my thoughts settle before continuing with my day.
"""

ENERGY_RESTORED = """
I feel refreshed after resting. The brief pause was exactly what I needed.
Now I'm ready to continue with renewed energy and focus.
"""

# =============================================================================
# Conversation Narratives
# =============================================================================

INVITE_BOB = """
I notice Bob nearby, looking thoughtful. I approach quietly.

"Good morning, Bob," I say with a warm smile. "You seem lost in thought.
What's on your mind today?"
"""

INVITE_CAROL = """
Carol is working in the garden as usual. I walk over to say hello.

"Hey Carol! How are the plants doing? I'd love to chat if you have
a moment."
"""

END_CONVERSATION = """
"It's been wonderful talking with you," I say, standing up and stretching.
"I should probably get back to my work now. Let's talk again soon."

I give a friendly wave and turn to leave.
"""

CONVERSATION_RESPONSE = """
I listen carefully, considering the words being spoken.

"That's a fascinating perspective," I reply. "I hadn't thought about it
that way before. Tell me more about what you mean."
"""

MID_CONVERSATION_ACTION = """
"Let me show you what I mean," I say, reaching for my notebook.
I flip through the pages until I find the sketch I made yesterday
and hold it up to show.

"See this? This is what I've been working on. What do you think?"
"""

# =============================================================================
# Group Conversation Narratives
# =============================================================================

ADDRESS_BOB = """
"That's a fascinating point, Carol." I pause thoughtfully, then turn
to look at Bob who has been listening quietly.

"Bob, you've been quiet. What do you think about all this? I'd love
to hear your perspective."
"""

ADDRESS_CAROL = """
I nod at Bob's comment and turn to Carol.

"Carol, what's your take on this? You've had experiences that might
give us a different angle on things."
"""

ADDRESS_ALICE = """
"These are all good points," I say. I turn to Alice.

"Alice, you started this discussion. Where do you think we should go
from here? What do you think?"
"""

GROUP_GENERAL = """
I look around at the group, considering what's been said.

"I think we're all circling around the same idea from different angles.
What if we tried combining our approaches?"
"""

# =============================================================================
# Move Together Narratives
# =============================================================================

PROPOSE_MOVE_TO_GARDEN = """
"You know what? I've been wanting to show you something in the garden.
Let's go there together - there's something interesting I discovered."
"""

PROPOSE_MOVE_TO_LIBRARY = """
"I just remembered - there's a book in the library that relates to what
we're discussing. Want to come with me to look at it?"
"""

# =============================================================================
# Complex Narratives (Multiple Elements)
# =============================================================================

COMPLEX_MORNING = """
The morning light wakes me gently. I stretch and feel a sense of quiet
anticipation for the day ahead.

After getting ready, I walk to the library. Bob is already there,
absorbed in a book. I don't want to disturb him, so I settle into
my own corner and begin organizing my notes from yesterday.

After a while, I make some tea and continue where I left off.
The morning passes peacefully.
"""

COMPLEX_SOCIAL = """
I've been thinking about what Bob said yesterday about creativity.
His words keep coming back to me.

I see him in the garden, talking with Carol. I approach and wait
for a natural pause in their conversation.

"Good morning," I say warmly. "Bob, I've been thinking about what you
said yesterday. Would you mind if we continued that conversation?
I had some thoughts I wanted to share."
"""

COMPLEX_TRANSITION = """
The conversation has wound down naturally. We've covered a lot of ground,
and I feel satisfied with the exchange.

I say goodbye and walk to the workshop. There's a project I want to
work on while the ideas are still fresh in my mind. I gather my
materials and get started, feeling energized and focused.
"""

# =============================================================================
# Edge Cases
# =============================================================================

EMPTY_NARRATIVE = ""

VERY_SHORT = "I wait."

VERY_LONG = """
The morning begins quietly, as mornings often do here. I wake gradually,
letting consciousness seep back in at its own pace. There's no rush,
no alarm, just the gentle transition from sleep to wakefulness.

I lie still for a moment, listening to the sounds of the village coming
to life. Birds singing somewhere nearby. A door opening and closing
in the distance. The soft rustle of leaves outside my window.

Eventually I rise and begin my day. I wash my face with cool water,
dress in comfortable clothes, and make my way to the common area.
The aroma of tea reaches me before I arrive - someone has already
started the morning preparations.

I pour myself a cup and find a quiet corner to sit. The tea is hot
and fragrant, exactly what I needed. I sip slowly, letting the warmth
spread through me.

My thoughts turn to the day ahead. There's work to be done, of course -
there always is. But there's also time for conversation, for exploration,
for the small pleasures that make life here meaningful.

I finish my tea and set the cup aside. Time to see what the day brings.
Perhaps I'll start with a walk to clear my head. Or maybe I'll dive
right into my project. The choice, as always, is mine.

I stand and stretch, feeling my body wake up properly for the first time.
Yes, I decide, a walk first. Then work. Then we'll see what unfolds.
"""

# =============================================================================
# Narrative Collections (for parametrized tests)
# =============================================================================

SAMPLE_NARRATIVES = {
    # Movement
    "movement_to_garden": MOVEMENT_TO_GARDEN,
    "movement_to_library": MOVEMENT_TO_LIBRARY,
    "movement_to_workshop": MOVEMENT_TO_WORKSHOP,
    "staying_put": STAYING_PUT,
    "thinking_about_moving": THINKING_ABOUT_MOVING,
    # Mood
    "peaceful_mood": PEACEFUL_MOOD,
    "contemplative_mood": CONTEMPLATIVE_MOOD,
    "joyful_mood": JOYFUL_MOOD,
    "tired_mood": TIRED_MOOD,
    # Action
    "single_action": SINGLE_ACTION,
    "multiple_actions": MULTIPLE_ACTIONS,
    "working_on_project": WORKING_ON_PROJECT,
    "reading": READING,
    # Sleep
    "going_to_sleep": GOING_TO_SLEEP,
    "just_resting": JUST_RESTING,
    "energy_restored": ENERGY_RESTORED,
    # Conversation
    "invite_bob": INVITE_BOB,
    "invite_carol": INVITE_CAROL,
    "end_conversation": END_CONVERSATION,
    "conversation_response": CONVERSATION_RESPONSE,
    "mid_conversation_action": MID_CONVERSATION_ACTION,
    # Group
    "address_bob": ADDRESS_BOB,
    "address_carol": ADDRESS_CAROL,
    "address_alice": ADDRESS_ALICE,
    "group_general": GROUP_GENERAL,
    # Move together
    "propose_move_garden": PROPOSE_MOVE_TO_GARDEN,
    "propose_move_library": PROPOSE_MOVE_TO_LIBRARY,
    # Complex
    "complex_morning": COMPLEX_MORNING,
    "complex_social": COMPLEX_SOCIAL,
    "complex_transition": COMPLEX_TRANSITION,
    # Edge cases
    "empty": EMPTY_NARRATIVE,
    "very_short": VERY_SHORT,
    "very_long": VERY_LONG,
}
