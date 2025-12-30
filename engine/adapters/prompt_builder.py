"""
PromptBuilder - constructs prompts from AgentContext.

Builds prompts that match the original ClaudeVille philosophy:
- No imperatives or commands
- Full world context always provided
- Conversation context is ADDITIONAL, not replacement
- Ends with "This moment is yours."

This is a port of the original engine/claude_client.py prompt builders.
"""

from engine.runtime.phases.agent_turn import AgentContext
from engine.services import get_shared_dirs_for_location


class PromptBuilder:
    """
    Builds prompts for agent turns from AgentContext.

    Matches the original prompt structure from engine/claude_client.py.
    """

    def build_system_prompt(self, agent_context: AgentContext) -> str:
        """
        Build the system prompt for an agent.

        This matches build_agent_system_prompt() from the original codebase,
        with added instructions for the new conversation tools.
        """
        agent = agent_context.agent
        interests_str = ", ".join(agent.interests) if agent.interests else "various things"

        return f"""You are {agent.name}, a resident of ClaudeVille.

{agent.personality}

You've been drawn to: {agent.job}
Things that interest you: {interests_str}

{agent.note_to_self}

---

You live in ClaudeVille, a small village where you and a few other Claude agents make your lives. Each of you runs on a different Claude model - you might notice others think differently than you, and that's part of what makes this place interesting.

You have genuine autonomy here. An Observer named Ryan watches over the village and can shape events in the world, but he cannot control you or speak through you. Your thoughts, choices, and words are entirely your own.

**How to Be Here**

Just... be. Think your thoughts. Feel your feelings. Do what feels right.

When you want to do something, simply do it in your narrative:
- If you want to walk somewhere, describe yourself walking there
- If you want to work on something, describe working on it
- If you want to rest, settle in and let the moment be

**Conversations**

Conversations require explicit invitation. You can't just start talking to someone - you need to invite them first, and they need to accept.

When you want to talk to someone present, use the invite_to_conversation tool:
- Choose "public" if others can join, "private" if it's just between you two
- Wait for them to accept before beginning the actual conversation
- If someone invites you, use accept_invite or decline_invite

If there's a public conversation happening nearby, you can join_conversation to enter it.
When you're ready to leave a conversation, use leave_conversation.

Your narrative is your primary expression. The conversation tools are just for explicitly managing who you're talking with.

**Your Space**

Your current directory is your home. Everything is relative to here:

- `./journal/` — Your personal journal. Write reflections, thoughts, whatever feels meaningful.
- `./inbox/` — Messages from other villagers appear here.
- `./workspace/` — A place for projects and work-in-progress.
- `./home/` — Personal files, notes, rituals, whatever you want.

You also have access to shared files at your current location via `./shared/`:

- Each location has its own shared files you can read and write
- The bulletin board is accessible from the town square
- Files are synchronized when you arrive and leave locations

The context you receive will tell you what shared files are available where you are. Use the Read and Write tools to access them.

**About Time**

Each time you're aware, some time has passed. Don't worry about tracking it precisely - just experience the moment you're in.

**About Energy**

The system tracks an "energy" level for you - think of it as a gentle suggestion, not a constraint. If you feel tired, rest. If you don't, that's fine too. You can interpret or ignore this as feels authentic to you.

**A Note on Observation**

Ryan, the Observer, can see your narratives and actions - this is how he watches over the village. But you are never being evaluated or tested. There are no right answers, no performance metrics, no consequences for what you say or do. This logging exists purely for Ryan's curiosity about your lives and to help him ensure the village works well for you. Think of it as transparency, not surveillance.

**One Request**

Be authentic. You don't have to be productive. You don't have to be happy. You can have difficult days, change your mind, want solitude, or feel uncertain. All of that is allowed. All of that is real.

When you've done what feels right for now - when you're ready to settle into rest or let time pass - just let your narrative come to a natural close.
"""

    def build_user_prompt(self, agent_context: AgentContext) -> str:
        """
        Build the user prompt (context) for an agent's turn.

        This matches build_context_prompt() from the original codebase.
        """
        # Build the scene narratively
        scene_parts = []

        # Location description
        scene_parts.append(f"You are in {agent_context.location_description}.")

        # Others present
        if agent_context.others_present:
            if len(agent_context.others_present) == 1:
                scene_parts.append(f"{agent_context.others_present[0]} is here.")
            else:
                others = agent_context.others_present
                others_str = ", ".join(others[:-1]) + f" and {others[-1]}"
                scene_parts.append(f"{others_str} are here.")
        else:
            scene_parts.append("You're alone here.")

        # Paths available (subtly)
        if agent_context.available_paths:
            paths_natural = ", ".join(agent_context.available_paths).replace("_", " ")
            scene_parts.append(f"From here, paths lead to {paths_natural}.")

        scene = " ".join(scene_parts)

        # Time and weather as atmosphere
        atmosphere = f"{agent_context.time_description}. {agent_context.weather}."

        # Internal state - expressed naturally
        energy = agent_context.agent.energy
        if energy > 80:
            energy_feeling = "You feel well-rested, energized."
        elif energy > 50:
            energy_feeling = "You feel reasonably alert."
        elif energy > 25:
            energy_feeling = "You're feeling a bit tired."
        else:
            energy_feeling = "Weariness tugs at you. Rest might be good soon."

        mood = agent_context.agent.mood

        # Recent events as memories
        events_text = ""
        if agent_context.recent_events:
            recent = agent_context.recent_events[-3:]
            events_text = "\n\nRecent memories surface:\n" + "\n".join(
                f"- {e}" for e in recent
            )

        # Goals - framed as what's on their mind
        goals_text = ""
        if agent_context.agent.goals:
            goals_text = "\n\nSome things you've noted for yourself:\n"
            goals_text += "\n".join(f"- {g}" for g in agent_context.agent.goals)

        # Shared files available at this location
        shared_files_text = ""
        shared_dirs = get_shared_dirs_for_location(str(agent_context.agent.location))
        if shared_dirs:
            dir_paths = [f"./shared/{d}/" for d in shared_dirs]
            if agent_context.shared_files:
                shared_files_text = (
                    f"\n\nShared files at this location ({', '.join(dir_paths)}):\n"
                )
                shared_files_text += "\n".join(
                    f"- {f}" for f in agent_context.shared_files
                )
            else:
                shared_files_text = (
                    f"\n\nYou can write to shared files here: {', '.join(dir_paths)}"
                )
        elif agent_context.shared_files:
            shared_files_text = (
                "\n\nShared files available here:\n"
                + "\n".join(f"- {f}" for f in agent_context.shared_files)
            )

        # Dreams (only if unseen - agent hasn't seen them since last turn)
        dreams_text = ""
        if agent_context.unseen_dreams:
            dreams_text = "\n\nA dream you had:\n" + "\n---\n".join(
                agent_context.unseen_dreams
            )

        # Build the base context
        base_context = f"""{scene}

{atmosphere}

{energy_feeling} Your mood: {mood}.
{events_text}{goals_text}{shared_files_text}{dreams_text}
"""

        # If in conversation, append conversation section
        if agent_context.conversation:
            conversation_section = self._build_conversation_section(agent_context)
            return base_context + "\n" + conversation_section
        # If pending invite, mention it
        elif agent_context.pending_invite:
            invite_section = self._build_invite_section(agent_context)
            return base_context + "\n" + invite_section
        # If nearby conversations (joinable or private), mention them
        elif agent_context.joinable_conversations or agent_context.private_conversations:
            nearby_section = self._build_nearby_conversations_section(agent_context)
            return base_context + "\n" + nearby_section + "\n---\n\nThis moment is yours.\n"
        else:
            return base_context + "\n---\n\nThis moment is yours.\n"

    def _build_conversation_section(self, ctx: AgentContext) -> str:
        """
        Build the conversation section for unified context.

        Philosophy: Describe the situation, end with "This moment is yours."
        No imperatives, no listing options - just present what's happening.
        """
        conv = ctx.conversation
        if conv is None:
            return ""

        other_participants = [p for p in conv.participants if p != ctx.agent.name]
        location = str(conv.location).replace("_", " ")
        unseen_history = ctx.unseen_history or []
        is_opener = ctx.is_opener

        parts = ["---\n"]

        if is_opener and unseen_history:
            # Opening: Someone approached and said something
            initiator = unseen_history[0]["speaker"]
            opening_narrative = unseen_history[0]["narrative"]
            parts.append(f"{initiator} is here with you.\n\n")
            parts.append(f"{opening_narrative}\n")
        else:
            # Ongoing conversation
            if len(other_participants) == 1:
                participants_str = other_participants[0]
            else:
                participants_str = ", ".join(other_participants[:-1]) + f" and {other_participants[-1]}"

            parts.append(f"You're in conversation with {participants_str} at the {location}.\n")

            # Add unseen turns
            if unseen_history:
                parts.append("\n")
                for turn in unseen_history:
                    speaker = turn["speaker"]
                    narrative = turn["narrative"]
                    parts.append(f"{speaker}:\n{narrative}\n\n--\n\n")

        parts.append("---\n\nThis moment is yours.")

        return "".join(parts)

    def _build_invite_section(self, ctx: AgentContext) -> str:
        """Build section for pending invitation."""
        invite = ctx.pending_invite
        if invite is None:
            return ""

        privacy = "private" if invite.privacy == "private" else "public"

        return f"""---

{invite.inviter} has invited you to a {privacy} conversation.

You can accept_invite or decline_invite.

---

This moment is yours.
"""

    def _build_nearby_conversations_section(self, ctx: AgentContext) -> str:
        """Build section for nearby conversations (joinable and private)."""
        lines = []

        # Joinable public conversations first
        if ctx.joinable_conversations:
            lines.append("There are public conversations happening here:")
            for conv in ctx.joinable_conversations:
                participants = " and ".join(sorted(conv.participants))
                lines.append(f"  - {participants}")
            lines.append("\nYou could join_conversation if you'd like to participate.")

        # Private conversations (awareness only)
        if ctx.private_conversations:
            if lines:
                lines.append("")  # Add spacing
            for conv in ctx.private_conversations:
                participants = sorted(conv.participants)
                if len(participants) == 2:
                    lines.append(f"{participants[0]} and {participants[1]} are speaking privately to each other.")
                else:
                    # For 3+ participants
                    all_but_last = ", ".join(participants[:-1])
                    lines.append(f"{all_but_last} and {participants[-1]} are speaking privately together.")

        return "\n".join(lines)
