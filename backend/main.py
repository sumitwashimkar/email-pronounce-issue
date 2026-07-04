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

# Terms that matter for the "spoken email" problem: the connector words
# themselves plus the domains users actually say out loud. Nova-3 uses
# keyterm prompting (plain terms, no ":boost" suffix), which replaced the
# older Nova-2 "keywords" parameter.
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

    async def on_transcript(self, result, **kwargs):
        alt = result.channel.alternatives[0]
        transcript = alt.transcript
        if not transcript:
            return

        if result.is_final:
            cleaned = normalize_email_like(transcript)
            await client_ws.send_json({
                "type": "final",
                "transcript": cleaned,
                "raw": transcript,
            })
        else:
            await client_ws.send_json({
                "type": "interim",
                "transcript": transcript,
            })

    async def on_error(self, error, **kwargs):
        logger.error("Deepgram error: %s", error)

    dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
    dg_connection.on(LiveTranscriptionEvents.Error, on_error)

    options = LiveOptions(
        model="nova-3",
        language="en-IN",
        smart_format=True,
        interim_results=True,
        punctuate=True,
        keyterm=KEYTERMS,
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
