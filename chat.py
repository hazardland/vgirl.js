import requests
import sys
import json
import time
import threading
import re
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.theme import Theme

theme = Theme({
    "user":      "bold green",
    "assistant": "bold blue",
    "info":      "cyan",
    "error":     "bold red",
    "dim":       "dim white",
    "warn":      "bold yellow",
})

console = Console(theme=theme)

CONTEXT_WARN = 3000


class Ollama:
    def __init__(self,
                 model_name,
                 api_url='http://127.0.0.1:11434',
                 prompt_file="./prompt.txt",
                 name=None,
                 stream_mode=True,
                 json_mode=False
                 ):
        self.name        = name or "Assistant"
        self.api_url     = api_url
        self.model_name  = model_name
        self.prompt_file = prompt_file
        self.stream_mode = stream_mode
        self.json_mode   = json_mode
        self.voice       = "cori"
        self.muted       = False
        self.system_prompt = self.load_prompt()
        if self.json_mode:
            self.stream_mode = False
        self.message_history = [{"role": "system", "content": self.system_prompt}]
        self.context_size    = 0
        self.spinner_running = False
        self.spinner_thread  = None
        self.history_file    = self.prompt_file.replace('prompt', 'history').replace('.txt', '.json')
        self.load_history()

    def load_prompt(self):
        try:
            with open(self.prompt_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            console.print(f"Error loading system prompt: {e}", style="error")
            sys.exit(1)

    def load_history(self):
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                self.message_history += json.load(f)
        except FileNotFoundError:
            pass

    def save_history(self):
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.message_history[1:], f, ensure_ascii=False)

    def remove_oldest_message(self, max_messages=30):
        while len(self.message_history) > max_messages:
            self.message_history.pop(1)

    def speak(self, text):
        if self.muted:
            return
        # Treat newlines as sentence endings
        text = re.sub(r'([^.!?,])\n', r'\1. ', text)
        text = re.sub(r'\n', ' ', text)
        # Replace & with comma
        text = re.sub(r'\s*&\s*', ', ', text)
        # Remove *markdown*
        text = re.sub(r'\*+.*?\*+', '', text)
        # Special chars between two words → sentence dot
        text = re.sub(r'(?<=[a-zA-Z0-9])\s*[^\w\s,.!?\'-]+\s*(?=[a-zA-Z0-9])', '. ', text)
        # Remaining special chars → remove
        text = re.sub(r'[^\w\s,.!?\'-]', '', text)
        # Normalize ellipsis to single dot
        text = re.sub(r'\.{2,}', '.', text)
        # Deduplicate punctuation: RIGHT?? → RIGHT?
        text = re.sub(r'([!?])\1+', r'\1', text)
        # Lowercase everything
        text = text.lower()
        # Clean extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Capitalize sentence starts
        text = re.sub(r'(?:^|(?<=[.!?])\s)(\w)', lambda m: m.group(0).upper(), text)
        # Remove spaces before punctuation
        text = re.sub(r'\s([.,!?\'"])', r'\1', text)
        # Ensure ends with sentence terminator
        if text and text[-1] not in '.!?':
            text += '.'
        try:
            requests.post("http://127.0.0.1:5001/speak", json={"text": text, "lang": self.voice}, timeout=1)
        except Exception:
            pass

    def start_spinner(self):
        frames = "⣾⣽⣻⢿⡿⣟⣯⣷"
        idx = 0
        self.spinner_running = True

        def spin():
            nonlocal idx
            while self.spinner_running:
                sys.stdout.write(f"\r\033[34m{self.name}: {frames[idx % len(frames)]} \033[0m")
                sys.stdout.flush()
                idx += 1
                time.sleep(0.1)

        self.spinner_thread = threading.Thread(target=spin)
        self.spinner_thread.start()

    def stop_spinner(self):
        if self.spinner_running:
            self.spinner_running = False
            if self.spinner_thread:
                self.spinner_thread.join()
                self.spinner_thread = None
                sys.stdout.write(f"\r{' ' * (len(self.name) + 4)}\r")
                sys.stdout.flush()

    def send(self, message):
        self.remove_oldest_message()
        self.message_history.append({"role": "user", "content": message})
        try:
            payload = {
                "model": self.model_name,
                "messages": self.message_history,
                "stream": self.stream_mode,
                "options": {
                    "temperature": 0.9,          # 0.8–1.1 sweet spot for creative but coherent dirty talk
                    "top_p": 0.95,
                    "min_p": 0.05,               # helps avoid total garbage tokens
                    "repeat_penalty": 1.15,      # mild anti-repetition without killing flow
                    # optionally: "presence_penalty": 0.3,   # discourages introducing new random topics
                    # "frequency_penalty": 0.2,              # lightly penalizes word reuse
                },
            }
            if self.json_mode:
                payload['format'] = "json"

            t_start = time.time()
            self.start_spinner()
            with requests.post(self.api_url + '/api/chat', json=payload, stream=self.stream_mode) as response:
                self.stop_spinner()
                response.raise_for_status()

                if self.stream_mode:
                    assistant_message = ""
                    sys.stdout.write("\r")
                    sys.stdout.flush()
                    console.print(f"[assistant]{self.name}:[/assistant] ", end="")
                    for line in response.iter_lines(decode_unicode=True):
                        if line:
                            chunk = json.loads(line)
                            msg = chunk.get("message", {})
                            if 'content' in msg:
                                assistant_message += msg['content']
                                console.print(msg['content'], end="", style="blue", markup=False)
                            if chunk.get('done'):
                                self.context_size = chunk.get('prompt_eval_count', self.context_size)
                    elapsed = time.time() - t_start
                    console.print(f"  [dim]({elapsed:.1f}s)[/dim]")
                    assistant_message = assistant_message.strip()
                    if assistant_message:
                        self.message_history.append({"role": "assistant", "content": assistant_message})
                    return assistant_message

                else:
                    data = response.json()
                    msg = data.get("message", {})
                    if 'content' in msg:
                        assistant_message = msg['content'].strip()
                        self.message_history.append({"role": "assistant", "content": assistant_message})
                        console.print(assistant_message, style="blue")
                    self.context_size = data.get('prompt_eval_count', self.context_size)
                    return assistant_message

        except KeyboardInterrupt:
            raise
        except Exception as e:
            console.print(f"Error: {e}", style="error")
        finally:
            self.stop_spinner()

    def chat(self):
        history_count = len(self.message_history) - 1
        history_note  = f"[dim]{history_count} messages loaded[/dim]" if history_count else ""

        console.print(Panel(
            f"[assistant]{self.name}[/assistant]  [dim]|[/dim]  [dim]{self.model_name}[/dim]  [dim]|[/dim]  [dim]{self.voice}[/dim]"
            + (f"\n{history_note}" if history_note else ""),
            subtitle="[dim]/help for commands[/dim]",
            border_style="blue",
        ))

        while True:
            try:
                ts_style = "warn" if self.context_size > CONTEXT_WARN else "dim"
                console.print(Rule(f"[{ts_style}]{datetime.now().strftime('%H:%M')}[/{ts_style}]", style=ts_style))
                user_message = console.input("[user]You[/user]: ")

                if not user_message.strip():
                    continue

                cmd = user_message.strip().lower()

                if cmd == "/exit":
                    self.save_history()
                    console.print("Goodbye!", style="info")
                    break

                if cmd == "/reset":
                    self.message_history = [{"role": "system", "content": self.system_prompt}]
                    console.print("Conversation reset.", style="info")
                    continue

                if cmd == "/mute":
                    self.muted = not self.muted
                    state = "muted" if self.muted else "unmuted"
                    console.print(f"TTS {state}.", style="info")
                    continue

                if cmd.startswith("/voice "):
                    self.voice = cmd.split(" ", 1)[1].strip()
                    console.print(f"Voice set to [bold]{self.voice}[/bold].", style="info")
                    continue

                if cmd == "/retry":
                    # Remove last user + assistant exchange and resend
                    for _ in range(2):
                        if len(self.message_history) > 1:
                            self.message_history.pop()
                    last_user = next(
                        (m["content"] for m in reversed(self.message_history) if m["role"] == "user"),
                        None
                    )
                    if not last_user:
                        console.print("Nothing to retry.", style="info")
                        continue
                    self.message_history.pop()  # remove that user message too so send() re-adds it
                    user_message = last_user

                if cmd == "/help":
                    console.print(Panel(
                        "[dim]/help[/dim]          show this message\n"
                        "[dim]/reset[/dim]         clear conversation history\n"
                        "[dim]/mute[/dim]          toggle TTS on/off\n"
                        "[dim]/voice [name][/dim]  switch voice (cori, jenny, amy)\n"
                        "[dim]/retry[/dim]         resend last message\n"
                        "[dim]/exit[/dim]          save history and quit",
                        title="Commands", border_style="dim"
                    ))
                    continue

                assistant_response = self.send(user_message)
                if assistant_response:
                    self.speak(assistant_response)

            except KeyboardInterrupt:
                self.save_history()
                console.print("\nGoodbye!", style="info")
                break


if __name__ == "__main__":
    persona = sys.argv[1] if len(sys.argv) > 1 else "anna"
    client = Ollama(
        model_name="artifish/llama3.2-uncensored",
        prompt_file=f'prompt.{persona}.txt',
        name=persona.capitalize(),
    )
    client.chat()
