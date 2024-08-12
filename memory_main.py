# memory_main.py
import os
import re
import json
import threading
import queue
from memory_prompt import system_prompt
import google.generativeai as genai
from typing import Dict, List, Any
from google.generativeai.types import GenerationConfig, HarmCategory, HarmBlockThreshold
from json_fixer_prompt import json_fixer_prompt

# Configure Gemini API
config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
genai.configure(api_key=json.loads(open(config_path).read())['api_keys']['GEMINI_API_KEY'])

# Initialize the model
model = genai.GenerativeModel(model_name="gemini-1.5-pro", system_instruction=system_prompt)


# Define paths for memory storage
MEMORY_PATH = "memory_data"
FULL_MEMORY_CONTENT_FILE = os.path.join(MEMORY_PATH, "full_memory_content.json")
LONG_TERM_MEMORY_FILE = os.path.join(MEMORY_PATH, "long_term_memory.json")
SHORT_TERM_MEMORY_FILE = os.path.join(MEMORY_PATH, "short_term_memory.json")
ABILITIES_MEMORY_FILE = os.path.join(MEMORY_PATH, "abilities_memory.json")
USER_PREFERENCES_FILE = os.path.join(MEMORY_PATH, "user_preferences.json")
IGNORE_FILE = os.path.join(MEMORY_PATH, "ignore.json")


