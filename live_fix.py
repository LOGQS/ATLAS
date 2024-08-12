# live_fix.py
import asyncio
import logging
from typing import Dict, Any
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from command_execution import *
import inspect
from live_fix_prompt import live_fix_prompt
from PIL import ImageGrab, ImageChops
import numpy as np
import json
from memory_main import MemoryManager
import mimetypes
import docx
from json_fixer_prompt import json_fixer_prompt
from live_fix_monitor import live_fix_monitor

def get_available_functions():
    available_functions = {}
    for name, obj in globals().items():
        if inspect.isclass(obj) and name.endswith('Agent'):
            class_functions = inspect.getmembers(obj, predicate=inspect.isfunction)
            for func_name, func in class_functions:
                if not func_name.startswith('_'):  # Exclude private methods
                    available_functions[func_name] = func

    return available_functions

class ScreenChangeDetector:
    def __init__(self, callback, threshold=0.05):
        self.running = False
        self.previous_image = None
        self.threshold = threshold
        self.callback = callback
        print(f"ScreenChangeDetector initialized with threshold: {self.threshold}")

    async def start(self):
        self.running = True
        print("ScreenChangeDetector started")  
        await self.detect_screen_change()

    def stop(self):
        self.running = False
        print("ScreenChangeDetector stopped")

    async def detect_screen_change(self):
        print("Screen change detection started")
        while self.running:
            try:
                current_image = ImageGrab.grab()
                if self.previous_image is not None:
                    diff = ImageChops.difference(self.previous_image, current_image)
                    diff_np = np.array(diff)
                    change_amount = np.sum(diff_np) / (diff_np.size * 255)
                    
                    print(f"Current change amount: {change_amount:.6f}")
                    
                    if change_amount > self.threshold:
                        print(f"Threshold exceeded: {change_amount:.6f} > {self.threshold}")
                        await self.callback(change_amount)
                else:
                    print("First image captured, waiting for next frame to compare")
                
                self.previous_image = current_image
            except Exception as e:
                print(f"Error in detect_screen_change: {str(e)}")
            
            await asyncio.sleep(1)
        print("Screen change detection stopped")

