# gui_element_manager.py
import tkinter as tk
from typing import Dict, Any
import weakref
import json
import threading
import os

class GUIElementManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GUIElementManager, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance

    def initialize(self):
        self.windows: Dict[str, weakref.ref] = {}
        self.elements: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.active_window: str = None
        self.print_lock = threading.Lock()
        self.print_scheduled = False
        self.close_callbacks = {}

    def register_window(self, window_name: str, window_object: tk.Tk):
        self.windows[window_name] = weakref.ref(window_object)
        self.elements[window_name] = {}
        self.print_current_state()

    def unregister_window(self, window_name: str):
        if window_name in self.windows:
            del self.windows[window_name]
        if window_name in self.elements:
            del self.elements[window_name]
        if self.active_window == window_name:
            self.active_window = None
        self.print_current_state()

    def get_interaction_options(self, element_type: str) -> list:
        common_options = ['get_info']
        type_specific_options = {
            'button': ['click'],
            'entry': ['set_text', 'get_text'],
            'text': ['set_text', 'get_text'],
            'textbox': ['set_text', 'get_text'],
            'switch': ['toggle', 'get_state'],
            'option_menu': ['select_option', 'get_selected'],
            'frame': [],
            'label': ['get_text'],
        }
        return common_options + type_specific_options.get(element_type, [])

    def set_active_window(self, window_name: str):
        if window_name in self.windows:
            self.active_window = window_name
        self.print_current_state()

    def register_element(self, window_name: str, element_name: str, element_object: Any, element_type: str):
        if window_name not in self.elements:
            return
        
        self.elements[window_name][element_name] = {
            'object': weakref.ref(element_object),
            'type': element_type
        }
        self.schedule_print_current_state()

    def schedule_print_current_state(self):
        if not self.print_scheduled:
            self.print_scheduled = True
            threading.Timer(0.1, self.delayed_print_current_state).start()

    def delayed_print_current_state(self):
        with self.print_lock:
            self.print_current_state()
            self.print_scheduled = False

    def print_current_state(self):
        output = f"Current active window and its elements:\nActive Window: {self.active_window}\n"
        
        if self.active_window:
            output += "Elements:\n"
            elements_info = {name: {'type': info['type']} for name, info in self.elements[self.active_window].items()}
            output += json.dumps(elements_info, indent=2)
        else:
            output += "No active window"
        
        os.makedirs("window state", exist_ok=True)
        with open("window state/gui_state.txt", "w") as f:
            f.write(output)

    def unregister_element(self, window_name: str, element_name: str):
        if window_name in self.elements and element_name in self.elements[window_name]:
            del self.elements[window_name][element_name]

    def get_active_window(self) -> str:
        return self.active_window

    def get_elements(self, window_name: str) -> Dict[str, Dict[str, Any]]:
        return self.elements.get(window_name, {})

    def interact_with_element(self, window_name: str, element_name: str, action: str, **kwargs):
        if window_name not in self.elements or element_name not in self.elements[window_name]:
            return f"Error: Element '{element_name}' in window '{window_name}' not found."

        element = self.elements[window_name][element_name]
        element_obj = element['object']()
        if element_obj is None:
            return f"Error: Element '{element_name}' in window '{window_name}' no longer exists."

        result = None

        if action == 'click' and hasattr(element_obj, 'invoke'):
            element_obj.invoke()
            result = "Button clicked"
        elif action == 'set_text':
            if hasattr(element_obj, 'delete') and hasattr(element_obj, 'insert'):
                element_obj.delete('1.0', tk.END) if element['type'] == 'textbox' else element_obj.delete(0, tk.END)
                element_obj.insert('1.0' if element['type'] == 'textbox' else 0, kwargs.get('text', ''))
                result = f"Text set to: {kwargs.get('text', '')}"
        elif action == 'get_text':
            if hasattr(element_obj, 'get'):
                result = element_obj.get('1.0', tk.END).strip() if element['type'] == 'textbox' else element_obj.get()
        elif action == 'select_option' and hasattr(element_obj, 'set'):
            element_obj.set(kwargs.get('option', ''))
            if hasattr(element_obj, 'cget') and element_obj.cget('command'):
                element_obj.cget('command')(kwargs.get('option', ''))
            result = f"Option selected: {kwargs.get('option', '')}"
        elif action == 'toggle' and hasattr(element_obj, 'toggle'):
            element_obj.toggle()
            if hasattr(element_obj, 'cget') and element_obj.cget('command'):
                element_obj.cget('command')()
            result = "Element toggled"
        elif action == 'get_state' and hasattr(element_obj, 'get'):
            result = element_obj.get()
        elif action == 'get_info':
            result = self.get_element_info(window_name, element_name)
        else:
            result = f"Unsupported action '{action}' for element type '{element['type']}'"

        if window_name == 'settings_window' and element_name in ['theme_menu', 'voice_menu', 'speed_slider']:
            self.update_config(element_name, result)

        return result

    def update_config(self, element_name, value):
        config_path = r"config\config.json"
        with open(config_path, 'r+') as f:
            config = json.load(f)
            if element_name == 'theme_menu':
                config["gui_settings"]["appearance_mode"] = value.lower()
            elif element_name == 'voice_menu':
                config["user_preferences"]["current_voice_name"] = value
            elif element_name == 'speed_slider':
                config["user_preferences"]["tts_rate"] = int(value)
            f.seek(0)
            json.dump(config, f, indent=4)
            f.truncate()
    
    def register_close_callback(self, window_name, callback):
        self.close_callbacks[window_name] = callback

    def close_window(self, window_name: str):
        if window_name in self.windows:
            window = self.windows[window_name]()
            if window:
                if window_name in self.close_callbacks:
                    self.close_callbacks[window_name]()
                else:
                    window.destroy()
                self.unregister_window(window_name)
            return f"Window '{window_name}' closed."
        return f"Window '{window_name}' not found."

    def get_element_info(self, window_name: str, element_name: str) -> Dict[str, Any]:
        if window_name not in self.elements or element_name not in self.elements[window_name]:
            return {}

        element = self.elements[window_name][element_name]
        element_obj = element['object']()
        if element_obj is None:
            return {}

        info = {
            'type': element['type'],
            'state': getattr(element_obj, 'state', lambda: None)(),
        }

        if element['type'] in ['button', 'label', 'entry', 'text']:
            if hasattr(element_obj, 'cget'):
                info['text'] = element_obj.cget('text')
            elif hasattr(element_obj, 'get'):
                info['text'] = element_obj.get()

        return info

    def list_windows(self) -> list:
        return list(self.windows.keys())

    def list_elements(self, window_name: str) -> list:
        return list(self.elements.get(window_name, {}).keys())

gui_manager = GUIElementManager()


def register_window(window_name: str, window_object: tk.Tk):
    gui_manager.register_window(window_name, window_object)

def register_element(window_name: str, element_name: str, element_object: Any, element_type: str):
    gui_manager.register_element(window_name, element_name, element_object, element_type)

def set_active_window(window_name: str):
    gui_manager.set_active_window(window_name)

def get_active_window() -> str:
    return gui_manager.get_active_window()

def list_windows() -> list:
    return gui_manager.list_windows()

def list_elements(window_name: str) -> list:
    return gui_manager.list_elements(window_name)

def interact_with_element(window_name: str, element_name: str, action: str, **kwargs):
    return gui_manager.interact_with_element(window_name, element_name, action, **kwargs)

def get_element_info(window_name: str, element_name: str) -> Dict[str, Any]:
    return gui_manager.get_element_info(window_name, element_name)

def get_interaction_options(element_type: str) -> list:
    return gui_manager.get_interaction_options(element_type)