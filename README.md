# Voice Transcript Demo

## The Problem

When people speak to a voice AI agent, some things are hard for speech-to-text
(STT) to get right — especially **email addresses** and **brand names**.

For example, if a user says their email out loud:

> "john dot smith at gmail dot com"

A normal STT engine writes down exactly what it heard — the *words*:

> `john dot smith at gmail dot com`

But what we actually want is the real email:

> `john.smith@gmail.com`

The same thing happens with:
- People pronouncing **"@" as "at"**, so it never becomes the `@` symbol.
- **Domain names** getting misheard (e.g. "gmail" heard as "redgmail").
- **Product / brand names** the STT has never seen (e.g. "vibetree" heard as
  "wip3" or "vip tree").

This demo picks one STT engine (Deepgram), reproduces these problems, and fixes
them.

## The Approach

No single STT engine solves this perfectly on its own — so the fix is built in
**layers**, each catching a different part of the problem:

1. **Tell the STT what to expect (before it listens).**
   Deepgram supports "keyterm normalisation" — we give it a list of words it should
   expect (`at`, `dot`, common domains, and brand names like `vibetree`). This
   makes it recognise those words correctly instead of guessing a wrong one.

2. **Clean up the text (after it listens).**
   A small rule-based step (`itn.py`) takes the raw transcript and:
   - turns spoken words into symbols → "at" becomes `@`, "dot" becomes `.`
   - only does this when it clearly looks like an email, so normal sentences
     ("meet me at the office") are left untouched.
   - fixes slightly-misheard known domains → "outlok.com" becomes `outlook.com`,
     "redgmail.com" becomes `gmail.com`.

So the STT gets a hint up front, and the transcript gets polished afterward.

### Simple Architecture

```
   You speak into the mic
            │
            ▼
   Browser (React)  ──── streams audio ────►  Backend (FastAPI)
   • mic button                                • relays audio to Deepgram
   • shows transcript ◄──── clean text ─────   • cleans up the result
            ▲                                         │
            │                                         ▼
            │                                   Deepgram STT
            │                                   • listens (with hints)
            └──────── final transcript ◄─────── • returns the text
```

- **Browser** — captures your voice and shows the live transcript.
- **Backend** — passes audio to Deepgram, then runs the clean-up step on the
  result before sending it back.
- **Deepgram** — the actual speech-to-text engine.

## How to Run

You'll need a free Deepgram API key (get one at
https://console.deepgram.com/signup — it comes with free credits).

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# open .env and paste your key:  DEEPGRAM_API_KEY=your_key_here
uvicorn main:app --reload
```

### 2. Frontend (in a second terminal)

```bash
cd frontend
npm install
npm run dev
```

Open the URL it prints (usually http://localhost:5173), click the mic button,
allow microphone access, and start talking.
