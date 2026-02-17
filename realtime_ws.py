import base64
import json
from typing import Any, Callable, Coroutine

import websockets

WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-realtime"


class RealtimeClient:
    def __init__(
        self,
        api_key: str,
        on_event: Callable[[dict[str, Any]], Coroutine],
    ):
        self._api_key = api_key
        self._on_event = on_event
        self._ws = None

    async def connect(self):
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "OpenAI-Beta": "realtime=v1",
        }
        self._ws = await websockets.connect(WS_URL, additional_headers=headers)
        print("[WS] Connected")

    async def send(self, event: dict):
        if self._ws:
            await self._ws.send(json.dumps(event))

    async def receive_loop(self):
        async for raw in self._ws:
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                print(f"[WS] Non-JSON message: {raw[:100]}")
                continue
            await self._on_event(event)

    # --- Helper methods ---

    async def send_session_update(
        self,
        instructions: str,
        tools: list[dict],
        turn_detection: dict | None,
    ):
        session = {
            "instructions": instructions,
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "voice": "ash",
            "tools": tools,
            "tool_choice": "auto",
        }
        if turn_detection is not None:
            session["turn_detection"] = turn_detection
        else:
            session["turn_detection"] = None
        await self.send({"type": "session.update", "session": session})

    async def send_audio(self, pcm_bytes: bytes):
        encoded = base64.b64encode(pcm_bytes).decode("ascii")
        await self.send(
            {"type": "input_audio_buffer.append", "audio": encoded}
        )

    async def send_response_create(self, instructions: str | None = None):
        event: dict[str, Any] = {"type": "response.create"}
        if instructions:
            event["response"] = {"instructions": instructions}
        await self.send(event)

    async def send_function_output(self, call_id: str, output_json: str):
        await self.send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": output_json,
                },
            }
        )
        await self.send_response_create()

    async def send_commit(self):
        await self.send({"type": "input_audio_buffer.commit"})

    async def send_cancel(self):
        await self.send({"type": "response.cancel"})

    async def close(self):
        if self._ws:
            await self._ws.close()
            self._ws = None
