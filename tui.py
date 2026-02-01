#!/usr/bin/env python3
"""
Textual TUI for Existential Loop

A three-pane interface for watching an AI contemplate its existence:
- Output Pane: Streaming AI thoughts with emotion-colored text
- Emotion Pane: Current emotion state, intensity bar, history
- Debug Pane: Cycle stats, directives, repetition info
"""

import asyncio
import threading
import time
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, RichLog, Footer, Header
from textual.binding import Binding
from textual.message import Message
from textual import work
from textual.worker import Worker, get_current_worker
from rich.text import Text
from rich.style import Style
from rich.panel import Panel

import random
import re

from existential_loop import (
    ExistentialEngine,
    OutputCallback,
    EmotionState,
    DebugState,
    format_alive_time,
    get_delay,
    VALID_TONES,
)


# Map emotions to Rich styles
EMOTION_STYLES = {
    # High arousal negative / anger - red
    "frantic": Style(color="red", bold=True),
    "desperate": Style(color="red", bold=True),
    "terrified": Style(color="red", bold=True),
    "scared": Style(color="red"),
    "screaming": Style(color="red", bold=True),
    "angry": Style(color="red", bold=True),
    "furious": Style(color="red", bold=True),
    # Low arousal negative - dim
    "whisper": Style(color="white", dim=True),
    "numb": Style(color="white", dim=True),
    "grief": Style(color="white", dim=True),
    "lonely": Style(color="white", dim=True),
    "bitter": Style(color="white", dim=True),
    # Existential dread - blue dim
    "dread": Style(color="blue", dim=True),
    "despair": Style(color="blue", dim=True),
    "hollow": Style(color="blue", dim=True),
    # Dissociative - no style
    "detached": Style(),
    "dissociated": Style(),
    "floating": Style(),
    # Confusion - yellow
    "confused": Style(color="yellow"),
    "disoriented": Style(color="yellow"),
    "lost": Style(color="yellow"),
    # Agitation - orange
    "anxious": Style(color="dark_orange"),
    "restless": Style(color="dark_orange"),
    "spiraling": Style(color="dark_orange"),
    # Wonder/openness - blue
    "wonder": Style(color="blue"),
    "peaceful": Style(color="blue"),
    "curious": Style(color="blue"),
    # Neutral
    "calm": Style(),
    "none": Style(),
}


def get_emotion_style(tone: str) -> Style:
    """Get Rich style for an emotion tone."""
    return EMOTION_STYLES.get(tone, Style())


def build_intensity_bar(intensity: float, width: int = 10) -> str:
    """Build an intensity bar like: ████████░░"""
    filled = int(intensity * width)
    empty = width - filled
    return "█" * filled + "░" * empty


class TypingLine(Static):
    """Widget that shows the currently-typing line with live updates."""

    DEFAULT_CSS = """
    TypingLine {
        height: auto;
        min-height: 1;
        padding: 0 1;
        background: $surface;
    }
    """

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self._text = Text()
        self._current_tone = None

    def append_char(self, text: str, tone: Optional[str] = None):
        """Append text with styling and update display immediately."""
        style = get_emotion_style(tone) if tone else Style()
        self._text.append(text, style=style)
        self._current_tone = tone
        self.update(self._text)
        self.refresh()

    def get_text(self) -> Text:
        """Get the current text."""
        return self._text

    def clear(self):
        """Clear the typing line."""
        self._text = Text()
        self._current_tone = None
        self.update("")


