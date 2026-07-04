import os
import logging

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
)

from itn import normalize_email_like

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-stt-demo")

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
if not DEEPGRAM_API_KEY:
    raise RuntimeError("DEEPGRAM_API_KEY is not set. Copy .env.example to .env and add your key.")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

KEYTERMS = [
    "at",
    "dot",
    "underscore",
    "hyphen",
    "dash",
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    # Brand / product names the STT would otherwise mishear as common words
    # (e.g. "vibetree" -> "wip3" / "vip tree"). Add company-specific terms here.
    "vibetree",
]

deepgram_client = DeepgramClient(
    DEEPGRAM_API_KEY,
    DeepgramClientOptions(options={"keepalive": "true"}),
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_transcribe(client_ws: WebSocket):
    await client_ws.accept()

    dg_connection = deepgram_client.listen.asyncwebsocket.v("1")

    final_buffer: list[str] = []

    async def flush_buffer():
        if not final_buffer:
            return
        full_transcript = " ".join(final_buffer)
        final_buffer.clear()
        cleaned = normalize_email_like(full_transcript)
        await client_ws.send_json({
            "type": "final",
            "transcript": cleaned,
            "raw": full_transcript,
        })

    async def on_transcript(self, result, **kwargs):
        alt = result.channel.alternatives[0]
        transcript = alt.transcript

        if result.is_final:
            if transcript:
                final_buffer.append(transcript)
            if result.speech_final:
                await flush_buffer()
            elif final_buffer:
                await client_ws.send_json({
                    "type": "interim",
                    "transcript": " ".join(final_buffer),
                })
            return

        if transcript:
            preview = " ".join(final_buffer + [transcript]) if final_buffer else transcript
            await client_ws.send_json({
                "type": "interim",
                "transcript": preview,
            })

    async def on_utterance_end(self, utterance_end, **kwargs):
        await flush_buffer()

    async def on_error(self, error, **kwargs):
        logger.error("Deepgram error: %s", error)

    dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
    dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)
    dg_connection.on(LiveTranscriptionEvents.Error, on_error)

    options = LiveOptions(
        model="nova-3",
        language="en-IN",
        smart_format=True,
        interim_results=True,
        punctuate=True,
        keyterm=KEYTERMS,
        endpointing=400,
        utterance_end_ms=1000,
    )

    started = await dg_connection.start(options)
    if not started:
        await client_ws.send_json({"type": "error", "message": "Failed to connect to Deepgram"})
        await client_ws.close()
        return

    try:
        while True:
            data = await client_ws.receive_bytes()
            await dg_connection.send(data)
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    finally:
        await dg_connection.finish()
