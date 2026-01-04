"""Tests for ConversationRepository."""

import pytest

from core.types import AgentName, ConversationId, Position
from core.agent import Agent, AgentModel
from core.conversation import INVITE_EXPIRY_TICKS
from storage import Storage


# --- Helpers ---


async def create_test_agent(storage: Storage, name: str, position: Position = Position(0, 0)):
    """Create a test agent."""
    agent = Agent(
        name=AgentName(name),
        model=AgentModel(id="test-model", display_name="Test"),
        position=position,
    )
    await storage.agents.save_agent(agent)
    return agent


class TestConversationCRUD:
    """Test conversation CRUD operations."""

    async def test_create_conversation(self, storage: Storage):
        """Should create a conversation."""
        await create_test_agent(storage, "Ember")

        conv = await storage.conversations.create_conversation(
            created_by=AgentName("Ember"),
            privacy="public",
            tick=1,
        )

        assert conv.id is not None
        assert conv.privacy == "public"
        assert conv.created_by == AgentName("Ember")
        assert conv.started_at_tick == 1
        assert conv.ended_at_tick is None
        # Creator is automatically added as participant
        assert AgentName("Ember") in conv.participants

    async def test_get_conversation(self, storage: Storage):
        """Should retrieve conversation by ID."""
        await create_test_agent(storage, "Sage")

        conv = await storage.conversations.create_conversation(
            created_by=AgentName("Sage"),
            privacy="private",
            tick=5,
        )

        retrieved = await storage.conversations.get_conversation(conv.id)
        assert retrieved is not None
        assert retrieved.id == conv.id
        assert retrieved.privacy == "private"

    async def test_get_nonexistent_conversation(self, storage: Storage):
        """Should return None for unknown conversation."""
        conv = await storage.conversations.get_conversation(ConversationId("unknown"))
        assert conv is None

    async def test_end_conversation(self, storage: Storage):
        """Should mark conversation as ended."""
        await create_test_agent(storage, "Ember")

        conv = await storage.conversations.create_conversation(
            created_by=AgentName("Ember"),
            privacy="public",
            tick=1,
        )

        await storage.conversations.end_conversation(conv.id, tick=10)

        retrieved = await storage.conversations.get_conversation(conv.id)
        assert retrieved.ended_at_tick == 10


class TestConversationParticipants:
    """Test conversation participant operations."""

    async def test_add_participant(self, storage: Storage):
        """Should add participant to conversation."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "Sage")

        conv = await storage.conversations.create_conversation(
            created_by=AgentName("Ember"),
            privacy="public",
            tick=1,
        )

        # Ember already added as creator
        await storage.conversations.add_participant(
            conv.id, AgentName("Sage"), tick=2
        )

        retrieved = await storage.conversations.get_conversation(conv.id)
        assert AgentName("Ember") in retrieved.participants
        assert AgentName("Sage") in retrieved.participants

    async def test_remove_participant(self, storage: Storage):
        """Should remove participant from conversation."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "Sage")

        conv = await storage.conversations.create_conversation(
            created_by=AgentName("Ember"),
            privacy="public",
            tick=1,
        )
        await storage.conversations.add_participant(conv.id, AgentName("Sage"), tick=1)

        remaining = await storage.conversations.remove_participant(
            conv.id, AgentName("Sage"), tick=5
        )

        assert remaining == 1  # Only Ember left
        retrieved = await storage.conversations.get_conversation(conv.id)
        assert AgentName("Ember") in retrieved.participants
        assert AgentName("Sage") not in retrieved.participants

    async def test_get_conversation_for_agent(self, storage: Storage):
        """Should find active conversation for agent."""
        await create_test_agent(storage, "Ember")

        conv = await storage.conversations.create_conversation(
            created_by=AgentName("Ember"),
            privacy="public",
            tick=1,
        )

        found = await storage.conversations.get_conversation_for_agent(
            AgentName("Ember")
        )
        assert found is not None
        assert found.id == conv.id

    async def test_get_conversation_for_agent_not_in_any(self, storage: Storage):
        """Should return None if agent not in any conversation."""
        conv = await storage.conversations.get_conversation_for_agent(
            AgentName("Unknown")
        )
        assert conv is None

    async def test_get_conversation_for_agent_ignores_left(self, storage: Storage):
        """Should not return conversations agent has left."""
        await create_test_agent(storage, "Ember")

        conv = await storage.conversations.create_conversation(
            created_by=AgentName("Ember"),
            privacy="public",
            tick=1,
        )
        await storage.conversations.remove_participant(conv.id, AgentName("Ember"), tick=5)

        found = await storage.conversations.get_conversation_for_agent(
            AgentName("Ember")
        )
        assert found is None


class TestConversationTurns:
    """Test conversation turn operations."""

    async def test_add_turn(self, storage: Storage):
        """Should add turn to conversation."""
        await create_test_agent(storage, "Ember")

        conv = await storage.conversations.create_conversation(
            created_by=AgentName("Ember"),
            privacy="public",
            tick=1,
        )

        turn = await storage.conversations.add_turn(
            conv_id=conv.id,
            speaker=AgentName("Ember"),
            message="Hello!",
            tick=2,
        )

        assert turn.speaker == AgentName("Ember")
        assert turn.message == "Hello!"
        assert turn.tick == 2

    async def test_conversation_has_history(self, storage: Storage):
        """Should include turns in conversation history."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "Sage")

        conv = await storage.conversations.create_conversation(
            created_by=AgentName("Ember"),
            privacy="public",
            tick=1,
        )
        await storage.conversations.add_participant(conv.id, AgentName("Sage"), tick=1)

        await storage.conversations.add_turn(conv.id, AgentName("Ember"), "Hi!", 2)
        await storage.conversations.add_turn(conv.id, AgentName("Sage"), "Hello!", 3)

        retrieved = await storage.conversations.get_conversation(conv.id)
        assert len(retrieved.history) == 2
        assert retrieved.history[0].speaker == AgentName("Ember")
        assert retrieved.history[1].speaker == AgentName("Sage")

    async def test_get_turns_since(self, storage: Storage):
        """Should return turns since a given tick."""
        await create_test_agent(storage, "Ember")

        conv = await storage.conversations.create_conversation(
            created_by=AgentName("Ember"),
            privacy="public",
            tick=1,
        )

        await storage.conversations.add_turn(conv.id, AgentName("Ember"), "One", 2)
        await storage.conversations.add_turn(conv.id, AgentName("Ember"), "Two", 5)
        await storage.conversations.add_turn(conv.id, AgentName("Ember"), "Three", 8)

        turns = await storage.conversations.get_turns_since(conv.id, since_tick=4)
        assert len(turns) == 2
        assert turns[0].message == "Two"
        assert turns[1].message == "Three"

    async def test_get_turns_since_none_returns_all(self, storage: Storage):
        """Should return all turns when since_tick is None."""
        await create_test_agent(storage, "Ember")

        conv = await storage.conversations.create_conversation(
            created_by=AgentName("Ember"),
            privacy="public",
            tick=1,
        )

        await storage.conversations.add_turn(conv.id, AgentName("Ember"), "One", 2)
        await storage.conversations.add_turn(conv.id, AgentName("Ember"), "Two", 5)

        turns = await storage.conversations.get_turns_since(conv.id, since_tick=None)
        assert len(turns) == 2

    async def test_get_last_turn_tick(self, storage: Storage):
        """Should return last turn tick for agent."""
        await create_test_agent(storage, "Ember")

        conv = await storage.conversations.create_conversation(
            created_by=AgentName("Ember"),
            privacy="public",
            tick=1,
        )

        last_tick = await storage.conversations.get_last_turn_tick(
            conv.id, AgentName("Ember")
        )
        assert last_tick is None  # No turns yet

        # Update last turn tick
        await storage.conversations.update_last_turn_tick(
            conv.id, AgentName("Ember"), tick=5
        )

        last_tick = await storage.conversations.get_last_turn_tick(
            conv.id, AgentName("Ember")
        )
        assert last_tick == 5

    async def test_add_turn_updates_last_turn_tick(self, storage: Storage):
        """Adding a turn should update speaker's last_turn_tick."""
        await create_test_agent(storage, "Ember")

        conv = await storage.conversations.create_conversation(
            created_by=AgentName("Ember"),
            privacy="public",
            tick=1,
        )

        await storage.conversations.add_turn(conv.id, AgentName("Ember"), "Hi", tick=5)

        last_tick = await storage.conversations.get_last_turn_tick(
            conv.id, AgentName("Ember")
        )
        assert last_tick == 5


