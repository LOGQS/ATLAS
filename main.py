# main.py
from chat_interface import ChatInterface
import subprocess
import sys

class ApplicationManager:
    def __init__(self):
        self.chat_interface = None
        self.agent_framework_process = None

    def start_chat_interface(self):
        self.chat_interface = ChatInterface({})  
        self.chat_interface.open_agent_framework = self.switch_to_agent_framework
        self.chat_interface.root.protocol("WM_DELETE_WINDOW", self.exit_application)
        self.chat_interface.root.mainloop()

    def switch_to_agent_framework(self):
        if self.chat_interface:
            self.chat_interface.root.destroy()
            self.chat_interface = None
        
        self.agent_framework_process = subprocess.Popen([sys.executable, 'ag_main.py'])
        self.agent_framework_process.wait()
        self.start_chat_interface()

    def exit_application(self):
        if self.agent_framework_process:
            self.agent_framework_process.terminate()
        if self.chat_interface:
            self.chat_interface.on_closing()
        sys.exit()

    def run(self):
        self.start_chat_interface()

if __name__ == "__main__":
    app_manager = ApplicationManager()
    app_manager.run()