class LiveFixAssistant:
    def __init__(self):
        self.logger = self.setup_logger()
        self.model = self.initialize_model()
        self.task_context = {}
        self.current_subtask_id = 1
        self.current_task = None
        self.screen_change_trigger = asyncio.Event()
        self.task_cancelled = False
        self.screen_detector = ScreenChangeDetector(self.on_screen_change)
        self.memory_manager = MemoryManager()
        self.chat_history = []
        self.uploaded_files = []
        self.background_tasks = {}
        self.available_functions = get_available_functions()
        self.waiting_for_screen_change = False
        self.json_fixer_model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=json_fixer_prompt)
        self.json_fixer_chat = self.json_fixer_model.start_chat(history=[])
        self.notification_callback = None
        self.config = self.load_config()

    def setup_logger(self):
        logger = logging.getLogger('LiveFixAssistant')
        logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler('logs/live_fix.log', encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger
    
    def load_config(self):
        config_path = r'config/config.json'
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {"gui_settings": {"mode_selected": "safe"}}
    
        
    def parse_json_response(self, response):
        if isinstance(response, dict):
            return response
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
            self.logger.error(f"Error parsing JSON: {str(e)}")
            self.logger.info("Attempting to fix JSON...")
            cleaned_response1 = fix_json_issues(cleaned_response)
            try:
                return json.loads(cleaned_response1)
            except json.JSONDecodeError as e:
                self.logger.error("Failed to fix JSON. Sending to JSON Fixer model...")
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
                
                # Try to parse the fixed JSON
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


    def initialize_model(self):
        return genai.GenerativeModel('gemini-1.5-flash', system_instruction=live_fix_prompt)
    
    def set_gui_callback(self, callback):
        self.gui_callback = callback

    def set_notification_callback(self, callback):
        self.notification_callback = callback

    async def send_notification(self, message: str):
        if self.notification_callback:
            await self.notification_callback(message)
        elif self.gui_callback:
            await self.gui_callback('notification', message)
        else:
            print(f"NOTIFICATION: {message}")

    async def get_user_confirmation(self, prompt: str) -> bool:
        if self.gui_callback:
            return await self.gui_callback('confirmation', prompt)
        return False

    async def get_user_input(self, prompt: str) -> str: 
        if self.gui_callback:
            return await self.gui_callback('input', prompt)
        return ""
    
    async def process_file(self, file_path):
        mime_type, _ = mimetypes.guess_type(file_path)
        file_type = mime_type.split('/')[0] if mime_type else 'unknown'
        file_name = os.path.basename(file_path)

        if file_type in ['image', 'video', 'audio'] or mime_type in [
            'text/plain', 'text/html', 'text/css', 'text/javascript', 'application/x-javascript',
            'text/x-typescript', 'application/x-typescript', 'text/csv', 'text/markdown',
            'text/x-python', 'application/x-python-code', 'application/json', 'text/xml',
            'application/rtf', 'text/rtf'
        ]:
            file = await self.upload_and_process_file(file_path, file_name)
            return file
        elif file_path.endswith('.pdf'):
            return self.extract_text_from_pdf(file_path)
        elif file_path.endswith('.docx'):
            return self.extract_text_from_docx(file_path)
        else:
            return f"Unsupported file type: {file_name}"
    
    async def upload_and_process_file(self, file_path, file_name):
        file = genai.upload_file(path=file_path, display_name=file_name)
        print(f"Uploaded file: {file.name}")
        self.uploaded_files.append((file_name, file))
        
        while file.state.name == "PROCESSING":
            await asyncio.sleep(1)
            file = genai.get_file(file.name)

        if file.state.name == "FAILED":
            raise ValueError(file.state.name)
        
        print("File processing completed.")
        
        return file
    
    def clear_uploaded_files(self):
        self.uploaded_files.clear()
        print("Cleared uploaded files in LiveFixAssistant")
    
    def extract_text_from_pdf(self, file_path):
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            return '\n'.join([page.extract_text() for page in pdf_reader.pages])

    def extract_text_from_docx(self, file_path):
        doc = docx.Document(file_path)
        return '\n'.join([paragraph.text for paragraph in doc.paragraphs])
    
    def add_file(self, file_name, file_content):
        self.uploaded_files.append((file_name, file_content))

    async def process_user_request(self, user_message: str) -> str:
        self.logger.info(f"Processing user request: {user_message}")
        try:
            content = self.prepare_content(user_message)
            print(f"Prepared content: {content}")
            response = await self.generate_response(content)
            print(f"Raw model response: {response}")
            parsed_response = self.parse_json_response(response)
            
            if not parsed_response:
                return "I apologize, but I encountered an error while processing your request. Could you please rephrase or provide more details?"
            
            print(f"Parsed response: {json.dumps(parsed_response, indent=2)}")
            
            final_response = await self.execute_task(parsed_response)
            
            if self.gui_callback:
                await self.gui_callback('task_complete', None)
            
            return final_response
        except Exception as e:
            self.logger.error(f"Error in process_user_request: {str(e)}")
            if self.gui_callback:
                await self.gui_callback('task_complete', None)
            return f"An error occurred: {str(e)}"
    
    def prepare_content(self, user_message):
        content = [f"User: {user_message}"]
        
        added_files = set()  # Keep track of added files
        for file_name, file_content in self.uploaded_files:
            if file_name not in added_files:
                if isinstance(file_content, genai.types.file_types.File):
                    content.append(file_content)
                    print(f"Attached file: {file_name}")
                elif isinstance(file_content, str):
                    content.append(f"Attached file content: {file_name}\n\n{file_content}")
                    print(f"Attached file: {file_name}")
                added_files.add(file_name)
        
        if self.task_context:
            # Include OCR results in the task context
            for key, value in self.task_context.items():
                if key.startswith("screenshot_") and "ocr_result" in value:
                    content.append(f"OCR result for {value['file']}:\n{json.dumps(value['ocr_result'], indent=2)}")
            
            content.append(f"User request: {user_message}")
            content.append(f"Task context: {json.dumps(self.task_context, indent=2)}")
        
        content.append(f"Current Subtask ID(THE SUBTASK IN YOUR RESPONSE WITH THIS SUBTASK ID WILL GET EXECUTED): {self.current_subtask_id}")
        
        return content

    async def generate_response(self, content):
        self.logger.debug(f"Generating response for: {content}")
        chat = self.model.start_chat(history=self.chat_history)
        try:
            response = await chat.send_message_async(
                content=content,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )
            self.chat_history = chat.history
            return response.text
        except Exception as e:
            self.logger.error(f"Error generating response: {str(e)}")
            return f"An error occurred while generating a response: {str(e)}"
        
    async def execute_task(self, parsed_response: Dict[str, Any]):
        if 'response_to_user' in parsed_response:
            await self.send_notification(parsed_response['response_to_user'])

        if parsed_response.get('user_request_fully_finished', False):
            print("User request fully finished")
            self.reset_state()
            return parsed_response.get('response_to_user', "Task completed")

        if not parsed_response.get('continue_execution', True):
            print("Execution stopped as continue_execution is False")
            return parsed_response.get('response_to_user', "Task paused")

        if 'task_breakdown' not in parsed_response or not parsed_response['task_breakdown']:
            return parsed_response.get('response_to_user', "I couldn't generate a proper response. Could you please try again?")

        await self.process_uploaded_files()

        while True:
            current_task = next((task for task in parsed_response['task_breakdown'] if task['subtask_id'] == self.current_subtask_id), None)

            if current_task is None:
                break

            print(f"Executing subtask: {json.dumps(current_task, indent=2)}")

            if current_task.get('start_monitoring', False):
                monitoring_instruction = current_task.get('monitoring_instruction', '')
                screen_descriptions = []
                while True:
                    monitor_response = await live_fix_monitor.analyze_screenshot(monitoring_instruction)
                    if monitor_response:
                        screen_descriptions.append(monitor_response['screen_description'])
                        if monitor_response['condition_met']:
                            break
                    else:
                        print("Error in monitor response")
                        break

                self.task_context[f"monitoring_{self.current_subtask_id}"] = {
                    "screen_descriptions": screen_descriptions,
                    "condition_met": True
                }
            elif current_task['function'] != "None":
                result = await self.execute_step(current_task)
                self.task_context[str(self.current_subtask_id)] = result
                if self.gui_callback:
                    await self.gui_callback('command_result', result)
            
            if current_task.get('waiting_time'):
                await asyncio.sleep(current_task['waiting_time'])
            
            if current_task.get('screen_change'):
                self.waiting_for_screen_change = True
                asyncio.create_task(self.screen_detector.start())
                await self.wait_for_screen_change()
                self.waiting_for_screen_change = False
                self.screen_detector.stop()

            if current_task.get('receive_screenshot') or current_task.get('monitoring', False):
                screenshot_file, ocr_result = await self.take_screenshot_and_ocr()
                if screenshot_file and ocr_result:
                    self.uploaded_files.append((screenshot_file.name, screenshot_file))
                    self.task_context[f"screenshot_{self.current_subtask_id}"] = {
                        "file": screenshot_file.name,
                        "ocr_result": ocr_result
                    }
                else:
                    print("Failed to capture screenshot or perform OCR")

            print(f"Task context after execution: {json.dumps(self.task_context, indent=2)}")

            new_parsed_response = await self.continue_execution(parsed_response)
        
            if not new_parsed_response:
                return "I encountered an error while processing. Could you please try again?"

            if new_parsed_response.get('user_request_fully_finished', False):
                print("User request fully finished")
                self.reset_state()
                return new_parsed_response.get('response_to_user', "Task completed")

            if not new_parsed_response.get('continue_execution', False):
                print("Execution stopped as continue_execution is False")
                return new_parsed_response.get('response_to_user', "Task paused")

            if 'response_to_user' in new_parsed_response:
                await self.send_notification(new_parsed_response['response_to_user'])

            self.current_subtask_id += 1
            parsed_response = new_parsed_response

        self.screen_detector.stop()
        return parsed_response.get('response_to_user', "Task completed")

    def reset_state(self):
        self.task_context = {}
        self.current_subtask_id = 1
        self.uploaded_files.clear()
    
    async def execute_monitoring_task(self, task):
        monitoring_interval = task.get('monitoring_interval', 3)
        while not self.task_cancelled:
            screenshot_file, ocr_result = await self.take_screenshot_and_ocr()
            if screenshot_file and ocr_result:
                self.uploaded_files.append((screenshot_file.name, screenshot_file))
                self.task_context[f"screenshot_{self.current_subtask_id}"] = {
                    "file": screenshot_file.name,
                    "ocr_result": ocr_result
                }
                
                content = self.prepare_content(f"Monitoring update. New screenshot available.")
                response = await self.generate_response(content)
                parsed_response = self.parse_json_response(response)
                
                if parsed_response:
                    if 'response_to_user' in parsed_response:
                        await self.send_notification(parsed_response['response_to_user'])
                    
                    if not parsed_response.get('continue_execution', False):
                        break
                
            await asyncio.sleep(monitoring_interval)
        
    async def execute_step(self, task):
        function_name = task['function']
        parameters = task.get('parameters', {})
        return await self.execute_command(function_name, parameters)

    async def execute_command(self, function: str, parameters: Dict[str, Any]):
        print(f"Executing command: {function} with parameters: {parameters}")
        
        if self.config['gui_settings']['mode_selected'] == 'efficiency':
            return await self._execute_command_internal(function, parameters)
        else:
            confirmation = await self.get_user_confirmation(f"Do you allow executing {function} with parameters {parameters}?")
            if not confirmation:
                return "Command execution cancelled by user."
            return await self._execute_command_internal(function, parameters)

    async def _execute_command_internal(self, function: str, parameters: Dict[str, Any]):
        try:
            if function in self.available_functions:
                func = self.available_functions[function]
                if asyncio.iscoroutinefunction(func):
                    result = await func(**parameters)
                else:
                    result = func(**parameters)
                print(f"Command execution result: {result}")
                return result
            else:
                error_message = f"Unknown function: {function}"
                print(error_message)
                return error_message
        except Exception as e:
            error_message = f"Error executing {function}: {str(e)}"
            print(error_message)
            return error_message
    
    async def take_screenshot_and_ocr(self):
        screenshot_dir = os.path.join(os.getcwd(), 'imgs', 'current_screen')
        os.makedirs(screenshot_dir, exist_ok=True)

        try:
            screenshot = ImageGrab.grab()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png', dir=screenshot_dir) as temp_file:
                screenshot.save(temp_file.name)
                screenshot_path = temp_file.name

            ocr_agent = GUIAutomationAgent()
            ocr_result = ocr_agent.perform_ocr(screenshot_path)

            file_name = os.path.basename(screenshot_path)
            uploaded_file = await self.upload_and_process_file(screenshot_path, file_name)

            return uploaded_file, ocr_result
        except Exception as e:
            print(f"Error in take_screenshot_and_ocr: {str(e)}")
            return None, None

    async def wait_for_screen_change(self):
        print("Entering wait_for_screen_change")
        self.logger.info("Waiting for screen change")
        self.screen_change_trigger.clear()
        print("Waiting for screen change trigger")
        await self.screen_change_trigger.wait()
        print("Screen change trigger set")
        self.logger.info("Screen change detected")

    async def on_screen_change(self, change_amount):
        if not self.waiting_for_screen_change:
            return 

        print(f"on_screen_change called with change_amount: {change_amount:.6f}")
        self.logger.info(f"Screen change detected. Change amount: {change_amount:.4f}")
        self.screen_change_trigger.set()
        self.waiting_for_screen_change = False

    async def handle_screen_change(self, change_amount):
        print(f"Handling screen change. Change amount: {change_amount:.6f}")
        self.logger.info(f"Handling screen change. Change amount: {change_amount}")
        screen_state = f"Screen changed with change amount: {change_amount}"
        content = self.prepare_content(f"Screen change detected: {screen_state}. What should I do next?")
        response = await self.generate_response(content)
        print(f"Screen change response: {response}")
        parsed_response = self.parse_json_response(response)
        if parsed_response:
            if 'response_to_user' in parsed_response:
                await self.send_notification(parsed_response['response_to_user'])
            await self.execute_task(parsed_response)
        else:
            print("Failed to parse screen change response")

    async def continue_execution(self, previous_response: Dict[str, Any]):
        follow_up_request = (
            f"Previous response: {json.dumps(previous_response)}. Please provide the next steps."
            f"LOOK AT THE FOLLOWING TASK CONTEXT IN DETAIL AND IF SCREEN DESCRIPTIONS ARE PROVIDED, IT MEANS SCREEN MONITORING IS FINISHED AND LIVE FIX MONITOR DETECTED THAT THE PREVIOUSLY GIVEN CONDITION HAPPENED. YOUR RESPONSE NOW SHOULD USE THE SCREEN DESCRIPTIONS TO CONTINUE THE TASK."
            f"The previous step has been completed. Task context: {json.dumps(self.task_context)}. "
            f"Current Subtask ID(THE SUBTASK IN YOUR RESPONSE WITH THIS SUBTASK ID WILL GET EXECUTED): {self.current_subtask_id} "
            f"YOUR RESPONSE HAS TO INCLUDE A SUBTASK WITH THE SAME SUBTASK ID AS THE CURRENT SUBTASK ID."
        )
        content = self.prepare_content(follow_up_request)
        response = await self.generate_response(content)
        print(f"Continue execution response: {response}")
        parsed_response = self.parse_json_response(response)
        if parsed_response:
            return parsed_response
        else:
            print("Failed to parse continue execution response")
            return None

    def cancel_task(self):
        self.task_cancelled = True
        self.screen_change_trigger.set()
        self.logger.info("Task cancellation requested")
    
    async def process_uploaded_files(self):
        for file_path, file_content in self.uploaded_files:
            self.logger.info(f"Processing file: {file_path}")
            self.task_context[f"file_{len(self.task_context)}"] = {
                "path": file_path,
                "content_summary": file_content[:100] + "..." if len(file_content) > 100 else file_content
            }

    def clear_uploaded_files(self):
        self.uploaded_files.clear()

    async def start_background_task(self, function: str, parameters: Dict[str, Any]):
        task_id = f"task_{len(self.background_tasks)}"
        self.background_tasks[task_id] = asyncio.create_task(self.run_background_task(task_id, function, parameters))
        return {"status": "background", "task_id": task_id, "message": f"Task {task_id} started in the background."}

    async def run_background_task(self, task_id: str, function: str, parameters: Dict[str, Any]):
        try:
            result = await self.execute_command(function, parameters)
            self.task_context[task_id] = result
            await self.send_notification(f"Background task {task_id} completed.")
        except Exception as e:
            self.logger.error(f"Error in background task {task_id}: {str(e)}")
            await self.send_notification(f"Background task {task_id} failed: {str(e)}")
        finally:
            del self.background_tasks[task_id]

    @property
    def generation_config(self):
        return genai.types.GenerationConfig(
            temperature=1,
            max_output_tokens=3000,
        )

    @property
    def safety_settings(self):
        return {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }