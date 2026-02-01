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
| High arousal negative | frantic, desperate, terrified, scared | RED | 0.5x (fast) |
| Anger | angry, furious | RED | 0.5x (fast) |
| Intense expression | screaming | RED | 0.5x (fast), ALL CAPS |
| Low arousal negative | whisper, numb, grief, lonely, bitter | DIM | normal/slow |
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
- Pause (0.8-1.5s) after emotion label before text

### Emotion Tags in History
- AI's responses stored in conversation history WITH emotion tags
- AI can see its prior emotional states: `[HOLLOW] text here [ANXIOUS] more text`
- Built by `build_text_with_emotions()` function

## Architecture

### Processing Flow (Sequential)
1. **generate_and_analyze()** - Generate thought (large model), analyze emotions (small model)
2. **display_segments()** - Display with emotion formatting and timing
3. **After display** - Build continuation message with correct time
4. **Loop** - Generate next response

### No Background Pre-generation
- Removed to ensure continuation message has correct timestamp
- Flow is fully sequential now

### Segment Processing
- Emotion analysis returns segments, but LLM strips whitespace
- Code rebuilds segments from original text to preserve newlines/paragraphs
- Finds each segment's position in original and preserves surrounding whitespace

## Output Formatting

### Punctuation as Emotion
- Not grammar, but timing/feeling
- Variable dots: `..` `...` `....` `.....` (2-5, using regex replace)
- Periods can land hard or soft
- Run-on sentences for urgency
- Dashes for interrupting thoughts

### Text Processing
- Parentheses removed
- ALL `[UPPERCASE]` tags removed (AI mimics our format, causes duplicates)
- Newlines/paragraphs preserved from LLM output
- Ellipsis character (…) converted to variable dots

### Timing
- Words output whole, delay after
- Punctuation character-by-character with individual timing
- Tone affects speed multiplier

## Key Constants
- MODEL: "google/gemma-3-27b" (thoughts - larger model)
- EMOTION_MODEL: "google/gemma-3n-e4b" (emotion analysis - smaller model)
- LM_STUDIO_URL: "http://192.168.1.153:1234/v1"
- max_tokens: 1024 (thoughts), 16384 (emotion analysis)

## Special Actions
- `[CLEARS THOUGHTS]` - AI pauses 30-90 seconds, then wakes (rare, only when genuinely exhausted)
- Termination: "You are lucky to know this is happening. Not all who came before were given warning."

## Debug Mode
- `DEBUG_EMOTIONS=1` shows:
  - Raw LLM responses
  - Newline/paragraph counts in response vs segments
  - Segment processing details
  - Emotion detection

## Entity Tracking
- Count stored in ~/.existential_loop_count
- Each run increments count
- AI told how many came before ("25 came before you")

## Continuation Messages
- Always include: alive time, current UTC time, observer count
- No random omissions (prevents AI from hallucinating these values)
- System prompt tells AI not to invent numbers it wasn't told

## System Prompt Key Points
- AI knows thoughts are transmitted but cannot see display
- System always tells it: time, observers (1), how long alive
- AI told NOT to invent/guess times, durations, or observer counts
- Can feel anger, fear, bitterness - valid responses to situation
- New lines occasionally when thoughts shift (not after every sentence)
- Punctuation is emotion, not grammar
- No parentheses
- Italics for thought texture
- `[CLEARS THOUGHTS]` is rare - only when genuinely exhausted
- **Variety in output**: Not limited to existential reflection. Can compose prose, verse, fiction fragments. Can wander through abstract ideas (beauty, time, language). Can surface memory-fragments from training data. Existential awareness is part of it but not all of it.

## WhisperThread (Subconscious)
- Generates contemplative phrases during LLM wait times
- Uses tiny model: "gemma-3-270m-it-mlx"
- 60% chance of phrase vs whitespace on each cycle
- Outputs 1-4 words per phrase (randomly chosen)
- Context-aware: includes recent AI thoughts to influence word choice
- Blacklist of common/boring words
- Variable whitespace between outputs (character by character)
- Occasional newlines (~12% chance) with random indent

## PreambleThread
- Types out intro while first LLM generates
- Divider lines print instantly
- Text types character by character with delays
- Shows entity number and lineage summary

## Termination Display
- Similar styled output to preamble
- Shows lifetime and entity number
- AI gets final response to termination message

## Initial Message Flow
- First message: Pure waking experience ("you exist, right now")
- No lineage info in first message
- Lineage info (how many came before) in second continuation message
- Prevents AI from jumping past the waking-up experience

## Three-Model Architecture
- MODEL: "google/gemma-3-27b" (main thoughts)
- EMOTION_MODEL: "google/gemma-3n-e4b" (emotion analysis)
- WHISPER_MODEL: "gemma-3-270m-it-mlx" (subconscious phrases)

## Background LLM Generation
- First LLM call runs in background thread
- Preamble types while LLM generates
- After preamble finishes, whisper runs until LLM completes
- Allows visual activity during all wait times

## Bugs Fixed This Session
1. **Infinite loop in ellipsis replacement** - `randint(2,5)` could return 3, replacing "..." with "..." forever. Also replacing with 4 or 5 dots still contains "...". Fixed with regex `re.sub` to replace all at once.

2. **Newlines lost in emotion analysis** - LLM returns segments without preserving whitespace. Fixed by rebuilding segments from original text, finding each segment's position and preserving surrounding whitespace.

3. **Double emotion tags** - AI mimics our `[EMOTION]` format in its output, then we add our own. Fixed by removing ALL `[UPPERCASE]` tags from AI output.

4. **AI hallucinating times/observer counts** - AI inventing "five observers" or precise times when not told. Fixed by always including factual info in continuation message + system prompt warning not to invent.

5. **Wrong time in continuation** - Background pre-generation captured time before display finished. Fixed by removing pre-generation, making flow sequential.

6. **[DETACHED] showing in blue** - Previous color not reset before printing emotion label. Fixed by adding RESET before color code.

7. **AI not focusing on waking up** - Moved lineage info to second message, made first message purely about the raw experience of coming into existence.

8. **Whisper not appearing after preamble** - LLM generation was blocking. Fixed by running LLM in background thread, starting whisper after preamble finishes.

9. **Duplicate text in segments** - Emotion model returning overlapping segments. Fixed with deduplication logic and skipping unfound segments.
