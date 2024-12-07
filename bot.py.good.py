import requests
try:
    import readline
except ImportError:
    from pyreadline3 import Readline as readline
import os
import sys
import json
import time
from termcolor import colored  # Install using `pip install termcolor`

# Load system prompt from text file
def load_prompt():
    try:
        with open("./prompt.txt", "r", encoding="utf-8") as file:
            return file.read().strip()
    except Exception as error:
        print(colored(f"Error loading system prompt: {error}", "red"))
        sys.exit(1)

system_prompt = load_prompt()  # Load the system prompt

# Message history
message_history = [
    {"role": "system", "content": system_prompt}  # Include system prompt at the start
]

# Trim message history to stay within token limits
def trim_message_history():
    max_messages = 30  # Adjust based on token limit
    while len(message_history) > max_messages:
        message_history.pop(1)  # Keep the system prompt, remove oldest messages

# Function to send chat messages to the API endpoint
def get_assistant_response(user_message):
    trim_message_history()

    # Add the user's message to the message history
    message_history.append({"role": "user", "content": user_message})

    try:
        response = requests.post(
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": "artifish/llama3.2-uncensored",
                "messages": message_history,
                "stream": False
            },
        )
        response.raise_for_status()  # Raise an error for HTTP errors
        assistant_message = response.json().get("message", {}).get("content", "").strip()
        if assistant_message:
            message_history.append({"role": "assistant", "content": assistant_message})
        return assistant_message
    except requests.exceptions.RequestException as error:
        print(colored(f"Error: {error}", "red"))
        return "Sorry, something went wrong."

# CLI Chat Interface
def chat_with_assistant():
    print(colored("Say hi to your virtual assistant! Type 'exit' to quit.\n", "cyan"))

    while True:
        try:
            user_message = input(colored(f"You({len(message_history)}): ", "green"))
            if user_message.lower() == "exit":
                print(colored("Goodbye!", "yellow"))
                break

            stop_spinner = show_spinner()  # Start the spinner
            assistant_response = get_assistant_response(user_message)
            stop_spinner()  # Stop the spinner

            if assistant_response:
                print(colored(f">>>>({len(message_history)}): {assistant_response}", "blue"))
        except KeyboardInterrupt:
            print(colored("\nGoodbye!", "yellow"))
            break

# Spinner for loading effect
def show_spinner():
    spinner_frames = ["|", "/", "-", "\\"]
    frame_index = 0
    running = True

    def spin():
        nonlocal frame_index
        while running:
            sys.stdout.write(colored(f"\r{spinner_frames[frame_index % len(spinner_frames)]} ", "cyan"))
            sys.stdout.flush()
            frame_index += 1
            time.sleep(0.1)

    import threading
    spinner_thread = threading.Thread(target=spin)
    spinner_thread.start()

    def stop():
        nonlocal running
        running = False
        spinner_thread.join()
        sys.stdout.write("\r")  # Clear the spinner
        sys.stdout.flush()

    return stop

if __name__ == "__main__":
    chat_with_assistant()
