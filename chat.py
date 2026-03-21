import requests
import sys
import os
import json
import time
from termcolor import colored
import threading
from pprint import pprint
import re
from datetime import datetime

class Ollama:
    def __init__(self, 
                 model_name, 
                 api_url = 'http://127.0.0.1:11434', 
                 prompt_file = "./prompt.txt",
                 name = None,
                 color = 'blue',
                 stream_mode = True,
                 json_mode = False
                 ):
        # config
        self.name = name
        self.color = color
        self.api_url = api_url
        self.model_name = model_name
        self.prompt_file = prompt_file
        self.stream_mode = stream_mode
        self.json_mode = json_mode
        self.system_prompt = self.load_prompt()
        if self.json_mode:
            self.stream_mode = False
        # private
        self.message_history = []
        self.message_history.append({"role": "system", "content": self.system_prompt})
        self.context_size = 0
        self.spinner_running = False
        self.spinner_thread = None

    def load_prompt(self):
        try:
            with open(self.prompt_file, "r", encoding="utf-8") as file:
                return file.read().strip()
        except Exception as error:
            print(colored(f"Error loading system prompt: {error}", "red"))
            sys.exit(1)

    def remove_oldest_message(self, max_messages=30):
        # This does not remove system message which is always 0
        while len(self.message_history) > max_messages:
            self.message_history.pop(1)

    def speak(self, text):
        # Remove emojis
        text = re.sub(r"[^\w\s,.!?']", ".", text)
        # Remove text between ** (including **)
        text = re.sub(r'\*.*?\*', '.', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Remove trailing dots
        text = re.sub(r"\.+$", "", text)
        try:
            requests.post("http://127.0.0.1:5001/speak", json={"text": text}, timeout=1)
        except:
            pass

    def start_spinner(self):
        spinner_frames = "⣾⣽⣻⢿⡿⣟⣯⣷"
        frame_index = 0
        self.spinner_running = True

        def spin():
            nonlocal frame_index
            while self.spinner_running:
                sys.stdout.write(colored(f"\r{spinner_frames[frame_index % len(spinner_frames)]} ", self.color))
                sys.stdout.flush()
                frame_index += 1
                time.sleep(0.1)

        self.spinner_thread = threading.Thread(target=spin)
        self.spinner_thread.start()

    def stop_spinner(self):
        if self.spinner_running:
            self.spinner_running = False
            if self.spinner_thread:
                self.spinner_thread.join()
                self.spinner_thread = None
                sys.stdout.write("\r")
                sys.stdout.flush()

    def handle_tool_call(self, message):
        pass
        # if 'tool_calls' in message:
        #     for tool_call in message['tool_calls']:
        #         if 'function' in tool_call:
        #             func = tool_call['function']
        #             if 'name' in func and 'arguments' in func:
        #                 print(colored(func['name']+'('+str(func['arguments'])+')', 'magenta'))
        #                 self.message_history.append({"role": "assistant", "tool_calls": message['tool_calls']})
        #                 self.tool_function = func['name'] 


    def send(self, message):
        self.remove_oldest_message()
        self.message_history.append({"role": "user", "content": message})
        try:
            payload = {
                "model": self.model_name,
                "messages": self.message_history,
                "stream": self.stream_mode,
                "options": {"penalize_newline": True, "temperature": 10},
            }
            if self.json_mode:
                payload['format'] = "json"

            self.start_spinner()
            with requests.post(
                self.api_url+'/api/chat',
                json=payload,
                stream=self.stream_mode
            ) as response:
                
                self.stop_spinner() 
                response.raise_for_status()
                # stram mode
                if self.stream_mode:
                    assistant_message = ""
                    if self.name:
                        sys.stdout.write(colored(self.name+': ', self.color))
                    for line in response.iter_lines(decode_unicode=True):
                        if line:
                            chunk = json.loads(line)
                            message = chunk.get("message", {})
                            if 'content' in message:                                    
                                assistant_message += message['content']
                                sys.stdout.write(colored(message['content'], self.color))
                                sys.stdout.flush()

                            if 'done' in chunk and chunk['done']:
                                self.context_size = chunk.get('prompt_eval_count', self.context_size)
                    
                    assistant_message = assistant_message.strip()
                    if assistant_message:
                        self.message_history.append({"role": "assistant", "content": assistant_message})
                    print('')
                    return assistant_message
                
                # regular non stream mode
                else:
                    
                    response_data = response.json()
                    message = response_data.get("message", {})
                    pprint(message)
                    if 'content' in message:                                    
                        assistant_message = message['content'].strip()
                        self.message_history.append({"role": "assistant", "content": assistant_message})
                        print(colored(assistant_message, self.color))

                    self.context_size = response_data.get('prompt_eval_count', self.context_size)
                    
                    # pprint(self.message_history)

                    return assistant_message
        except KeyboardInterrupt:
            exit()
            raise
        except Exception as error:
            print(colored(f"Error: {error.response.text}", "red"))
        finally:
            self.stop_spinner()  # Stop spinner in all cases

    def chat(self):
        print(colored("Say hi to your virtual assistant! Type '/exit' to quit.\n", "cyan"))
        while True:
            try:
                user_message = input(colored(f"You({self.context_size}): ", "green"))
                if user_message.lower() == "/exit":
                    print(colored("Goodbye!", "yellow"))
                    break
                assistant_response = self.send(user_message)
                self.speak(assistant_response)
                print('')
            except KeyboardInterrupt:
                print(colored("\nGoodbye!", "yellow"))
                break


if __name__ == "__main__":

    client = Ollama(
        model_name="artifish/llama3.2-uncensored",
        # model_name="mistral-nemo",
        # model_name="julia:latest",
        prompt_file='prompt.anna.txt'
    )
    client.chat()

    # client1 = Ollama(
    #     model_name="artifish/llama3.2-uncensored",
    #     prompt_file="prompt.universe.txt",
    #     name='Anna'
    # )
    # client1.name='Anna'
    # client2 = Ollama(
    #     model_name="artifish/llama3.2-uncensored",
    #     prompt_file="prompt.universe.txt",
    #     name='Miranda',
    #     color='green'
    # )
    # client2.color='green'
    # client2.name='Miranda'
    # message = 'What is purpose of universe?'
    # while True:
    #     message = client1.send(message)
    #     message = client2.send(message)