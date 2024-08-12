# speech_control.py
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import speech_recognition as sr
import pyttsx3
import threading
import queue
import time
import json
import os
from gui_element_manager import get_active_window, interact_with_element, gui_manager

class SpeechControl:
    def __init__(self, update_indicator, update_transcript, update_status_icon):
        self.update_indicator = update_indicator
        self.update_transcript = update_transcript
        self.update_status_icon = update_status_icon

        self.recognizer = sr.Recognizer()
        self.tts_engine = pyttsx3.init()
        self.is_listening = False
        self.commands_queue = queue.Queue()
        self.listening_thread = None
        self.stopped = threading.Event()

        # Configure Gemini
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
        genai.configure(api_key=json.loads(open(config_path).read())['api_keys']['GEMINI_API_KEY'])

        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        self.generation_config = {
            "temperature": 1,
            "max_output_tokens": 3000,
        }

        self.system_prompt = """
        You are an AI assistant for the Advanced PC Assistant GUI application that has a AI called "ATLAS" in it's core. Your role is to interpret user voice commands, answer questions about the application, and control the GUI based on the current state and available elements.

        Application Structure:
        1. Main chat interface
            1.1. Model dropdown menu(options: gemini-1.5-flash, gemini-1.5-pro, gemini-1.0-pro)
            Explanation: The model dropdown menu allows you to select model that the assistant uses. NEVER SET THE MODEL ANYTHING OTHER THAN 1 OF THE 3 GIVEN OPTIONS. And don't recommend using the gemini-1.0-pro model as it is not as robust as the other 2 models.
            1.2. Text-to-Speech switch
            Explanation: The Text-to-Speech switch allows you to toggle the assistant's speech output on or off.
            1.3. Safe/Efficiency switch(enabled=efficiency, disabled=safe)
            Explanation: The Safe/Efficiency switch allows you to toggle the assistant's ability to execute commands without user confirmation. When enabled, the assistant will execute commands directly. When disabled, a notification window will appear for the user to confirm before executing the command.
            1.4. Enable Memory switch
            Explanation: The Enable Memory switch allows you to toggle the assistant's memory feature on or off. Any memory related feature needs this switch to be enabled to work.
            1.5. Open Memory button
            Explanation: The Open Memory button opens a window where you can view and manage the assistant's memory. The memory corrects, improves and expands the assistant's capabilities and responses.
            1.6. External Knowledge button
            Explanation: The External Knowledge button opens a window where you can view and manage the assistant's external knowledge. The files added here get sent to the assistant every request.
            1.7. Execute Workflow button
            Explanation: The Execute Workflow button opens a window where you can use the workflows previously created from Agent Framework.
            1.8. Speech Control button
            Explanation: The Speech Control button opens a window where you can have an extra assistant, which is you, to control the application using voice commands and to inform the user about the application so that everyone can use it effectively.
            1.9. Microphone button
            Explanation: The microphone button is a easy way to convert speech into text in the input box. It is useful for users who have difficulty typing or for users who prefer to speak rather than type.
            1.10. Reset Chat button
            Explanation: The Reset Chat button clears the chat interface and resets the conversation history with the assistant.
            1.11. Settings button
            Explanation: The Settings button opens the settings window.
            1.12. Send button
            Explanation: The Send button sends the text in the input box to the assistant for processing.
            1.13. Train button
            Explanation: The Train button opens the train function window.
            1.14. Observe button
            Explanation: The Observe button opens the observe function window.
            1.15. Live Fix button
            Explanation: The Live Fix button opens the first live fix window.
            1.16. Advanced Options button
            Explanation: The Advanced Options button opens the advanced options window.
        2. Settings window
            Explanation of the window: The settings window allows you to configure the main interface settings.
        3. Memory management window
            Explanation of the function: The memory management window allows you to view and manage the assistant's memory. The memory corrects, improves and expands the assistant's capabilities and responses over time. There are 4 types of memory: Long-term memory, Short-term memory, Abilities memory and User Preferences memory. Each type of memory has different types of features that are relevant to their function and are useful for different purposes.
        4. Train function window
            Explanation of the function: The train function serves as an intelligent data capture, plan retrieval and learning module designed to facilitate long-term reasoning and planning for the ATLAS system. This function is pivotal in converting user actions into structured knowledge, which ATLAS can use to enhance its decision-making capabilities over time.
        5. Observe function window
            Explanation of the function: The observe function is a advanced observation and analysis system within the ATLAS framework, specifically designed to provide detailed insights into user habits, productivity, health, overall well being and so much more. This system continuously monitors user activity and screen content, processes this data, and generates comprehensive reports that both the users and ATLAS can use.
        7. Advanced options (VM Learn and Agent Framework)

        Available GUI Elements and Actions:

        1. Buttons: Can be clicked
        Action: CLICK
        Parameters: element_name

        2. Textboxes: Can have text set or retrieved
        Actions: SET_TEXT, GET_TEXT
        Parameters: element_name, text (for SET_TEXT only)

        3. Switches: Can be toggled or their state retrieved
        Actions: TOGGLE, GET_STATE
        Parameters: element_name

        4. Option menus: Can have an option selected or the current selection retrieved
        Actions: SELECT_OPTION, GET_SELECTED
        Parameters: element_name, option (for SELECT_OPTION only)

        5. Scrollable frames: Can be scrolled
        Action: SCROLL
        Parameters: element_name, direction (UP or DOWN), amount

        6. Sliders: Can have their value set or retrieved
        Actions: SET_VALUE, GET_VALUE
        Parameters: element_name, value (for SET_VALUE only)

        7. Windows: Can be opened using buttons or closed using the following command
        Actions: CLOSE_WINDOW
        Parameters: window_name


        You will receive the current GUI state, including the active window and its elements. Use this information to provide accurate responses and execute appropriate commands.

        Respond in one of these formats:

        1. For answering questions:
        RESPONSE: [Your answer to the user's question]

        2. For executing a single command:
        COMMAND: [action from the list above]
        PARAMETERS: [element_name] [additional parameters if required]

        3. For multi-step operations:
        STEPS:
        - COMMAND1: [action1]
        PARAMETERS1: [parameters1]
        - COMMAND2: [action2]
        PARAMETERS2: [parameters2]
        ...

        Always consider the current GUI state when formulating your response. If a requested action is not possible given the current state, explain why and suggest alternatives if applicable.

        If you need more information or clarification, ask the user before providing a command or response.
        """

        self.model = genai.GenerativeModel(model_name="gemini-1.5-flash", system_instruction=self.system_prompt)
        self.chat = self.model.start_chat(history=[])

        threading.Thread(target=self.main_loop, daemon=True).start()
    
    def main_loop(self):
        while not self.stopped.is_set():
            try:
                if not self.commands_queue.empty():
                    command = self.commands_queue.get()
                    result = self.process_command(command)
                    if result:
                        self.handle_command_result(result)
                        time.sleep(0.5) # Short delay between commands
            except Exception as e:
                print(f"Error in main_loop: {str(e)}")
                import traceback
                traceback.print_exc()
            time.sleep(0.1)
        
    def start(self):
        self.is_listening = True
        self.listening_thread = threading.Thread(target=self.listen_continuously, daemon=True)
        self.listening_thread.start()

    def stop(self):
        self.is_listening = False
        self.stopped.set()

    def cleanup(self):
        self.stop()
        self.is_shutting_down = True 
        if self.listening_thread:
            self.listening_thread.join(timeout=2)
        self.update_indicator = lambda _: None
        self.update_transcript = lambda _, __: None
        self.update_status_icon = lambda _: None 

    def listen_continuously(self):
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source)
            while not self.stopped.is_set():
                if not self.is_listening:
                    time.sleep(0.1)
                    continue
                try:
                    if hasattr(self, 'is_shutting_down') and self.is_shutting_down:
                        break 
                    self.update_indicator("Listening")
                    self.update_status_icon("listening")
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                    self.update_indicator("Processing")
                    self.update_status_icon("idle")
                    text = self.recognizer.recognize_google(audio)
                    self.update_transcript(text, "User")
                    self.commands_queue.put(text)
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    self.update_transcript("Could not understand audio", "System")
                except Exception as e:
                    if not self.stopped.is_set():
                        self.update_transcript(f"Error: {str(e)}", "System")
            if not hasattr(self, 'is_shutting_down') or not self.is_shutting_down:
                self.update_indicator("Not listening")
                self.update_status_icon("idle")

    def handle_command_result(self, result):
        response = ""
        if result["type"] == "response":
            response = result["content"]
        elif result["type"] == "command":
            response = f"Executing command: {result['command']}. Result: {result['result']}"
        elif result["type"] == "multi_step":
            response = "Executing multiple steps. "
            for step_result in result["results"]:
                response += f"Step: {step_result['command']}, Result: {step_result['result']}. "
        elif result["type"] == "error":
            response = result["message"]
        
        self.speak(response)

    def process_command(self, command):
        if not command:
            return None

        gui_state = self.read_gui_state()
        
        prompt = f"""
        User: {command}

        Current GUI State:
        {gui_state}
        """
        
        try:
            chat_response = self.chat.send_message(
                content=prompt,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )
            response_text = chat_response.text
            self.update_transcript(response_text, "Assistant")
            
            if response_text.startswith("RESPONSE:"):
                response_content = response_text.split(":", 1)[1].strip()
                return {"type": "response", "content": response_content}
            elif response_text.startswith("COMMAND:"):
                command, parameters = self.parse_command(response_text)
                result = self.execute_command(command, parameters)
                return {"type": "command", "command": command, "parameters": parameters, "result": result}
            elif response_text.startswith("STEPS:"):
                steps = self.parse_steps(response_text)
                results = self.execute_multi_step(steps)
                return {"type": "multi_step", "steps": steps, "results": results}
            else:
                error_msg = "I'm sorry, I couldn't generate a valid command. Could you please try again?"
                return {"type": "error", "message": error_msg}
        except Exception as e:
            error_msg = f"Error processing command: {str(e)}"
            self.update_transcript(error_msg, "System")
            return {"type": "error", "message": error_msg}
        
    def read_gui_state(self):
        try:
            with open("window state/gui_state.txt", "r") as f:
                return f.read()
        except FileNotFoundError:
            return "No GUI state available"

    def parse_command(self, response_text):
        lines = response_text.split("\n")
        command = parameters = None
        for line in lines:
            if line.strip().startswith("COMMAND:"):
                command = line.split(":", 1)[1].strip()
            elif line.strip().startswith("PARAMETERS:"):
                parameters = line.split(":", 1)[1].strip()
        return command, parameters

    def parse_steps(self, response_text):
        steps = []
        lines = response_text.split("\n")[1:] 
        current_step = {}
        for line in lines:
            line = line.strip()
            if line.startswith("- COMMAND"):
                if current_step:
                    steps.append(current_step)
                    current_step = {}
                command_num = line.split(":")[0].strip("- COMMAND")
                current_step["command"] = line.split(":", 1)[1].strip()
            elif line.startswith("PARAMETERS"):
                param_num = line.split(":")[0].strip("PARAMETERS")
                if command_num == param_num:
                    current_step["parameters"] = line.split(":", 1)[1].strip()
        if current_step:
            steps.append(current_step)
        return steps
    
    def execute_command(self, command, parameters):
        active_window = get_active_window()
        param_list = parameters.split()
        element_name = param_list[0]

        if command == "CLICK":
            return interact_with_element(active_window, element_name, "click")
        elif command == "SET_TEXT":
            text = " ".join(param_list[1:])
            return interact_with_element(active_window, element_name, "set_text", text=text)
        elif command == "GET_TEXT":
            return interact_with_element(active_window, element_name, "get_text")
        elif command == "TOGGLE":
            return interact_with_element(active_window, element_name, "toggle")
        elif command == "GET_STATE":
            return interact_with_element(active_window, element_name, "get_state")
        elif command == "SELECT_OPTION":
            option = " ".join(param_list[1:])
            return interact_with_element(active_window, element_name, "select_option", option=option)
        elif command == "GET_SELECTED":
            return interact_with_element(active_window, element_name, "get_selected")
        elif command == "SCROLL":
            direction = param_list[1]
            amount = int(param_list[2]) if len(param_list) > 2 else 1
            return interact_with_element(active_window, element_name, "scroll", direction=direction, amount=amount)
        elif command == "CLOSE_WINDOW":
            return gui_manager.close_window(active_window)
        else:
            return f"Unknown command: {command}"

    
    def scroll_canvas(self, window_name: str, element_name: str, direction: str, amount: int = 1):
        if window_name not in self.elements or element_name not in self.elements[window_name]:
            return f"Error: Element '{element_name}' in window '{window_name}' not found."

        element = self.elements[window_name][element_name]
        element_obj = element['object']()
        if element_obj is None:
            return f"Error: Element '{element_name}' in window '{window_name}' no longer exists."

        if hasattr(element_obj, 'yview_scroll'):
            if direction.lower() == 'up':
                element_obj.yview_scroll(-amount, 'units')
            elif direction.lower() == 'down':
                element_obj.yview_scroll(amount, 'units')
            return f"Scrolled {direction} by {amount} units"
        else:
            return f"Element '{element_name}' is not scrollable"

    def execute_multi_step(self, steps):
        results = []
        for step in steps:
            command = step["command"]
            parameters = step["parameters"]
            result = self.execute_command(command, parameters)
            time.sleep(0.5)
            results.append({"command": command, "parameters": parameters, "result": result})
        return results
    
    def speak(self, text):
        self.is_listening = False  
        self.update_indicator("talking")
        self.update_status_icon("talking")
        self.tts_engine.say(text)
        self.tts_engine.runAndWait()
        self.is_listening = True 
        self.update_indicator("idle")
        self.update_status_icon("idle")