class MemoryManager:
    memory_enabled = False
    memory_queue = queue.Queue()
    processing_thread = None

    def __init__(self):
        self.ensure_memory_files_exist()
        self.lock = threading.Lock()
        self.processing_thread = None
        self.generation_config = GenerationConfig(
            response_mime_type="application/json",
            temperature=1,
            max_output_tokens=3000,
        )
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        self.json_fixer_model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=json_fixer_prompt)
        self.json_fixer_chat = self.json_fixer_model.start_chat(history=[])
    
    def parse_json_response(self, response):
        def fix_json_issues(bad_json):
            # Adding quotes around unquoted keys
            bad_json = re.sub(r'(?<!")(\b\w+\b)(?=\s*:)', r'"\1"', bad_json)
            # Escaping backslashes correctly
            bad_json = re.sub(r'\\(?![\\"])', r'\\\\', bad_json)
            # Removing invalid escape sequences
            bad_json = re.sub(r'\\[^\\"]', r'', bad_json)
            # Fixing missing commas between key-value pairs
            bad_json = re.sub(r'(?<=\w)(\s*)(?=")', r',\1', bad_json)
            # Fixing missing braces
            if bad_json.count('{') > bad_json.count('}'):
                bad_json += '}'
            if bad_json.count('[') > bad_json.count(']'):
                bad_json += ']'
            # Fixing trailing commas before closing braces
            bad_json = re.sub(r',(\s*[}\]])', r'\1', bad_json)
            # Ensuring colons are followed by a space
            bad_json = re.sub(r':(\S)', r': \1', bad_json)
            # Fixing common typos in JSON keys/values
            bad_json = re.sub(r'\bNone\b', 'null', bad_json)
            bad_json = re.sub(r'\bTrue\b', 'true', bad_json)
            bad_json = re.sub(r'\bFalse\b', 'false', bad_json)
            return bad_json

        cleaned_response = re.sub(r'^```json\n|```$', '', response).strip()
        cleaned_response = cleaned_response.replace("```", "")

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {str(e)}")
            cleaned_response1 = fix_json_issues(cleaned_response)
            try:
                return json.loads(cleaned_response1)
            except json.JSONDecodeError as e:
                print("Failed to fix JSON. Sending to JSON Fixer model...")
                return self.fix_json_with_model(cleaned_response, str(e))

    def fix_json_with_model(self, bad_json, error_message):
        max_attempts = 5
        attempt = 0

        while attempt < max_attempts:
            try:
                model_response = self.json_fixer_chat.send_message(
                    f"Fix this JSON:\n\n{bad_json}\n\nError: {error_message}",
                    generation_config=self.json_fixer_generation_config
                )
                fixed_json = model_response.text
                cleaned_fixed_json = re.sub(r'^```json\n|```$', '', fixed_json).strip()
                cleaned_fixed_json = cleaned_fixed_json.replace("```", "")
                
                parsed_json = json.loads(cleaned_fixed_json)
                return parsed_json
            except json.JSONDecodeError as e:
                attempt += 1
                error_message = str(e)
                if attempt == max_attempts:
                    raise ValueError(f"Failed to fix JSON after {max_attempts} attempts")

    @property
    def json_fixer_generation_config(self):
        return genai.types.GenerationConfig(
            temperature=1,
            top_p=1,
            top_k=1,
            max_output_tokens=8000,
        )
    
    def set_memory_path(self, path):
        global MEMORY_PATH, FULL_MEMORY_CONTENT_FILE, LONG_TERM_MEMORY_FILE, SHORT_TERM_MEMORY_FILE, ABILITIES_MEMORY_FILE, USER_PREFERENCES_FILE, IGNORE_FILE
        
        MEMORY_PATH = path
        FULL_MEMORY_CONTENT_FILE = os.path.join(MEMORY_PATH, "full_memory_content.json")
        LONG_TERM_MEMORY_FILE = os.path.join(MEMORY_PATH, "long_term_memory.json")
        SHORT_TERM_MEMORY_FILE = os.path.join(MEMORY_PATH, "short_term_memory.json")
        ABILITIES_MEMORY_FILE = os.path.join(MEMORY_PATH, "abilities_memory.json")
        USER_PREFERENCES_FILE = os.path.join(MEMORY_PATH, "user_preferences.json")
        IGNORE_FILE = os.path.join(MEMORY_PATH, "ignore.json")
        
        self.ensure_memory_files_exist()
    
    @classmethod
    def set_memory_enabled(cls, enabled):
        cls.memory_enabled = enabled
        if enabled and cls.processing_thread is None:
            cls.processing_thread = threading.Thread(target=cls.process_memory_queue, daemon=True)
            cls.processing_thread.start()
        elif not enabled and cls.processing_thread is not None:
            cls.processing_thread.join()
            cls.processing_thread = None

    def append_to_full_memory(self, content_type: str, content: str):
        if self.memory_enabled:
            formatted_content = f"--- {content_type} ---\n{content}\n--- END {content_type} ---\n\n"
            self.memory_queue.put((content_type, formatted_content))
        else:
            print("Attempted to append to memory, but memory system is disabled")

    @classmethod
    def process_memory_queue(cls):
        while cls.memory_enabled or not cls.memory_queue.empty():
            try:
                content_type, content = cls.memory_queue.get(timeout=1)
                cls.process_memory_item(content_type, content)
            except queue.Empty:
                print("Memory queue is empty")
                continue

    @classmethod
    def process_memory_item(cls, content_type: str, content: str):
        instance = cls()
        with instance.lock:
            with open(FULL_MEMORY_CONTENT_FILE, 'r+') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = []
                data.append({"type": content_type, "content": content})
                f.seek(0)
                json.dump(data, f, indent=4)
                f.truncate()
        
        instance.process_memory()

    def ensure_memory_files_exist(self):
        os.makedirs(MEMORY_PATH, exist_ok=True)
        for file_path in [FULL_MEMORY_CONTENT_FILE, LONG_TERM_MEMORY_FILE, SHORT_TERM_MEMORY_FILE, ABILITIES_MEMORY_FILE, USER_PREFERENCES_FILE, IGNORE_FILE]:
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    json.dump([], f)

    def process_memory(self):
        with self.lock:
            with open(FULL_MEMORY_CONTENT_FILE, 'r') as f:
                full_memory_content = json.load(f)
            
            if not full_memory_content:
                return

            processed_data = self.process_information(full_memory_content)
            
            for memory_type in ["long_term_memory", "short_term_memory", "abilities", "user_preferences"]:
                self.save_memory(memory_type, processed_data.get(f"{memory_type}", []))

            self.update_ignore_file(full_memory_content)

            with open(FULL_MEMORY_CONTENT_FILE, 'w') as f:
                json.dump([], f)

    def update_ignore_file(self, processed_content):
        with open(IGNORE_FILE, 'r+') as f:
            try:
                ignore_data = json.load(f)
            except json.JSONDecodeError:
                ignore_data = []
            ignore_data.extend(processed_content)
            f.seek(0)
            json.dump(ignore_data, f, indent=4)
            f.truncate()

    def process_information(self, full_memory_content) -> Dict[str, List[Dict[str, Any]]]:
        prompt = f"""
        ---------------------------------------------------------------------------------------------------

        Content to Analyze:

         {json.dumps(full_memory_content, indent=2)}

        ---------------------------------------------------------------------------------------------------
        
        EXISTING MEMORY:
            
            ----------------
            LONG TERM MEMORY:
            {json.dumps(self.get_memory("long_term_memory"), indent=2)}

            ----------------
            SHORT TERM MEMORY:
            {json.dumps(self.get_memory("short_term_memory"), indent=2)}

            ----------------
            ABILITIES MEMORY:
            {json.dumps(self.get_memory("abilities"), indent=2)}

            ----------------
            USER PREFERENCES:
            {json.dumps(self.get_memory("user_preferences"), indent=2)}

            ----------------

        ---------------------------------------------------------------------------------------------------
        """

        response = model.generate_content(
            prompt,
            generation_config=self.generation_config,
            safety_settings=self.safety_settings
        )
        parsed_response = self.parse_json_response(response.text)
        
        if isinstance(parsed_response, str):
            return json.loads(parsed_response)
        return parsed_response

    def save_memory(self, memory_type: str, data: List[Dict[str, Any]]):
        file_path = {
            "long_term_memory": LONG_TERM_MEMORY_FILE,
            "short_term_memory": SHORT_TERM_MEMORY_FILE,
            "abilities": ABILITIES_MEMORY_FILE,
            "user_preferences": USER_PREFERENCES_FILE
        }.get(memory_type)

        if not file_path:
            raise ValueError(f"Invalid memory type: {memory_type}")

        with open(file_path, 'r+') as f:
            existing_data = json.load(f)
            existing_data.extend(data)
            f.seek(0)
            json.dump(existing_data, f, indent=4)
            f.truncate()

    def get_memory(self, memory_type: str) -> List[Dict[str, Any]]:
        if memory_type == "full_memory_content":
            with open(FULL_MEMORY_CONTENT_FILE, 'r') as f:
                return json.load(f)
        else:
            file_path = {
                "long_term_memory": LONG_TERM_MEMORY_FILE,
                "short_term_memory": SHORT_TERM_MEMORY_FILE,
                "abilities": ABILITIES_MEMORY_FILE,
                "user_preferences": USER_PREFERENCES_FILE
            }.get(memory_type)

            if not file_path:
                raise ValueError(f"Invalid memory type: {memory_type}")

            with open(file_path, 'r') as f:
                return json.load(f)


    def get_all_memory(self) -> Dict[str, List[Dict[str, Any]]]:
        return {
            "long_term_memory": self.get_memory("long_term_memory"),
            "short_term_memory": self.get_memory("short_term_memory"),
            "abilities": self.get_memory("abilities"),
            "user_preferences": self.get_memory("user_preferences")
        }