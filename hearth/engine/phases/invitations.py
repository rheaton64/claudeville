"""Invitation expiry phase for Hearth engine.

Expires conversation invitations that have passed their expiry tick.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from core.constants import HEARTH_TZ
from core.events import InvitationExpiredEvent
from ..context import TickContext

if TYPE_CHECKING:
    from services.conversation import ConversationService


class InvitationExpiryPhase:
    """Phase that expires old conversation invitations.

    Runs at the start of each tick to clean up invitations that
    have passed their expiry tick without a response.
    """

    def __init__(self, conversation_service: "ConversationService"):
        """Initialize phase.

        Args:
            conversation_service: ConversationService for expiring invitations
        """
        self._conversation = conversation_service

    async def execute(self, ctx: TickContext) -> TickContext:
        """Expire old invitations.

        Args:
            ctx: Current tick context

        Returns:
            Context with expiration events appended
        """
        # Expire invitations
        expired = await self._conversation.expire_invitations(ctx.tick)

        if not expired:
            return ctx

        # Create events for each expired invitation
        events = []
        for invite in expired:
            events.append(
                InvitationExpiredEvent(
                    tick=ctx.tick,
                    timestamp=datetime.now(HEARTH_TZ),
                    inviter=invite.inviter,
                    invitee=invite.invitee,
                )
            )

        return ctx.append_events(events)
