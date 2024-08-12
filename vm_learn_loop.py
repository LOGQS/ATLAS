# vm_learn_loop
import os
import json
import asyncio
from main_assistant import MainAssistant
from memory_main import MemoryManager
import google.generativeai as genai

VM_LEARN_DATA_PATH = "vm_learn_data"
VM_LEARN_MEMORY_PATH = os.path.join(VM_LEARN_DATA_PATH, "memory_data")
SHARED_FOLDER_PATH = "vm_share"


class VMLearningLoop:
    def __init__(self, vm_learning):
        self.vm_learning = vm_learning
        self.config = vm_learning.config
        self.main_assistant = MainAssistant(self.config)
        self.vm_learn_memory = MemoryManager()
        self.vm_learn_memory.set_memory_path(VM_LEARN_MEMORY_PATH)
        self.user_agent = self.initialize_user_agent()
        self.user_agent_chat = None
        self.training_in_progress = False
        self.stop_requested = False
        self.current_request_index = 0
        self.training_requests = []

    def initialize_user_agent(self):
        return genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            generation_config={
                "temperature": 1,
                "top_p": 1,
                "top_k": 1,
                "max_output_tokens": 2000,
            }
        )

    async def start_training(self, training_requests):
        if self.training_in_progress:
            return {"status": "error", "message": "Training already in progress"}

        self.training_requests = training_requests
        self.current_request_index = 0
        self.training_in_progress = True
        self.stop_requested = False

        return await self.process_next_request()

    async def stop_training(self):
        if not self.training_in_progress:
            return {"status": "error", "message": "No training in progress"}

        self.stop_requested = True
        return {"status": "success", "message": "Stop request received"}

    async def process_next_request(self):
        if self.stop_requested or self.current_request_index >= len(self.training_requests):
            self.training_in_progress = False
            return {"status": "completed", "message": "Training completed or stopped"}

        self.main_assistant.reset_chat_history()
        self.user_agent_chat = self.user_agent.start_chat(history=[])

        current_request = self.training_requests[self.current_request_index]
        response = await self.main_assistant.process_user_request(current_request)
        
        while not self.stop_requested and not self.is_request_completed(response):
            user_response = await self.get_user_agent_response(response)
            response = await self.main_assistant.process_user_request(user_response)
            await self.execute_action(response)

        if not self.stop_requested:
            await self.process_memory(response)

        self.current_request_index += 1
        return await self.process_next_request()

    def is_request_completed(self, response):
        parsed_response = self.main_assistant.parse_json_response(response)
        return parsed_response.get("user_request_fully_finished", False)

    async def get_user_agent_response(self, main_assistant_response):
        parsed_response = self.main_assistant.parse_json_response(main_assistant_response)
        response_to_user = parsed_response.get("response_to_user", "")

        user_agent_prompt = f"""
        You are simulating a user interacting with an AI assistant in a virtual machine environment. 
        The assistant's last response was:

        {response_to_user}

        Please provide a natural and contextually appropriate response to continue the conversation.
        Your response should aim to progress the task towards completion within the VM environment.

        Response format:
        {{
            "user_response": "Your simulated user response here"
        }}
        """

        user_agent_response = await self.user_agent_chat.send_message_async(user_agent_prompt)
        parsed_user_response = self.main_assistant.parse_json_response(user_agent_response.text)
        
        return parsed_user_response["user_response"]

    async def execute_action(self, response):
        parsed_response = self.main_assistant.parse_json_response(response)
        action = parsed_response.get("action", {})
        if action:
            self.write_action_to_shared_folder(action)
            # Wait for the action to be executed by vm_action_executor.py
            await asyncio.sleep(1)
            
    def write_action_to_shared_folder(self, action):
        with open(SHARED_FOLDER_PATH, 'w') as f:
            json.dump(action, f)

    async def process_memory(self, response):
        memory_content = {
            "request": self.training_requests[self.current_request_index],
            "conversation": self.main_assistant.get_chat_history(),
            "final_response": response
        }
        self.vm_learn_memory.append_to_full_memory("TRAINING_COMPLETION", json.dumps(memory_content))
        await self.vm_learn_memory.process_memory()

    def get_training_status(self):
        return {
            "in_progress": self.training_in_progress,
            "current_index": self.current_request_index,
            "total_requests": len(self.training_requests),
            "stop_requested": self.stop_requested
        }