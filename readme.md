# vgirl

A local AI voice assistant — text chat powered by Ollama with real-time text-to-speech via Piper.

![Chat Screenshot](./readme.png)

---

## How it works

- `chat.py` — sends messages to a local Ollama model and streams the response to the terminal
- `speak.py` — HTTP server that receives text and speaks it aloud using Piper TTS
- The assistant's response is normalized (emojis stripped, punctuation cleaned) before being sent to Piper

---

## Prerequisites

- [Ollama](https://ollama.com) installed and running
- [Piper TTS binary](https://github.com/rhasspy/piper/releases) — the standalone executable, not the Python package
- Python 3.10+
- A Piper voice model (`.onnx` + `.onnx.json`)

---

## Setup

### 1. Install Ollama and pull the model

```bash
ollama pull artifish/llama3.2-uncensored
ollama serve
```

### 2. Install Piper binary

Download the Piper binary for your platform from the [releases page](https://github.com/rhasspy/piper/releases) and extract it to a folder, e.g. `~/piper` or `D:\app\piper`.

Add that folder to your system `PATH` so `piper` is available globally.

> **Note:** Do not install `piper-tts` from PyPI — it conflicts with the binary.

### 3. Download a voice model

Place `.onnx` and `.onnx.json` files in the same folder as the Piper binary.

Recommended voices:
- **cori-high** (British female) — [brycebeattie.com/files/tts](https://brycebeattie.com/files/tts/)
- **en_GB-jenny_dioco-medium** — [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices)

### 4. Install Python dependencies

```bash
pip install -r requirements.txt
pip install pyaudio
```

### 5. Configure your assistant

Edit `prompt.anna.txt` to define the assistant's personality and role. The file is loaded as the system prompt on startup.

To use a different prompt file, change `prompt_file` in `chat.py`:

```python
client = Ollama(
    model_name="artifish/llama3.2-uncensored",
    prompt_file="prompt.anna.txt"
)
```

---

## Running

Start the TTS server in one terminal:

```bash
python speak.py --server
```

Start the chat in another terminal:

```bash
python chat.py
```

---

## speak.py usage

```bash
# Speak directly
python speak.py en "Hello there"
python speak.py cori "Hey, how are you?"

# Start HTTP server (default port 5001)
python speak.py --server
python speak.py --server --port 5002
```

HTTP API:

```bash
curl -X POST http://localhost:5001/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello", "lang": "cori"}'
```

| Field | Required | Description |
|-------|----------|-------------|
| `text` | yes | Text to speak |
| `lang` | no | Voice key (default: `en`). See `MODELS` in `speak.py` |
| `model` | no | Direct path to a `.onnx` file |

---

## Available voices

Edit the `MODELS` dict in `speak.py` to add or change voices:

```python
MODELS = {
    "en":    "cori-high.onnx",       # default
    "cori":  "cori-high.onnx",
    "jenny": "en_GB-jenny_dioco-medium.onnx",
    "amy":   "en_US-amy-medium.onnx",
    "ka":    "ka_GE-natia-medium.onnx",
}
```

---

## Chat commands

| Command | Description |
|---------|-------------|
| `/reset` | Clear conversation history |
| `/exit` | Save history and quit |

Conversation history is saved to `history.<name>.json` on exit and restored on next startup.
