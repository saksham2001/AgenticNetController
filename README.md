# AgenticHamNet

AI net control operator for amateur radio nets. Uses OpenAI's Realtime API for live voice interaction over radio.

Built for W3VC Carnegie Tech Radio Club.

## Setup

```
sudo apt install libportaudio2
pip install -r requirements.txt
```

Add your OpenAI API key to `.env`:
```
OPENAI_API_KEY="sk-..."
```

## Run

```
python3 main.py
```

Audio in/out should be wired to your radio (mic in = RX audio, speaker out = TX audio).

## Commands

| Command | What it does |
|---|---|
| `:start` | Read the opening script, begin check-ins |
| `:mode checkin` | Switch to check-in mode |
| `:mode ragchew` | Call stations for updates/chat |
| `:mode recheckin` | Roll call for FCC re-identification |
| `:mode emergency` | Priority traffic handling |
| `:mode wrapup` | Close the net |
| `:respond` | Force the AI to speak |
| `:list` | Print checked-in stations |
| `:export` | Dump the JSONL log |
| `:prompt <text>` | Send an arbitrary instruction to the AI |
| `:ptt on` | Disable VAD, require manual `:commit` |
| `:ptt off` | Re-enable VAD |
| `:commit` | Send buffered audio (PTT mode) |
| `:cancel` | Stop AI mid-speech |
| `:quit` | Shut down |

## Typical flow

1. `:start` — opening script plays, check-in mode begins
2. Stations check in over the air, AI logs them
3. `:mode ragchew` — AI calls each station for updates
4. `:mode wrapup` — AI closes the net
5. `:quit`