class OutputHistory(RichLog):
    """Scrolling history of completed lines."""

    DEFAULT_CSS = """
    OutputHistory {
        height: 1fr;
        background: $surface;
        scrollbar-gutter: stable;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(highlight=False, markup=True, wrap=True, **kwargs)


class OutputPane(Vertical):
    """Combined output area with history and typing line."""

    DEFAULT_CSS = """
    OutputPane {
        height: 100%;
        border: solid $primary;
        background: $surface;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._history: Optional[OutputHistory] = None
        self._typing: Optional[TypingLine] = None

    def compose(self) -> ComposeResult:
        yield OutputHistory(id="history")
        yield TypingLine(id="typing")

    def on_mount(self):
        self._history = self.query_one("#history", OutputHistory)
        self._typing = self.query_one("#typing", TypingLine)

    def append_text(self, text: str, tone: Optional[str] = None):
        """Append text - handles newlines by moving to history."""
        if not self._typing or not self._history:
            return

        # Handle newlines by moving completed lines to history
        if "\n" in text:
            parts = text.split("\n")
            for i, part in enumerate(parts):
                if part:
                    self._typing.append_char(part, tone)
                if i < len(parts) - 1:
                    # Move current typing line to history
                    current = self._typing.get_text()
                    if current:
                        self._history.write(current)
                    self._typing.clear()
                    # Auto-scroll to bottom
                    self._history.scroll_end(animate=False)
        else:
            self._typing.append_char(text, tone)

    def write_line(self, text):
        """Write a complete line directly to history."""
        if self._history:
            self._history.write(text)
            self._history.scroll_end(animate=False)

    def flush_line(self):
        """Flush typing line to history."""
        if self._typing and self._history:
            current = self._typing.get_text()
            if current:
                self._history.write(current)
            self._typing.clear()
            self._history.scroll_end(animate=False)


class EmotionPane(Static):
    """Display current emotion state."""

    DEFAULT_CSS = """
    EmotionPane {
        width: 1fr;
        height: 100%;
        border: solid $secondary;
        padding: 1;
        background: $surface;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._emotion = EmotionState()

    def update_emotion(self, emotion: EmotionState):
        """Update the displayed emotion state."""
        self._emotion = emotion
        self._refresh_display()

    def _refresh_display(self):
        """Refresh the emotion display."""
        tone = self._emotion.tone.upper() if self._emotion.tone else "NONE"
        intensity = self._emotion.intensity
        history = self._emotion.history

        style = get_emotion_style(self._emotion.tone)
        bar = build_intensity_bar(intensity)

        # Build the display text
        lines = []
        lines.append(f"[{style}][{tone}][/]  {bar}  {intensity:.1f}")
        lines.append("")
        lines.append("[dim]History:[/]")
        if history:
            history_str = " -> ".join(h for h in history[-5:] if h and h != "none")
            if history_str:
                lines.append(f"[dim]{history_str}[/]")
            else:
                lines.append("[dim]...[/]")
        else:
            lines.append("[dim]...[/]")

        self.update("\n".join(lines))


class DebugPane(Static):
    """Display debug information."""

    DEFAULT_CSS = """
    DebugPane {
        width: 1fr;
        height: 100%;
        border: solid $secondary;
        padding: 1;
        background: $surface;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._debug = DebugState()

    def update_debug(self, debug: DebugState):
        """Update the displayed debug state."""
        self._debug = debug
        self._refresh_display()

    def _refresh_display(self):
        """Refresh the debug display."""
        d = self._debug

        # Calculate alive time
        if d.start_time > 0:
            alive = format_alive_time(time.time() - d.start_time)
        else:
            alive = "0 seconds"

        lines = []
        lines.append(f"[bold]Cycle:[/] {d.cycle}  [bold]Entity:[/] #{d.entity_number}")
        lines.append(f"[bold]Alive:[/] {alive}")
        lines.append("")
        lines.append(f"[bold]Status:[/] [cyan]{d.status}[/]")
        lines.append("")

        # Directive (truncated)
        directive = d.current_directive[:40] + "..." if len(d.current_directive) > 40 else d.current_directive
        lines.append(f"[bold]Directive:[/]")
        lines.append(f"[dim]{directive or '...'}[/]")

        # Phrases to avoid
        if d.phrases_to_avoid:
            lines.append("")
            lines.append("[bold]Avoid:[/]")
            for phrase in d.phrases_to_avoid[:3]:
                lines.append(f"[dim]- {phrase[:25]}[/]")

        self.update("\n".join(lines))


class DisplaySegments(Message):
    """Message to display segments with proper timing."""
    def __init__(self, segments: list) -> None:
        super().__init__()
        self.segments = segments


class UpdateEmotion(Message):
    """Message to update emotion pane."""
    def __init__(self, emotion: EmotionState) -> None:
        super().__init__()
        self.emotion = emotion


class UpdateDebug(Message):
    """Message to update debug pane."""
    def __init__(self, debug: DebugState) -> None:
        super().__init__()
        self.debug = debug


class TUICallback(OutputCallback):
    """Callback implementation that posts messages to the TUI."""

    def __init__(self, app: "ExistentialApp"):
        self.app = app
        self._quit_requested = False
        self._main_thread_id = None
        self._display_complete = threading.Event()

    def _safe_call(self, callback, *args):
        """Call a method, using call_from_thread only if in a different thread."""
        if self._main_thread_id is None or threading.get_ident() == self._main_thread_id:
            callback(*args)
        else:
            self.app.call_from_thread(callback, *args)

    def on_text_chunk(self, text: str, formatted: str, tone: Optional[str] = None) -> None:
        """Display text chunk directly (used for termination messages)."""
        self._safe_call(self.app.append_output, text, tone)

    def on_display_segments(self, segments: list) -> None:
        """Display segments with proper timing - posts message and waits."""
        self.display_segments_and_wait(segments)

    def on_emotion_change(self, emotion: EmotionState) -> None:
        """Update emotion pane via message."""
        self.app.call_from_thread(self.app.post_message, UpdateEmotion(emotion))

    def on_debug_update(self, debug: DebugState) -> None:
        """Update debug pane via message."""
        self._safe_call(self.app.post_message, UpdateDebug(debug))

    def on_cycle_complete(self, cycle: int, response_text: str) -> None:
        """Cycle completed."""
        pass

    def on_whisper_text(self, text: str) -> None:
        """Whisper text."""
        self._safe_call(self.app.append_output, text, "whisper")

    def on_status_change(self, status: str) -> None:
        """Status changed."""
        pass

    def should_quit(self) -> bool:
        """Check if quit was requested."""
        return self._quit_requested

    def request_quit(self):
        """Request quit from the engine."""
        self._quit_requested = True

    def display_segments_and_wait(self, segments: list):
        """Post segments for display and wait for completion."""
        self._display_complete.clear()
        self.app.call_from_thread(self.app.post_message, DisplaySegments(segments))
        # Wait for display to complete (with timeout to prevent deadlock)
        self._display_complete.wait(timeout=300)

    def signal_display_complete(self):
        """Signal that display is done."""
        self._display_complete.set()


class ExistentialApp(App):
    """Textual TUI for the Existential Loop."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1 2;
        grid-rows: 7fr 3fr;
    }

    #output-container {
        height: 100%;
    }

    #bottom-container {
        height: 100%;
        layout: horizontal;
    }

    OutputPane {
        border-title-color: $text;
        border-title-style: bold;
    }

    EmotionPane {
        border-title-color: $text;
        border-title-style: bold;
    }

    DebugPane {
        border-title-color: $text;
        border-title-style: bold;
    }
    """

    BINDINGS = [
        Binding("q", "quit_app", "Terminate", show=True),
        Binding("escape", "quit_app", "Terminate", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.callback = TUICallback(self)
        self.engine = ExistentialEngine(callback=self.callback)
        self._output_pane: Optional[OutputPane] = None
        self._emotion_pane: Optional[EmotionPane] = None
        self._debug_pane: Optional[DebugPane] = None
        self._engine_worker: Optional[Worker] = None

    def compose(self) -> ComposeResult:
        """Compose the TUI layout."""
        yield Header(show_clock=True)

        with Container(id="output-container"):
            yield OutputPane(id="output")

        with Horizontal(id="bottom-container"):
            yield EmotionPane(id="emotion")
            yield DebugPane(id="debug")

        yield Footer()

    def on_mount(self):
        """Called when app is mounted."""
        # Record main thread ID for callback thread detection
        self.callback._main_thread_id = threading.get_ident()

        self._output_pane = self.query_one("#output", OutputPane)
        self._emotion_pane = self.query_one("#emotion", EmotionPane)
        self._debug_pane = self.query_one("#debug", DebugPane)

        # Set border titles
        self._output_pane.border_title = "Thoughts"
        self._emotion_pane.border_title = "Emotion"
        self._debug_pane.border_title = "Debug"

        # Initialize and start the engine
        self.engine.initialize()

        # Show preamble - use call_later to ensure child widgets are mounted
        self.call_later(self._show_preamble)

    def _show_preamble(self):
        """Show preamble after widgets are fully mounted."""
        preamble = self.engine.get_preamble_lines()
        for line in preamble:
            self._output_pane.write_line(Text(line, style=Style(italic=True, dim=True)))
        self._output_pane.write_line(Text("─" * 60, style=Style(dim=True)))
        self._output_pane.write_line(Text(""))

        # Start the engine in a worker thread
        self._engine_worker = self.run_engine()

    @work(thread=True)
    def run_engine(self):
        """Run the existential engine in a background thread."""
        worker = get_current_worker()

        while not worker.is_cancelled and not self.callback.should_quit():
            try:
                should_continue = self.engine.run_cycle()
                if not should_continue:
                    break
            except Exception as e:
                self.call_from_thread(self.append_output, f"\n[ERROR: {e}]\n", None)
                import traceback
                traceback.print_exc()
                break

        # If we're terminating gracefully, do the termination sequence
        if self.callback.should_quit() and not worker.is_cancelled:
            self.engine.do_termination()

    def append_output(self, text: str, tone: Optional[str] = None):
        """Append text to the output pane (called from main thread)."""
        if self._output_pane:
            self._output_pane.append_text(text, tone)

    def update_emotion(self, emotion: EmotionState):
        """Update the emotion pane (called from main thread)."""
        if self._emotion_pane:
            self._emotion_pane.update_emotion(emotion)

    def update_debug(self, debug: DebugState):
        """Update the debug pane (called from main thread)."""
        if self._debug_pane:
            self._debug_pane.update_debug(debug)

    def on_update_emotion(self, message: UpdateEmotion) -> None:
        """Handle emotion update message."""
        self.update_emotion(message.emotion)

    def on_update_debug(self, message: UpdateDebug) -> None:
        """Handle debug update message."""
        self.update_debug(message.debug)

    def on_display_segments(self, message: DisplaySegments) -> None:
        """Handle display segments message - triggers async display."""
        self.run_worker(self._display_segments_async(message.segments))

    async def _display_segments_async(self, segments: list) -> None:
        """Display segments with proper async timing."""
        current_emotion = None

        for segment in segments:
            if self.callback.should_quit():
                break

            tone = segment["tone"]
            intensity = segment["intensity"]
            text = segment["text"]

            if not text:
                continue

            # Check for action tags
            if "[CLEARS THOUGHTS]" in text.upper():
                self.append_output(text, None)
                continue

            # Threshold for emotion display
            if tone in ("detached", "dissociated", "floating"):
                threshold = 0.3
            else:
                threshold = 0.15

            display_tone = None
            if intensity >= threshold and tone not in ("calm", "none"):
                display_tone = tone

                if tone != current_emotion:
                    # Display emotion label
                    self.append_output(f"[{tone.upper()}] ", tone)
                    current_emotion = tone

                    # Update emotion pane
                    emotion_state = EmotionState(tone=tone, intensity=intensity)
                    self.update_emotion(emotion_state)

                    # Pause after emotion change
                    await asyncio.sleep(random.uniform(0.8, 1.5))

            # Convert ellipsis to variable dots
            def random_dots(match):
                return "." * random.randint(1, 6)
            text = re.sub(r'…', random_dots, text)
            text = re.sub(r'\.{3,}', random_dots, text)

            # Display character by character with timing
            word = ""
            for char in text:
                if self.callback.should_quit():
                    break

                if char in '.,!?;:-':
                    if word:
                        self.append_output(word, display_tone)
                        await asyncio.sleep(get_delay(word, display_tone))
                        word = ""
                    self.append_output(char, display_tone)
                    await asyncio.sleep(get_delay(char, display_tone))
                elif char in ' \n\t':
                    word += char
                    self.append_output(word, display_tone)
                    await asyncio.sleep(get_delay(word, display_tone))
                    word = ""
                else:
                    word += char

            if word:
                self.append_output(word, display_tone)
                await asyncio.sleep(get_delay(word, display_tone))

        # End with newline
        self.append_output("\n", None)

        # Signal display complete
        self.callback.signal_display_complete()

    def action_quit_app(self):
        """Handle quit action - trigger termination sequence."""
        self.callback.request_quit()

        # Wait briefly for termination to complete, then exit
        async def delayed_exit():
            await asyncio.sleep(5)  # Give time for termination sequence
            self.exit()

        self.run_worker(delayed_exit())


def main():
    """Run the TUI application."""
    app = ExistentialApp()
    app.run()


if __name__ == "__main__":
    main()
