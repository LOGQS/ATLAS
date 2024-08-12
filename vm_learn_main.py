# vm_learn_main.py
import subprocess
import google.generativeai as genai
import json
import time
import os
import threading
from PIL import Image
import io
import tempfile

config_path = 'config/config.json'
with open(config_path, 'r') as config_file:
    config_data = json.load(config_file)


class VMLearning:
    def __init__(self):
        self.vboxmanage_path = os.getenv('VBOXMANAGE_PATH', r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe")
        self.data_dir = r"vm_learn_data"
        self.previous_requests_file = os.path.join(self.data_dir, "previous_requests.json")
        self.ensure_data_directory()
        self.previous_requests = self.load_previous_requests()
        self.gemini_api_key = config_data['api_keys']['GEMINI_API_KEY']
        self.initialize_gemini()
        self.screenshot_thread = None
        self.stop_screenshot = threading.Event()
        self.shared_folder_path = r"vm_share"
        self.config = {
            "gui_settings": {
                "api_key": config_data['api_keys']['GEMINI_API_KEY'],
                "model_selected": config_data['gui_settings']['model_selected'],
                "mode_selected": "efficiency"
            }
        }
    

    def ensure_data_directory(self):
        os.makedirs(self.data_dir, exist_ok=True)
        if not os.path.exists(self.previous_requests_file):
            with open(self.previous_requests_file, 'w') as f:
                json.dump([], f)
    
    def get_shared_folder_path(self):
        return self.shared_folder_path
    
    def execute_training_action(self, action):
        # This method will be called by vm_learn_loop.py to execute actions in the VM
        action_file = os.path.join(self.shared_folder_path, "action.json")
        with open(action_file, 'w') as f:
            json.dump(action, f)
        
        # Will implement a more robust mechanism to check for completion
        time.sleep(1)
        
        result_file = os.path.join(self.shared_folder_path, "result.json")
        if os.path.exists(result_file):
            with open(result_file, 'r') as f:
                result = json.load(f)
            os.remove(result_file)
            return result
        else:
            return {"status": "error", "message": "Action execution failed or timed out"}

    def initialize_gemini(self):
        genai.configure(api_key=self.gemini_api_key)
        self.gemini_model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")
        self.generation_config = genai.types.GenerationConfig(
            temperature=1,
            max_output_tokens=3000,
        )

    def load_previous_requests(self):
        try:
            with open(self.previous_requests_file, 'r') as file:
                return set(json.load(file))
        except json.JSONDecodeError:
            return set()

    def save_previous_requests(self):
        with open(self.previous_requests_file, 'w') as file:
            json.dump(list(self.previous_requests), file)

    def setup_virtual_machine(self, vm_name):
        try:
            if self.is_vm_running(vm_name):
                return {"status": "success", "message": f"VM {vm_name} is already running."}
            else:
                result = subprocess.run([self.vboxmanage_path, "startvm", vm_name, "--type", "headless"], 
                                        capture_output=True, text=True, check=True)
                return {"status": "success", "message": f"VM {vm_name} has been successfully started."}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "message": f"Error: Failed to start VM {vm_name}. {e.stderr.strip()}"}

    def is_vm_running(self, vm_name):
        try:
            result = subprocess.run([self.vboxmanage_path, "showvminfo", vm_name, "--machinereadable"], 
                                    capture_output=True, text=True, check=True)
            for line in result.stdout.splitlines():
                if line.startswith("VMState="):
                    return line.split("=")[1].strip('"') == "running"
            return False
        except subprocess.CalledProcessError:
            return False

    def take_screenshot(self, vm_name):
        if not self.is_vm_running(vm_name):
            return "VM is not running"
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_path = temp_file.name
            
            subprocess.run([self.vboxmanage_path, "controlvm", vm_name, "screenshotpng", temp_path], check=True)
            
            with open(temp_path, "rb") as img_file:
                image = Image.open(io.BytesIO(img_file.read()))
            
            os.unlink(temp_path)
            return image
        except subprocess.CalledProcessError as e:
            return f"Error taking screenshot: {e}"
        except PermissionError:
            return "Permission denied when accessing screenshot file"
        except Exception as e:
            return f"Unexpected error: {e}"

    def generate_user_queries(self, count):
        content = f"""
        -------------------------------
        Important Note: Do not write any of the requests already in the following list: {list(self.previous_requests)}
        -------------------------------
        ALWAYS STRICTLY GENERATE {count} scenarios in which you are the PC user and you have an AI PC assistant that can do tasks using "AVAILABLE FUNCTIONS" for you.
        Some examples would be: send a gmail, open this website, play this song on youtube, etc. Tasks should be achievable. Write them in plain text format.
        While being connected to reality, you should also be creative and try to diversify the requests as much as possible. Be efficient and clear in your requests.
        Imagine yourself in random roles and then write the imaginary requests in the following format. DO NOT WRITE ANYTHING OTHER THAN WHAT IS IN THE FOLLOWING FORMAT.

        CRITICAL NOTES:
        - THE REQUESTS WILL BE HANDLED IN WINDOWS ENVIRONMENT WITH AN INTERNET CONNECTION.
        - THE REQUEST WILL BE HANDLED IN A CLEAN WINDOWS ENVIRONMENT. NO PREVIOUS DATA WILL BE AVAILABLE.
        - THE REQUESTS SHOULD VARY IN COMPLEXITY.
        - THE REQUESTS SHOULD BE CLEAR AND SHOULDN'T BE TOO CASE SPECIFIC.
        - THE REQUESTS SHOULD BE WITHIN THE COMBINED CAPABILITY FUNCTIONS GIVEN IN THE "AVAILABLE FUNCTIONS" SECTION.

        EXAMPLE REQUESTS:
        - A GOOD REQUEST: "Open the browser and search for the latest news."
        - WHY IS IT GOOD: It is clear and easy to understand. Doesn't require any previous context.
        - A BAD REQUEST: "SEND A MAIL TO MY FRIEND."
        - WHY IS IT BAD: It is not clear who the friend is and what the mail should contain. It is too case specific.
        - A GOOD REQUEST: "Create a pdf file on my desktop with a poem written in it. Then create another one with another poem. Then merge them."
        - WHY IS IT GOOD: It is clear and gives a sequence of tasks to be done. It is creative and efficient.
        - A BAD REQUEST: "Send a message to John."
        - WHY IS IT BAD: Who is John? What message should be sent? It is too case specific.
        - A BAD REQUEST: "Find the folder called 'Project' then send the file 'report' to my boss."
        - WHY IS IT BAD: Where did that folder come from? What is the file 'report'? Who is the boss? It isnt possible to do in a clean environment without previous context.

        ONLY WRITE THE FOLLOWING PART IN YOUR ANSWER:
        User_request: [Here you write your request]
        User_request: [Here you write your request]
        ...
        (ALWAYS repeat this format {count} times with different requests)
        """
        response = self.gemini_model.generate_content(content, generation_config=self.generation_config)

        new_requests = response.text.strip().split('\n')

        queries = []
        for request in new_requests:
            if request.startswith("User_request: ") and request[14:] not in self.previous_requests:
                self.previous_requests.add(request[14:])
                queries.append(request)
        
        self.save_previous_requests()
        return queries[:count]

    def set_vm_visibility(self, vm_name, visible):
        if visible:
            self.stop_screenshot.clear()
            self.screenshot_thread = threading.Thread(target=self.continuous_screenshot, args=(vm_name,))
            self.screenshot_thread.start()
            return "VM visibility enabled."
        else:
            if self.screenshot_thread:
                self.stop_screenshot.set()
                self.screenshot_thread.join()
            return "VM visibility disabled."

    def continuous_screenshot(self, vm_name):
        while not self.stop_screenshot.is_set():
            screenshot = self.take_screenshot(vm_name)
            if screenshot:
                pass
            time.sleep(1)

    def process_request(self, request):
        # This is a placeholder for processing user requests
        # In the finished implementation, this will interact with the VM to perform the requested action
        return f"Processing request: {request}"

if __name__ == "__main__":
    vm_learning = VMLearning()