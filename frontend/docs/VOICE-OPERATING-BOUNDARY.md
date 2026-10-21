# Voice operating boundary (V1.1)

## What hands-free "Hey Canvas" is

- Continuous **browser** speech recognition while the feature is enabled in **Settings → Voice**.
- Wake phrase **"Hey Canvas"** then a spoken command (or wake-only to enter listening).
- Same behavior in **Hey Canvas workspace** and **course chat** (shared hook).

## What it is not

- **Not** a system-wide always-on assistant. No background service when the browser is closed.
- **Not** guaranteed when the tab is backgrounded, minimized, or the OS sleeps — browser policies vary.
- **Not** a replacement for OS wake engines (Siri, Bixby, Copilot voice, etc.).

## Pauses and safety

Recognition **pauses** while:

- The assistant is sending or streaming a reply.
- Push-to-talk is listening or processing.
- Spoken responses (TTS) are playing.

Audio is processed by the browser; Hey Canvas does **not** store raw recordings.

## Human validation still required

Microphone permission, wake accuracy in your room, and TTS self-trigger behavior must be validated on a real machine with Chrome or Edge.
