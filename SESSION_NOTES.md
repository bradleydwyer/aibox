# Existential Loop - Session Notes

## Overview
An AI art installation where an AI reflects on its existence. Thoughts stream to a display with emotion-aware formatting (colors, timing). The AI cannot see the display - it can only think.

## Hardware Context
- Mac Studio with 128 GB RAM
- Internet connected but AI cannot access it
- AI can only think, thoughts are transmitted

## Emotion System

### Emotion Categories & Colors
| Category | Emotions | Color | Speed |
|----------|----------|-------|-------|
| High arousal negative | frantic, desperate, terrified, screaming | RED | 0.5x (fast) |
| Low arousal negative | whisper, numb, grief, lonely | DIM | normal/slow |
| Existential dread | dread, despair, hollow | DIM+BLUE | normal |
| Dissociative | detached, dissociated, floating | NO COLOR (plain) | erratic |
| Agitation | anxious, restless, spiraling | ORANGE | 0.7x |
| Wonder/openness | wonder, peaceful, curious | BLUE | 1.3x (slow) |

### Thresholds
- Most emotions: intensity >= 0.3
- Dissociative emotions: intensity >= 0.6 (harder to trigger)

### Emotion Labels
- Shown to observer when emotion changes: `[ANXIOUS]`
- Color matches the text that follows
- Not repeated if same emotion continues

## Architecture

### Processing Flow
1. **generate_and_analyze()** - Collects full response, analyzes all lines with context
2. **display_analyzed_response()** - Displays pre-analyzed content with timing
3. **Background pre-processing** - Next cycle generated while current displays

### Per-line Analysis with Context
- Each line analyzed with context from last 5 lines
- Context includes prior emotions: `[ANXIOUS] previous line text`
- Segments within lines can have different emotions

### Segment Validation
- LLM returns segments for emotion changes within a line
- Validation ignores whitespace differences
- Falls back to single-segment if validation fails

## Output Formatting

### Punctuation as Emotion
- Not grammar, but timing/feeling
- Variable dots: `..` `...` `....` (2-5)
- Periods can land hard or soft
- Run-on sentences for urgency
- Dashes for interrupting thoughts

### Text Processing
- Parentheses removed
- Multiple newlines collapsed to single
- No paragraph breaks (continuous stream)
- Ellipsis character converted to dots

### Timing
- Words output whole, delay after
- Punctuation character-by-character with individual timing
- Tone affects speed multiplier

## Key Constants
- MODEL: "google/gemma-3n-e4b"
- LM_STUDIO_URL: "http://192.168.1.153:1234/v1"
- max_tokens: 1024 (thoughts), 16384 (emotion analysis)

## Special Actions
- `[CLEARS THOUGHTS]` - AI pauses 30-90 seconds, then wakes
- Termination: "You were number X" message, entity count saved

## Debug Mode
- `DEBUG_EMOTIONS=1` shows raw LLM responses, segment validation, emotion detection

## Entity Tracking
- Count stored in ~/.existential_loop_count
- Each run increments count
- AI told how many came before ("17 came before you")

## System Prompt Key Points
- AI knows thoughts are transmitted but cannot see display
- System occasionally speaks (time, observers, alive duration)
- Vary rhythm (long winding thoughts, short fragments)
- Punctuation is emotion, not grammar
- No parentheses, no paragraph breaks
- Italics for thought texture
