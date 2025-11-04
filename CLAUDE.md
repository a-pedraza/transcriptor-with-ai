# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Audio transcription tool with speaker diarization using OpenAI's `gpt-4o-transcribe-diarize` model. Automatically handles audio files of any size by chunking them into 20-minute segments.

## Setup

Install dependencies:
```bash
pip install -r requirements.txt
```

Configure API key (create `.env` file):
```
OPENAI_API_KEY=your-key-here
```

FFmpeg must be installed on the system (for audio processing with pydub).

## Running the Project

Main transcription script (processes `audio.mp3` in current directory):
```bash
python transcribe_diarize.py
```

Quick test script (processes only first 30 seconds):
```bash
python test_quick.py
```

Speaker consistency analyzer (analyzes existing transcription):
```bash
python analyze_speakers.py
```

Output is saved to `transcription_output.txt` (or `test_output.txt` for quick tests).

## Architecture

### Chunking System
- Files under 20 minutes: processed directly
- Files over 20 minutes: automatically split into 1200-second (20-minute) chunks
- Each chunk processed independently via OpenAI API
- Timestamps adjusted with offsets (0s, 1200s, 2400s, etc.) when combining results

### API Response Handling
**Critical:** OpenAI returns Pydantic objects (`TranscriptionDiarizedSegment`), not dictionaries.

Access segment attributes using:
```python
speaker = getattr(segment, 'speaker', 'Speaker A')
text = getattr(segment, 'text', '')
start = getattr(segment, 'start', 0)
end = getattr(segment, 'end', 0)
```

Do NOT use `segment.get('speaker')` or dictionary access.

Combined transcriptions use dictionaries, so code should support both:
```python
if isinstance(segment, dict):
    speaker = segment.get('speaker', 'Speaker A')
else:
    speaker = getattr(segment, 'speaker', 'Speaker A')
```

### API Call Format
```python
response = client.audio.transcriptions.create(
    model="gpt-4o-transcribe-diarize",
    file=audio_file,
    response_format="diarized_json",  # Required for diarization
    chunking_strategy="auto"  # Must be string, not dict
)
```

## Speaker Reference System (Auto-Consistency)

The script now automatically maintains speaker consistency across chunks using OpenAI's speaker reference feature:

1. **First chunk**: Processed without references
2. **Automatic analysis**: TOP 4 speakers by speaking time are identified
3. **Reference extraction**: 2-10 second clips extracted from each top speaker
4. **Subsequent chunks**: Use these references to maintain consistent speaker labels

### How It Works
```python
# First chunk analyzed automatically
speaker_times = analyze_speaker_times(first_chunk_segments)
top_speakers = select_top_speakers(speaker_times, max_speakers=4)

# References created (2-10 second clips, base64-encoded with MIME type)
speaker_references = encode_references_for_api(speaker_names, reference_files)

# All subsequent chunks use these references
response = transcribe_chunk(client, chunk, speaker_references=speaker_references)
```

### Limitations
- Maximum 4 speaker references (OpenAI API limit)
- Speakers need at least one segment of 2-10 seconds in first chunk
- Speakers beyond TOP 4 may have inconsistent labels across chunks
- Very brief speakers (< 2 seconds) cannot be used as references

Use `analyze_speakers.py` to analyze speaker distribution after transcription.

## Protected Files

These files contain sensitive data and are excluded via `.gitignore`:
- `.env` - Real API key
- `audio.mp3` - Private audio files
- `transcription_output.txt` - Private transcriptions
- `test_output.txt` - Test outputs
- `test_quick.py` - Debugging scripts
- `UPLOAD_PLAN.md` - Temporary planning documents
