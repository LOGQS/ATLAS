# vm_action_executor.py

import json
import os
import time
import pyautogui
import subprocess
import shutil
import winreg
import psutil
import cv2
import soundfile as sf
import win32gui
import win32con
import win32api
import ctypes
import logging

# Setup logging
logging.basicConfig(filename='vm_action_executor.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Shared folder path
SHARED_FOLDER_PATH = "Z:\\action.json"

def execute_cmd(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return {"status": "success", "output": result.stdout, "error": result.stderr}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def create_file(path, content=''):
    try:
        with open(path, 'w') as f:
            f.write(content)
        return {"status": "success", "message": f"File created at {path}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def read_file(path):
    try:
        with open(path, 'r') as f:
            content = f.read()
        return {"status": "success", "content": content}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Will include all other functions from command_execution.py here

def execute_action(action):
    action_type = action.get("action_type")
    if action_type == "command_execution":
        return execute_cmd(action["command"])
    elif action_type == "file_operation":
        if action["operation"] == "create":
            return create_file(action["path"], action.get("content", ""))
        elif action["operation"] == "read":
            return read_file(action["path"])
    elif action_type == "gui_automation":
        if action["operation"] == "click":
            pyautogui.click(x=action["x"], y=action["y"], button=action["button"])
        elif action["operation"] == "type":
            pyautogui.typewrite(action["text"])
        elif action["operation"] == "keypress":
            pyautogui.press(action["key"])

def main():
    while True:
        if os.path.exists(SHARED_FOLDER_PATH):
            try:
                with open(SHARED_FOLDER_PATH, 'r') as file:
                    action = json.load(file)
                result = execute_action(action)
                logging.info(f"Action executed: {action}, Result: {result}")
                with open(SHARED_FOLDER_PATH, 'w') as file:
                    json.dump(result, file)
            except Exception as e:
                logging.error(f"Error executing action: {str(e)}")
            finally:
                os.remove(SHARED_FOLDER_PATH)
        time.sleep(1)

if __name__ == "__main__":
    main()