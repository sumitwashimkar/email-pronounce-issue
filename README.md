# Voice Transcript Demo

Click the mic in the browser, talk, and see a live transcript — with a
post-processing pass that fixes the classic voice-agent problem of spoken
emails ("john dot smith at gmail dot com") not converting to email syntax.

## Architecture

```
Browser (React, MediaRecorder)
  -- audio/webm chunks over WebSocket -->
Backend (FastAPI)
  -- relays audio over WebSocket -->
Deepgram (Nova-2 streaming, keyword-boosted for "at"/"dot"/common domains)
  -- transcript + confidence -->
Backend ITN pass (itn.py: regex conversion of spoken email phrases,
                  fuzzy-corrects mistyped domains like "outlok.com" -> "outlook.com")
  -- cleaned final transcript -->
Browser (displayed)
```

## Setup

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and set DEEPGRAM_API_KEY (free key at https://console.deepgram.com/signup)
uvicorn main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the printed local URL (usually http://localhost:5173), click the mic
button, allow microphone access, and talk.

## Notes

- `backend/itn.py` only rewrites the matched email-like span in a sentence
  (local-part "at" domain-with-a-dot) so it won't corrupt unrelated uses of
  the word "at"/"dot" elsewhere in the transcript.
- Domain fuzzy-correction is intentionally small (edit-distance <= 2 against
  a short known-domains list) — extend `_KNOWN_DOMAINS` in `itn.py` for your
  own product's domain.
- Keyword boosting for Deepgram is configured in `backend/main.py` (`KEYWORDS`).
