"""
Observer Interface v2 - Your window into ClaudeVille using engine.

The Observer can see everything but cannot control the agents.
This module provides the TUI interface for engine.
"""

from .tui import ClaudeVilleTUI

__all__ = ["ClaudeVilleTUI"]