class TestInvitations:
    """Test invitation operations."""

    async def test_create_invitation(self, storage: Storage):
        """Should create an invitation."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "Sage")

        invite = await storage.conversations.create_invitation(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            privacy="public",
            tick=1,
        )

        assert invite.id is not None
        assert invite.inviter == AgentName("Ember")
        assert invite.invitee == AgentName("Sage")
        assert invite.privacy == "public"
        assert invite.created_at_tick == 1
        assert invite.expires_at_tick == 1 + INVITE_EXPIRY_TICKS

    async def test_get_pending_invitation(self, storage: Storage):
        """Should find pending invitation for agent."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "Sage")

        await storage.conversations.create_invitation(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            privacy="public",
            tick=1,
        )

        invite = await storage.conversations.get_pending_invitation(AgentName("Sage"))
        assert invite is not None
        assert invite.inviter == AgentName("Ember")

    async def test_get_pending_invitation_none(self, storage: Storage):
        """Should return None if no pending invitation."""
        invite = await storage.conversations.get_pending_invitation(
            AgentName("Unknown")
        )
        assert invite is None

    async def test_delete_invitation(self, storage: Storage):
        """Should delete invitation."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "Sage")

        invite = await storage.conversations.create_invitation(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            privacy="public",
            tick=1,
        )

        await storage.conversations.delete_invitation(invite.id)

        found = await storage.conversations.get_pending_invitation(AgentName("Sage"))
        assert found is None

    async def test_delete_invitations_for_invitee(self, storage: Storage):
        """Should delete all invitations for an agent."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "River")
        await create_test_agent(storage, "Sage")

        await storage.conversations.create_invitation(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            privacy="public",
            tick=1,
        )
        await storage.conversations.create_invitation(
            inviter=AgentName("River"),
            invitee=AgentName("Sage"),
            privacy="private",
            tick=2,
        )

        await storage.conversations.delete_invitations_for_invitee(AgentName("Sage"))

        found = await storage.conversations.get_pending_invitation(AgentName("Sage"))
        assert found is None

    async def test_get_expired_invitations(self, storage: Storage):
        """Should find expired invitations."""
        await create_test_agent(storage, "Ember")
        await create_test_agent(storage, "River")
        await create_test_agent(storage, "Sage")

        # Create invitation expiring at tick 3 (tick 1 + 2)
        await storage.conversations.create_invitation(
            inviter=AgentName("Ember"),
            invitee=AgentName("Sage"),
            privacy="public",
            tick=1,
        )

        # Create invitation expiring at tick 7 (tick 5 + 2)
        await storage.conversations.create_invitation(
            inviter=AgentName("River"),
            invitee=AgentName("Ember"),
            privacy="private",
            tick=5,
        )

        # At tick 4, only first should be expired (expires_at_tick <= 4)
        expired = await storage.conversations.get_expired_invitations(current_tick=4)
        assert len(expired) == 1
        assert expired[0].invitee == AgentName("Sage")

        # At tick 10, both should be expired
        expired = await storage.conversations.get_expired_invitations(current_tick=10)
        assert len(expired) == 2
