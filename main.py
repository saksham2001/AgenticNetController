import asyncio
import base64
import os
import sys

from dotenv import load_dotenv

from audio_io import AudioInput, AudioOutput
from controller import NetController, NetMode
from prompts import OPENING_SCRIPT, SYSTEM_PROMPT
from realtime_ws import RealtimeClient
from tools import TOOL_SCHEMAS, ToolExecutor

SEMANTIC_VAD = {
    "type": "semantic_vad",
    "create_response": False,
    "interrupt_response": False,
}


async def main():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set in .env")
        sys.exit(1)

    tool_exec = ToolExecutor()
    controller = NetController()
    audio_in = AudioInput()
    audio_out = AudioOutput()

    # --- Event handler ---
    client: RealtimeClient | None = None

    async def handle_event(event: dict):
        etype = event.get("type", "")

        if etype == "session.created":
            print("[Session] Created — sending session.update")
            await client.send_session_update(
                instructions=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                turn_detection=SEMANTIC_VAD,
            )

        elif etype == "session.updated":
            print("[Session] Updated OK")

        elif etype == "response.audio.delta":
            pcm = base64.b64decode(event.get("delta", ""))
            audio_out.write(pcm)

        elif etype == "response.function_call_arguments.done":
            name = event.get("name", "")
            call_id = event.get("call_id", "")
            arguments = event.get("arguments", "{}")
            print(f"[Tool] {name}({arguments})")
            result = tool_exec.execute(name, arguments)
            print(f"[Tool] Result: {result}")
            await client.send_function_output(call_id, result)

        elif etype == "response.done":
            pass  # Response complete

        elif etype == "input_audio_buffer.speech_started":
            print("[VAD] Speech started — cancelling current response")
            await client.send_cancel()
            audio_out.flush()

        elif etype == "input_audio_buffer.speech_stopped":
            print("[VAD] Speech stopped — triggering response")
            await client.send_response_create()

        elif etype == "error":
            print(f"[ERROR] {event.get('error', event)}")

    client = RealtimeClient(api_key=api_key, on_event=handle_event)

    # --- Connect ---
    await client.connect()

    loop = asyncio.get_event_loop()
    audio_in.start(loop)
    audio_out.start()

    # --- Audio send loop ---
    async def audio_send_loop():
        try:
            while True:
                frame = await audio_in.read_frame()
                await client.send_audio(frame)
        except asyncio.CancelledError:
            pass

    # --- CLI loop ---
    async def cli_loop():
        print("\n=== AgenticHamNet CLI ===")
        print("Commands: :start :mode <m> :respond :list :export")
        print("          :prompt <text> :ptt on|off :commit :cancel :quit\n")
        try:
            while True:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    continue
                line = line.strip()
                if not line:
                    continue

                # Session timeout warning
                if controller.should_warn_session_timeout():
                    print("[WARN] Approaching 55-min session limit!")

                if line == ":start":
                    print("[CMD] Starting net — sending opening script")
                    await client.send_response_create(instructions=OPENING_SCRIPT)
                    directive = controller.set_mode(NetMode.CHECKIN)
                    print(f"[Mode] → CHECKIN")

                elif line.startswith(":mode "):
                    mode_str = line.split(None, 1)[1].lower()
                    try:
                        mode = NetMode(mode_str)
                    except ValueError:
                        print(f"[ERR] Unknown mode: {mode_str}")
                        print("  Valid: checkin, ragchew, emergency, wrapup")
                        continue
                    directive = controller.set_mode(mode)
                    print(f"[Mode] → {mode.name}")
                    await client.send_response_create(instructions=directive)

                elif line == ":respond":
                    print("[CMD] Triggering response")
                    await client.send_response_create()

                elif line == ":list":
                    stations = tool_exec.checked_in
                    if not stations:
                        print("[List] No stations checked in.")
                    else:
                        print(f"[List] {len(stations)} station(s):")
                        for i, s in enumerate(stations, 1):
                            parts = [s["call_sign"]]
                            if s.get("name"):
                                parts.append(s["name"])
                            if s.get("location"):
                                parts.append(s["location"])
                            print(f"  {i}. {' — '.join(parts)}")

                elif line == ":export":
                    print(f"[Export] Log file: {tool_exec.log_path}")
                    try:
                        with open(tool_exec.log_path) as f:
                            print(f.read())
                    except FileNotFoundError:
                        print("  (no entries yet)")

                elif line.startswith(":prompt "):
                    text = line.split(None, 1)[1]
                    print(f"[CMD] Injecting prompt: {text[:60]}...")
                    await client.send_response_create(instructions=text)

                elif line.startswith(":ptt "):
                    arg = line.split(None, 1)[1].lower()
                    if arg == "on":
                        print("[PTT] ON — VAD disabled, use :commit to send")
                        await client.send_session_update(
                            instructions=SYSTEM_PROMPT,
                            tools=TOOL_SCHEMAS,
                            turn_detection=None,
                        )
                    elif arg == "off":
                        print("[PTT] OFF — VAD re-enabled")
                        await client.send_session_update(
                            instructions=SYSTEM_PROMPT,
                            tools=TOOL_SCHEMAS,
                            turn_detection=SEMANTIC_VAD,
                        )
                    else:
                        print("[ERR] Usage: :ptt on|off")

                elif line == ":commit":
                    print("[CMD] Committing audio buffer")
                    await client.send_commit()
                    await client.send_response_create()

                elif line == ":cancel":
                    print("[CMD] Cancelling response")
                    await client.send_cancel()
                    audio_out.flush()

                elif line == ":quit":
                    print("[CMD] Shutting down...")
                    return

                else:
                    print(f"[ERR] Unknown command: {line}")

        except asyncio.CancelledError:
            pass

    # --- Run all tasks ---
    tasks = [
        asyncio.create_task(audio_send_loop()),
        asyncio.create_task(client.receive_loop()),
        asyncio.create_task(cli_loop()),
    ]

    # Wait for CLI to exit, then cancel others
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    for t in pending:
        try:
            await t
        except asyncio.CancelledError:
            pass

    # Cleanup
    audio_in.stop()
    audio_out.stop()
    await client.close()
    print("[Done] Net session ended.")
    print(f"[Done] Log: {tool_exec.log_path}")


if __name__ == "__main__":
    asyncio.run(main())
