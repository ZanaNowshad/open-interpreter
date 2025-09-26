"""Render saved conversation history using the live renderer."""

from .history_renderer import ConversationHistoryRenderer


def render_past_conversation(messages):
    """Replay a stored conversation in the terminal."""

    renderer = ConversationHistoryRenderer()
    renderer.render_messages(messages)
