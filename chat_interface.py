# chat_interface.py
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from customtkinter import CTkImage
from PIL import Image
import logging
import threading
import queue
import os
import sys
import time
import asyncio
import speech_recognition as sr
import pyttsx3
import mimetypes
from main_assistant import MainAssistant
from train_function import start_recording, stop_recording
from observe_func_rec import start_recording as start_observe_recording, stop_recording as stop_observe_recording, get_recording_count
from observe_func_sum import process_next_video, get_summarizing_status
from ag_main import *
from memory_gui import MemoryGUI
from memory_main import MemoryManager
from live_fix import LiveFixAssistant
from vm_learn_gui import VMLearningGUI
from speech_control import SpeechControl
from gui_element_manager import register_window, register_element, set_active_window, gui_manager
from ag_canvas import execute_workflow_in_environment, choose_execution_environment
from typing import Any
import shutil   
from screen_capture import ScreenCaptureOverlay
import tempfile

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class ChatInterface:
    CONFIG_PATH = r"config\config.json"
    DEFAULT_CONFIG = {
        "api_keys": {
            "GEMINI_API_KEY": "your_api_key_here"
        },
        "gui_settings": {
            "appearance_mode": "dark",
            "tts_enabled": False,
            "model_selected": "gemini-1.5-pro",
            "memory_enabled": False,
            "mode_selected": "safe"
        },
        "user_preferences": {
            "current_voice": "default_voice_id",
            "current_voice_name": "Default",
            "tts_rate": 150,
        }
    }

    def __init__(self, config=None, parent=None):
        self.config = config if config else self.load_config()
        self.parent = parent
        self.root = ctk.CTk() if parent is None else ctk.CTkToplevel(parent)
        register_window("main_window", self.root)
        self.root.bind("<FocusIn>", self.on_main_window_focus)
        self.root.title("ATLAS")
        self.root.geometry("1300x800")
        self.msg_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.load_api_key()
        self.main_assistant = MainAssistant(self.config)
        self.main_assistant.set_update_plan_callback(self.update_plan_bubble)
        self.main_assistant.update_external_knowledge()
        self.active_window = None
        self.is_processing = False
        self.train_status = tk.StringVar(value="Status: Not recording")
        self.observing = False
        self.rec_thread = None
        self.sum_thread = None
        self.observation_active = False
        self.stop_requested = False
        self.start_but_train = "normal"
        self.stop_but_train = "disabled"
        self.start_but_observe = "normal"
        self.stop_but_observe = "disabled"
        self.is_listening = False
        self.recognizer = sr.Recognizer()
        self.mic_thread = None
        self.tts_engine = pyttsx3.init()
        self.tts_enabled = self.config["gui_settings"]["tts_enabled"]
        self.tts_voice = self.config["user_preferences"]["current_voice"]
        self.tts_rate = self.config["user_preferences"]["tts_rate"]
        self.tts_in_progress = False
        self.tts_thread = None
        self.tts_stop_event = threading.Event()  
        self.current_voice = self.tts_voice
        self.voice_var = None  
        self.current_voice_name = self.get_current_voice_name()
        self.uploaded_files = []
        self.file_upload_queue = []
        self.file_icons = []
        self.file_upload_in_progress = False
        self.upload_cancellation_events = {}
        self.upload_tasks = {}  
        self.memory_window = None
        self.memory_manager = MemoryManager()
        self.memory_enabled = self.config["gui_settings"]["memory_enabled"]
        self.live_fix_assistant = None
        self.live_fix_window = None
        self.live_fix_initial_window = None
        self.live_fix_main_window = None
        self.live_fix_file_icons = []
        self.live_fix_file_upload_queue = []
        self.live_fix_file_icon_area = None
        self.vm_learn_window = None
        self.speech_control_window = None
        self.speech_control = None

        self.file_icon_image = CTkImage(light_image=Image.open(r"imgs\\file_icon.png"), 
                                        dark_image=Image.open(r"imgs\\file_icon.png"), 
                                        size=(20, 20))
        self.delete_icon_image = CTkImage(light_image=Image.open(r"imgs\\delete_icon.png"), 
                                        dark_image=Image.open(r"imgs\\delete_icon.png"), 
                                        size=(15, 15))
        
        # Set TTS voice and rate
        self.tts_engine.setProperty('voice', self.tts_voice)
        self.tts_engine.setProperty('rate', self.tts_rate)

        # Create an event loop in a separate thread
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self.run_async_loop, daemon=True)
        self.loop_thread.start()
        
        self.create_gui()
        self.root.after(100, self.process_queue)

        set_active_window("main_window")

        # Set initial states for switches and other settings
        self.tts_var.set(self.tts_enabled)
        self.memory_var.set(self.memory_enabled)
        self.mode_var.set(self.config["gui_settings"]["mode_selected"] == "efficiency")
        self.model_var.set(self.config["gui_settings"]["model_selected"])

        self.update_send_button_state()
        self.voice_var = ctk.StringVar(value=self.config["user_preferences"]["current_voice_name"])

        self.register_close_callbacks()

    def register_close_callbacks(self):
        gui_manager.register_close_callback("memory_window", self.close_memory_window)
        gui_manager.register_close_callback("live_fix_initial_window", self.close_active_window)
        gui_manager.register_close_callback("live_fix_main_window", self.close_live_fix)
        gui_manager.register_close_callback("execute_workflow_window", self.close_active_window)
        gui_manager.register_close_callback("settings_window", self.close_active_window)
        gui_manager.register_close_callback("advanced_options_window", self.close_active_window)
        gui_manager.register_close_callback("train_window", self.close_active_window)
        gui_manager.register_close_callback("observe_window", self.close_observe_window)

    def load_config(self):
        if os.path.exists(self.CONFIG_PATH):
            with open(self.CONFIG_PATH, 'r') as file:
                return json.load(file)
        else:
            return self.DEFAULT_CONFIG

    def save_config(self):
        with open(self.CONFIG_PATH, 'w') as file:
            json.dump(self.config, file, indent=4)

    def load_api_key(self):
        api_key = self.config["api_keys"].get("GEMINI_API_KEY", "your_api_key_here")
        if api_key == "your_api_key_here":
            self.prompt_for_api_key()
        else:
            os.environ["GEMINI_API_KEY"] = api_key

    def prompt_for_api_key(self):
        api_key = tk.simpledialog.askstring("API Key Required", "Please enter your GEMINI API Key:")
        if api_key:
            self.config["api_keys"]["GEMINI_API_KEY"] = api_key
            self.save_config()
            os.environ["GEMINI_API_KEY"] = api_key
        else:
            messagebox.showerror("API Key Required", "An API key is required to proceed.")
            self.root.destroy()
    
    def on_main_window_focus(self, event):
        if not self.active_window:
            set_active_window("main_window")

    def run_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def create_gui(self):
        ctk.set_appearance_mode(self.config["gui_settings"]["appearance_mode"])
        ctk.set_default_color_theme("blue")

        self.title_bar = self.create_title_bar()
        register_element("main_window", "title_bar", self.title_bar, "frame")
        
        self.main_frame = self.create_main_content()
        register_element("main_window", "main_content", self.main_frame, "frame")
        
        self.footer_frame = self.create_footer()
        register_element("main_window", "footer", self.footer_frame, "frame")
        
        self.settings_button = self.create_settings_button()
        register_element("main_window", "settings_button", self.settings_button, "button")


    def create_title_bar(self):
        title_bar = ctk.CTkFrame(self.root, height=40)
        title_bar.pack(fill=tk.X)

        icon_image = Image.open("imgs/app_icon_inverted.png")
        
        icon_ctk_image = ctk.CTkImage(light_image=icon_image, dark_image=icon_image, size=(40, 40))

        title_icon_label = ctk.CTkLabel(title_bar, image=icon_ctk_image, text="")
        title_icon_label.pack(side=tk.LEFT, padx=40)

        self.reset_chat_button = ctk.CTkButton(
            title_bar,
            text="Reset Chat",
            font=("Helvetica", 12),
            command=self.reset_chat,
            width=100,
            height=30
        )
        self.reset_chat_button.pack(side=tk.RIGHT, padx=60, pady=10)
        register_element("main_window", "reset_chat_button", self.reset_chat_button, "button")
        
        return title_bar
    
    def reset_chat(self):
        confirm = messagebox.askyesno("Confirm Reset", "Are you sure you want to reset the chat? This action cannot be undone.")
        if confirm:
            logging.info("Chat reset confirmed by user")
            if MemoryManager.memory_enabled:
                chat_history_str = self.main_assistant.get_chat_history_as_string()
                logging.info(f"Appending chat history to memory. Length: {len(chat_history_str)}")
                self.memory_manager.append_to_full_memory("CHAT LOGS", chat_history_str)
            try:
                self.main_assistant.reset_chat_history()
                for widget in self.messages_frame.winfo_children():
                    widget.destroy()
                self.chat_display._parent_canvas.yview_moveto(0.0)
                self.chat_display._parent_canvas.update_idletasks()
                self.stop_tts(force=True)
                self.tts_in_progress = False
                self.display_message("Chat has been reset.", "system")
                self.root.after(2000, lambda: self.remove_message("system"))
                logging.info("Chat reset successful")
            except Exception as e:
                error_message = f"Error resetting chat: {str(e)}"
                logging.error(error_message)
                messagebox.showerror("Reset Error", error_message)

    def remove_message(self, sender):
        def delayed_remove():
            for widget in self.messages_frame.winfo_children():
                if hasattr(widget, 'winfo_children') and widget.winfo_children():
                    first_child = widget.winfo_children()[0]
                    if isinstance(first_child, ctk.CTkLabel):
                        if first_child.cget("text") in ["Chat has been reset.", "Text-to-Speech enabled", "Text-to-Speech disabled"]:
                            widget.destroy()
                            break
        self.root.after(100, delayed_remove)

    def create_main_content(self):
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

        left_frame = ctk.CTkFrame(main_frame, width=200)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.create_left_sidebar(left_frame)

        right_frame = ctk.CTkFrame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.create_chat_area(right_frame)
        self.create_input_area(right_frame)

        return main_frame

    def create_left_sidebar(self, parent):
        # Model selection
        model_label = ctk.CTkLabel(parent, text="Model:")
        model_label.pack(pady=(10, 5))
        self.model_var = ctk.StringVar(value=self.config["gui_settings"]["model_selected"])
        model_menu = ctk.CTkOptionMenu(parent, variable=self.model_var, 
                                    values=["gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.0-pro"],
                                    command=self.change_model)
        model_menu.pack(pady=(0, 10))
        register_element("main_window", "model_menu", model_menu, "option_menu")

        # Text-to-Speech toggle
        self.tts_var = ctk.BooleanVar(value=self.config["gui_settings"]["tts_enabled"])
        self.tts_switch = ctk.CTkSwitch(parent, text="Text-to-Speech", variable=self.tts_var, 
                                        command=self.toggle_tts)
        self.tts_switch.pack(pady=10)
        register_element("main_window", "tts_switch", self.tts_switch, "switch")

        # Safe/Efficiency mode switch
        self.mode_var = ctk.BooleanVar(value=self.config["gui_settings"]["mode_selected"] == "efficiency")
        mode_switch = ctk.CTkSwitch(parent, text="Safe/Efficiency Mode", variable=self.mode_var, 
                                    command=self.toggle_mode)
        mode_switch.pack(pady=10)
        register_element("main_window", "mode_switch", mode_switch, "switch")

        # Memory switch
        self.memory_var = ctk.BooleanVar(value=self.config["gui_settings"]["memory_enabled"])
        memory_switch = ctk.CTkSwitch(parent, text="Enable Memory", variable=self.memory_var, 
                                    command=self.toggle_memory)
        memory_switch.pack(pady=10)
        register_element("main_window", "memory_switch", memory_switch, "switch")

        # Memory button
        memory_button = ctk.CTkButton(parent, text="Open Memory", command=self.open_memory_gui)
        memory_button.pack(pady=10)
        register_element("main_window", "memory_button", memory_button, "button")
        
        # External Knowledge button
        external_knowledge_button = ctk.CTkButton(parent, text="External Knowledge", command=self.open_external_knowledge_window)
        external_knowledge_button.pack(pady=10)
        register_element("main_window", "external_knowledge_button", external_knowledge_button, "button")

        # Add the Execute Workflow button
        execute_workflow_button = ctk.CTkButton(parent, text="Execute Workflow", command=self.open_execute_workflow_window)
        execute_workflow_button.pack(pady=10)
        register_element("main_window", "execute_workflow_button", execute_workflow_button, "button")

        # Add the new Speech Control button
        speech_control_button = ctk.CTkButton(parent, text="Speech Control", command=self.open_speech_control)
        speech_control_button.pack(pady=10)
        register_element("main_window", "speech_control_button", speech_control_button, "button")

        # Microphone button
        mic_image = Image.open(r"imgs\\microphone_icon.png")
        mic_ctk_image = CTkImage(light_image=mic_image, dark_image=mic_image, size=(30, 30))
        self.mic_button = ctk.CTkButton(parent, image=mic_ctk_image, text="", width=30, height=30, 
                                        command=self.toggle_microphone)
        self.mic_button.pack(pady=10)
        register_element("main_window", "mic_button", self.mic_button, "button")

        # Indicator light
        self.indicator_canvas = tk.Canvas(parent, width=10, height=10, bg="#2b2b2b", highlightthickness=0)
        self.indicator_light = self.indicator_canvas.create_oval(2, 2, 8, 8, fill="red")
        self.indicator_canvas.pack(pady=5)

    def create_chat_area(self, parent):
        chat_frame = ctk.CTkFrame(parent)
        chat_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 10))

        self.chat_display = ctk.CTkScrollableFrame(chat_frame, fg_color="#2b2b2b")
        self.chat_display.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        register_element("main_window", "chat_display", self.chat_display, "scrollable_frame")

        self.messages_frame = ctk.CTkFrame(self.chat_display, fg_color="#2b2b2b")
        self.messages_frame.pack(expand=True, fill=tk.BOTH)
        register_element("main_window", "messages_frame", self.messages_frame, "frame")

    def create_input_area(self, parent):
        input_frame = ctk.CTkFrame(parent)
        input_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 10))

        # Area for file icons
        self.file_icon_area = ctk.CTkFrame(input_frame, fg_color="transparent")

        # Input box and buttons
        input_box_frame = ctk.CTkFrame(input_frame)
        input_box_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.user_input = ctk.CTkTextbox(input_box_frame, font=("Helvetica", 12), height=40)
        self.user_input.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(10, 5), pady=10)
        self.user_input.bind("<Return>", self.send_message)
        self.user_input.bind("<Shift-Return>", self.new_line)
        register_element("main_window", "user_input", self.user_input, "textbox")

        self.send_button = ctk.CTkButton(input_box_frame, text="Send", command=self.send_message)
        self.send_button.pack(side=tk.RIGHT, padx=(5, 10), pady=10)
        register_element("main_window", "send_button", self.send_button, "button")

        file_image = Image.open(r"imgs\\add_file_icon.png")
        file_ctk_image = CTkImage(light_image=file_image, dark_image=file_image, size=(30, 30))
        self.file_button = ctk.CTkButton(input_box_frame, image=file_ctk_image, text="", width=30, height=30, 
                                        command=self.open_file_dialog)
        self.file_button.pack(side=tk.RIGHT, padx=5, pady=10)
        register_element("main_window", "file_button", self.file_button, "button")

    def update_file_button_state(self, model_name):
        if model_name == "gemini-1.0-pro":
            self.file_button.configure(state="disabled")
        else:
            self.file_button.configure(state="normal")

    def toggle_memory(self):
        MemoryManager.set_memory_enabled(self.memory_var.get())
        self.config["gui_settings"]["memory_enabled"] = MemoryManager.memory_enabled
        self.save_config()
        if MemoryManager.memory_enabled:
            print("Memory system enabled")
        else:
            print("Memory system disabled")

    def process_memory(self):
        if MemoryManager.memory_enabled:
            threading.Thread(target=self.memory_manager.process_memory, daemon=True).start()
    
    def open_memory_gui(self):
        if self.memory_window is not None:
            self.memory_window.lift()
            return

        self.memory_window = ctk.CTkToplevel(self.root)
        register_window("memory_window", self.memory_window)
        self.memory_window.bind("<FocusIn>", lambda e: set_active_window("memory_window"))
        self.memory_window.title("Memory Manager")
        self.memory_window.geometry("900x700")
        self.memory_window.protocol("WM_DELETE_WINDOW", self.close_memory_window)
        self.memory_window.transient(self.root)
        self.memory_window.grab_set()

        MemoryGUI(self.memory_window, self.close_memory_window)

    def close_memory_window(self):
        if self.memory_window:
            self.memory_window.grab_release()
            self.memory_window.destroy()
            gui_manager.unregister_window("memory_window")
            self.memory_window = None
            set_active_window("main_window")
    
    def open_external_knowledge_window(self):
        if hasattr(self, 'external_knowledge_window') and self.external_knowledge_window.winfo_exists():
            self.external_knowledge_window.lift()
            return

        self.external_knowledge_window = ctk.CTkToplevel(self.root)
        self.external_knowledge_window.title("External Knowledge")
        self.external_knowledge_window.geometry("400x500")
        self.external_knowledge_window.protocol("WM_DELETE_WINDOW", self.close_external_knowledge_window)
        self.external_knowledge_window.transient(self.root)
        self.external_knowledge_window.grab_set()

        frame = ctk.CTkFrame(self.external_knowledge_window)
        frame.pack(padx=20, pady=20, fill="both", expand=True)

        ctk.CTkButton(frame, text="Train Data", command=lambda: self.handle_external_knowledge("train")).pack(pady=10)
        ctk.CTkButton(frame, text="Observe Data", command=lambda: self.handle_external_knowledge("observe")).pack(pady=10)
        ctk.CTkButton(frame, text="External File", command=lambda: self.handle_external_knowledge("external")).pack(pady=10)

        self.external_knowledge_switch = ctk.CTkSwitch(frame, text="Enable External Knowledge", command=self.toggle_external_knowledge)
        self.external_knowledge_switch.pack(pady=10)

        self.external_knowledge_list = ctk.CTkTextbox(frame, height=200, state="disabled")
        self.external_knowledge_list.pack(fill=tk.BOTH, expand=True, pady=10)
        self.external_knowledge_list.bind("<Double-1>", self.remove_external_knowledge)

        self.load_external_knowledge_config()
        self.update_external_knowledge_list()
        self.clean_knowledge_folder()

    def close_external_knowledge_window(self):
        if hasattr(self, 'external_knowledge_window'):
            self.external_knowledge_window.grab_release()
            self.external_knowledge_window.destroy()
            delattr(self, 'external_knowledge_window')

    def handle_external_knowledge(self, knowledge_type):
        config_dir = os.path.join(os.path.dirname(__file__), "config")
        knowledge_dir = os.path.join(config_dir, "external_knowledge")
        os.makedirs(knowledge_dir, exist_ok=True)
        config_file = os.path.join(config_dir, "knowledge.json")

        if not os.path.exists(config_file):
            with open(config_file, 'w') as f:
                json.dump({"train": {"enabled": False},
                        "observe": {"enabled": False},
                        "enabled": False}, f)

        with open(config_file, 'r+') as f:
            config = json.load(f)

            if knowledge_type in ["train", "observe"]:
                config[knowledge_type]["enabled"] = not config[knowledge_type]["enabled"]
                messagebox.showinfo("External Knowledge", f"{knowledge_type.capitalize()} data {'enabled' if config[knowledge_type]['enabled'] else 'disabled'}.")
            elif knowledge_type == "external":
                file_path = filedialog.askopenfilename(filetypes=[("Supported files", "*.txt *.pdf *.docx"), ("All files", "*.*")])
                if file_path:
                    file_name = os.path.basename(file_path)
                    if self.validate_file_type(file_name):
                        dest_path = os.path.join(knowledge_dir, file_name)
                        try:
                            shutil.copy2(file_path, dest_path)
                            messagebox.showinfo("External Knowledge", f"File '{file_name}' added to external knowledge.")
                        except Exception as e:
                            messagebox.showerror("Error", f"Failed to copy file: {str(e)}")
                    else:
                        messagebox.showerror("Error", "Unsupported file type. Please use .txt, .pdf, or .docx files.")

            f.seek(0)
            json.dump(config, f, indent=4)
            f.truncate()

        self.update_external_knowledge_list()
        self.main_assistant.update_external_knowledge()
    
    def validate_file_type(self, file_name):
        return file_name.lower().endswith(('.txt', '.pdf', '.docx'))

    def clean_knowledge_folder(self):
        knowledge_dir = os.path.join(os.path.dirname(__file__), "config", "external_knowledge")
        for file in os.listdir(knowledge_dir):
            if not self.validate_file_type(file):
                file_path = os.path.join(knowledge_dir, file)
                try:
                    os.remove(file_path)
                    print(f"Removed unsupported file: {file}")
                except Exception as e:
                    print(f"Failed to remove file {file}: {str(e)}")

    def toggle_external_knowledge(self):
        config_file = os.path.join(os.path.dirname(__file__), "config", "knowledge.json")
        with open(config_file, 'r+') as f:
            config = json.load(f)
            config["enabled"] = self.external_knowledge_switch.get()
            f.seek(0)
            json.dump(config, f, indent=4)
            f.truncate()
        self.update_external_knowledge_list()
        self.main_assistant.update_external_knowledge()

    def load_external_knowledge_config(self):
        config_file = os.path.join(os.path.dirname(__file__), "config", "knowledge.json")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                self.external_knowledge_switch.select() if config.get("enabled", False) else self.external_knowledge_switch.deselect()

    def update_external_knowledge_list(self):
        config_file = os.path.join(os.path.dirname(__file__), "config", "knowledge.json")
        knowledge_dir = os.path.join(os.path.dirname(__file__), "config", "external_knowledge")
        self.external_knowledge_list.configure(state="normal")
        self.external_knowledge_list.delete("1.0", tk.END)
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            if config["train"]["enabled"]:
                self.external_knowledge_list.insert(tk.END, "Train Data:\n- ability_memory.json\n\n")
            if config["observe"]["enabled"]:
                self.external_knowledge_list.insert(tk.END, "Observe Data:\n- observed_summary.txt\n\n")
            
            self.external_knowledge_list.insert(tk.END, "External Files:\n")
            for file in os.listdir(knowledge_dir):
                if file.lower().endswith(('.txt', '.pdf', '.docx')):
                    self.external_knowledge_list.insert(tk.END, f"- {file}\n")
            
            if not config.get("enabled", False):
                self.external_knowledge_list.insert(tk.END, "\nNote: External Knowledge is currently disabled.")
        else:
            self.external_knowledge_list.insert(tk.END, "External Knowledge configuration not found.")
        self.external_knowledge_list.configure(state="disabled")

    def remove_external_knowledge(self, event):
        index = self.external_knowledge_list.index(f"@{event.x},{event.y}")
        line_start = self.external_knowledge_list.index(f"{index} linestart")
        line_end = self.external_knowledge_list.index(f"{index} lineend")
        line = self.external_knowledge_list.get(line_start, line_end).strip()

        if line.startswith("-"):
            file_to_remove = line[1:].strip()
            if file_to_remove not in ["ability_memory.json", "observed_summary.txt"]:
                if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete {file_to_remove}?"):
                    knowledge_dir = os.path.join(os.path.dirname(__file__), "config", "external_knowledge")
                    file_path = os.path.join(knowledge_dir, file_to_remove)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        messagebox.showinfo("File Deleted", f"{file_to_remove} has been deleted.")
                        self.update_external_knowledge_list()
                        self.main_assistant.update_external_knowledge()
                    else:
                        messagebox.showerror("Error", f"File {file_to_remove} not found.")
            else:
                messagebox.showinfo("Info", "Train and Observe data cannot be deleted. Use the toggle buttons to enable/disable them.")
    
    def open_execute_workflow_window(self):
        if self.active_window:
            self.active_window.lift()
            return

        self.active_window = ctk.CTkToplevel(self.root)
        register_window("execute_workflow_window", self.active_window)
        self.active_window.bind("<FocusIn>", lambda e: set_active_window("execute_workflow_window"))
        self.active_window.title("Execute Workflow")
        self.active_window.geometry("400x200")
        self.active_window.protocol("WM_DELETE_WINDOW", self.close_active_window)
        self.active_window.transient(self.root)
        self.active_window.grab_set()

        frame = ctk.CTkFrame(self.active_window)
        frame.pack(padx=20, pady=20, fill="both", expand=True)

        label = ctk.CTkLabel(frame, text="Select a workflow:")
        label.pack(pady=(0, 10))

        workflows = self.get_saved_workflows()
        self.workflow_var = ctk.StringVar(value=workflows[0] if workflows else "")
        workflow_dropdown = ctk.CTkOptionMenu(frame, variable=self.workflow_var, values=workflows)
        workflow_dropdown.pack(pady=(0, 20))

        execute_button = ctk.CTkButton(frame, text="Execute", command=self.execute_selected_workflow)
        execute_button.pack()

        register_element("execute_workflow_window", "workflow_dropdown", workflow_dropdown, "option_menu")
        register_element("execute_workflow_window", "execute_button", execute_button, "button")

    def get_saved_workflows(self):
        workflows_dir = r'agent_gen\saved_workflows'
        workflows = [f.split('.')[0] for f in os.listdir(workflows_dir) if f.endswith('.json')]
        return workflows

    def execute_selected_workflow(self):
        selected_workflow = self.workflow_var.get()
        if not selected_workflow:
            messagebox.showerror("Error", "Please select a workflow.")
            return

        self.close_active_window()

        venv_path = choose_execution_environment(self.root)
        if venv_path is None:
            return

        workflow_file = os.path.join(r'agent_gen\saved_workflows', f"{selected_workflow}.json")
        with open(workflow_file, 'r', encoding='utf-8') as f:
            workflow_data = json.load(f)

        output_window = ctk.CTkToplevel(self.root)
        output_window.title("Workflow Execution")
        output_window.geometry("800x600")

        output_text = ctk.CTkTextbox(output_window, wrap="word")
        output_text.pack(expand=True, fill="both", padx=10, pady=10)

        def update_output(text):
            output_text.insert("end", text + "\n")
            output_text.see("end")
            output_text.update()

        threading.Thread(target=lambda: execute_workflow_in_environment(workflow_data, update_output, venv_path), daemon=True).start()


    def toggle_microphone(self):
        if not self.is_listening:
            self.start_listening()
        else:
            self.stop_listening()

    def start_listening(self):
        self.is_listening = True
        self.mic_button.configure(fg_color="#3a7ebf")
        self.indicator_canvas.itemconfig(self.indicator_light, fill="green")
        self.mic_thread = threading.Thread(target=self.listen_for_speech)
        self.mic_thread.daemon = True
        self.mic_thread.start()

    def stop_listening(self):
        self.is_listening = False
        self.mic_button.configure(fg_color="#1f538d")
        self.indicator_canvas.itemconfig(self.indicator_light, fill="red")

    def listen_for_speech(self):
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source)
            while self.is_listening:
                try:
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=10)
                    text = self.recognizer.recognize_google(audio)
                    self.root.after(0, self.update_chat_input, text)
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    print(f"Could not request results; {e}")
                except Exception as e:
                    print(f"Error in speech recognition: {e}")

    def update_chat_input(self, text):
        current_text = self.user_input.get("1.0", tk.END).strip()
        if current_text:
            self.user_input.insert(tk.END, " " + text)
        else:
            self.user_input.insert(tk.END, text)
        self.user_input.see(tk.END)

    def create_footer(self):
        footer_frame = ctk.CTkFrame(self.root)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        button_options = {
            "Train": self.open_train_window,
            "Observe": self.open_observe_window,
            "Live Fix": self.open_live_fix_window,
            "Advanced Options": self.show_advanced_options
        }

        for btn_text, btn_command in button_options.items():
            button = ctk.CTkButton(footer_frame, text=btn_text, command=btn_command)
            button.pack(side=tk.LEFT, padx=5, pady=5, expand=True)
            register_element("main_window", f"{btn_text.lower().replace(' ', '_')}_button", button, "button")

        # Observe status indicator
        self.observe_status = ctk.CTkLabel(footer_frame, text="Observe: Off")
        self.observe_status.pack(side=tk.RIGHT, padx=5, pady=5)

        return footer_frame

    def create_settings_button(self):
        settings_button = ctk.CTkButton(self.root, text="⚙️", width=40, command=self.open_settings)
        settings_button.place(relx=1.0, rely=0.0, x=-10, y=10, anchor="ne")
        return settings_button

    async def process_message(self, user_message):
        try:
            response = await self.main_assistant.process_user_request(user_message)
            return response
        except Exception as e:
            return f"Error: {str(e)}"

    def update_send_button_state(self):
        if self.file_upload_in_progress and self.upload_tasks:
            self.send_button.configure(state="disabled")
        else:
            self.send_button.configure(state="normal")

    def send_message(self, event=None):
        if self.is_processing or self.file_upload_in_progress:
            return "break"
        
        user_message = self.user_input.get("1.0", tk.END).strip()
        if user_message or self.uploaded_files:
            self.display_message(user_message, "user")
            self.user_input.delete("1.0", tk.END)
            self.is_processing = True
            self.display_typing_indicator()
            self.reset_chat_button.configure(state="disabled")

            print(f"Uploaded files: {self.uploaded_files}")
            
            future = asyncio.run_coroutine_threadsafe(
                self.main_assistant.process_user_request(user_message, self.uploaded_files),
                self.loop
            )
            future.add_done_callback(lambda f: self.root.after(0, self.handle_response, f))
            
            for icon in self.file_icons:
                icon.destroy()
            self.file_icons.clear()
            self.uploaded_files.clear()
        
        if event:
            return "break"

    def handle_response(self, future):
        try:
            response = future.result()
            self.remove_typing_indicator()
            if response:
                self.stop_tts() 
                self.display_message(response, "assistant")
        except Exception as e:
            self.remove_typing_indicator()
            self.display_message(f"Error: {str(e)}", "assistant")
        finally:
            self.is_processing = False
            self.reset_chat_button.configure(state="normal")
            self.uploaded_files.clear()

    def new_line(self, event=None):
        self.user_input.insert(tk.INSERT, '\n')
        return "break"
    
    def display_response(self):
        self.remove_typing_indicator()
        response = self.response_queue.get()
        self.display_message(response, "assistant")
        self.is_processing = False

    def process_queue(self):
        while not self.msg_queue.empty():
            message, sender = self.msg_queue.get()
            self.display_message(message, sender)
        self.root.after(100, self.process_queue)
    
    def on_typing_indicator_click(self, event):
        if messagebox.askyesno("Restart Program", "Do you want to restart the program?"):
            self.restart_program()
        else:
            pass

    def restart_program(self):
        try:
            self.stop_tts()
            self.main_assistant.cleanup_uploaded_files()
            self.loop.call_soon_threadsafe(self.loop.stop)
            python = sys.executable
            os.execl(python, python, "main.py")
        except Exception as e:
            logging.error(f"Failed to restart program: {e}")
            messagebox.showerror("Error", "Failed to restart the program. Please try again.")
    
    def update_plan_bubble(self, plan_info):
        if not hasattr(self, 'plan_bubble_frame'):
            self.plan_bubble_frame = ctk.CTkFrame(self.messages_frame, fg_color="#373737", corner_radius=20)
            self.plan_bubble_frame.pack(anchor="w", padx=(10, 50), pady=5)
            self.plan_bubble_label = ctk.CTkLabel(self.plan_bubble_frame, text="",
                                                font=("Helvetica", 12), text_color="#ffffff",
                                                wraplength=500, justify="left")
            self.plan_bubble_label.pack(padx=15, pady=10)

        if plan_info:
            current_plan = f"Current Plan: {plan_info.get('current_plan', 'N/A')}\n"
            current_subtask = f"Current Subtask: {plan_info.get('current_subtask', 'N/A')}"
            self.plan_bubble_label.configure(text=current_plan + current_subtask)
        else:
            self.plan_bubble_label.configure(text="Processing request...")

        self.root.update_idletasks()
        self.scroll_to_bottom()

    def display_typing_indicator(self):
        self.typing_indicator_frame = ctk.CTkFrame(self.messages_frame, fg_color="#2b2b2b")
        self.typing_indicator_frame.pack(anchor="center", pady=5)

        self.typing_indicator_canvas = tk.Canvas(self.typing_indicator_frame, width=50, height=50, bg="#2b2b2b", highlightthickness=0)
        self.typing_indicator_canvas.pack(padx=10, pady=10)
        self.typing_indicator_canvas.bind("<Button-1>", self.on_typing_indicator_click)

        self.angle = 0
        self.animate_typing_indicator()

        self.update_plan_bubble(None)

    def animate_typing_indicator(self):
        self.typing_indicator_canvas.delete("all")
        x0, y0, x1, y1 = 10, 10, 40, 40
        extent = 270

        self.typing_indicator_canvas.create_arc(x0, y0, x1, y1, start=self.angle, extent=extent, outline="#3a7ebf", width=4)
        self.angle = (self.angle + 10) % 360
        self.typing_indicator_animation = self.root.after(50, self.animate_typing_indicator)

    def remove_typing_indicator(self):
        if hasattr(self, 'typing_indicator_animation'):
            self.root.after_cancel(self.typing_indicator_animation)
        if hasattr(self, 'typing_indicator_frame'):
            self.typing_indicator_frame.destroy()
            delattr(self, 'typing_indicator_frame')
        if hasattr(self, 'typing_indicator_canvas'):
            self.typing_indicator_canvas.destroy()
            delattr(self, 'typing_indicator_canvas')
        if hasattr(self, 'plan_bubble_frame'):
            self.plan_bubble_frame.destroy()
            delattr(self, 'plan_bubble_frame')

    def display_message(self, message, sender):
        bubble_frame = ctk.CTkFrame(self.messages_frame, fg_color="#3b3b3b", corner_radius=20)

        if sender == "user":
            bubble_frame.configure(fg_color="#1c2e4a")
            bubble_frame.pack(anchor="e", padx=(50, 10), pady=5)
            label = ctk.CTkLabel(bubble_frame, text=f"{message}",
                                font=("Helvetica", 12), text_color="#ffffff",
                                wraplength=500, justify="right")
        elif sender == "assistant":
            bubble_frame.configure(fg_color="#373737")
            bubble_frame.pack(anchor="w", padx=(10, 50), pady=5)
            label = ctk.CTkLabel(bubble_frame, text=f"{message}",
                                font=("Helvetica", 12), text_color="#ffffff",
                                wraplength=500, justify="left")
        else:
            bubble_frame.configure(fg_color="#2b2b2b")
            bubble_frame.pack(anchor="center", pady=5)
            label = ctk.CTkLabel(bubble_frame, text=f"{message}",
                                font=("Helvetica", 10), text_color="#b0b0b0",
                                wraplength=500, justify="center")

        label.pack(padx=15, pady=10)

        if self.tts_enabled and sender != "user":
            threading.Thread(target=self.speak_text, args=(message,), daemon=True).start()

        self.root.update_idletasks()

        self.root.after(100, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        self.chat_display._parent_canvas.yview_moveto(1.0)


    def open_file_dialog(self):
        file_paths = tk.filedialog.askopenfilenames(
            filetypes=[
                ("All supported files", "*.txt *.pdf *.docx *.png *.jpg *.jpeg *.webp *.heic *.heif *.wav *.mp3 *.aiff *.aac *.ogg *.flac *.mp4 *.mpeg *.mov *.avi *.flv *.mpg *.webm *.wmv *.3gpp"),
                ("Image files", "*.png *.jpg *.jpeg *.webp *.heic *.heif"),
                ("Audio files", "*.wav *.mp3 *.aiff *.aac *.ogg *.flac"),
                ("Video files", "*.mp4 *.mpeg *.mov *.avi *.flv *.mpg *.webm *.wmv *.3gpp"),
                ("Text files", "*.txt *.html *.css *.js *.ts *.csv *.md *.py *.json *.xml *.rtf"),
                ("PDF files", "*.pdf"),
                ("Word documents", "*.docx")
            ]
        )
        if file_paths:
            for file_path in file_paths:
                self.add_file_to_queue(file_path)

    def add_file_to_queue(self, file_path):
        file_name = os.path.basename(file_path)
        icon = self.create_file_icon(file_name)
        self.file_upload_queue.append((file_path, icon))
        self.start_file_upload()

    def create_file_icon(self, file_name):
        icon_frame = ctk.CTkFrame(self.file_icon_area)
        icon_frame.pack(side=tk.LEFT, padx=(0, 5), pady=2)
        
        icon_label = ctk.CTkLabel(icon_frame, image=self.file_icon_image, text="")
        icon_label.pack(side=tk.LEFT, padx=(0, 5))
        
        name_label = ctk.CTkLabel(icon_frame, text=file_name, fg_color="gray", corner_radius=5)
        name_label.pack(side=tk.LEFT)
        
        delete_button = ctk.CTkButton(icon_frame, image=self.delete_icon_image, text="", width=15, height=15,
                                    command=lambda: self.delete_file(icon_frame, file_name))
        delete_button.pack(side=tk.LEFT, padx=(5, 0))
        
        self.file_icons.append(icon_frame)
        self.update_file_icon_area()
        return icon_frame

    def delete_file(self, icon_frame, file_name):
        icon_frame.destroy()
        self.uploaded_files = [f for f in self.uploaded_files if f[0] != file_name]
        self.file_icons.remove(icon_frame)
        self.update_file_icon_area()
        
        if file_name in self.upload_tasks:
            self.upload_tasks[file_name].cancel()
            del self.upload_tasks[file_name]
        
        self.update_send_button_state()

    def update_file_icon_area(self):
        if self.file_icons:
            self.file_icon_area.pack(side=tk.TOP, fill=tk.X, pady=(5, 0))
        else:
            self.file_icon_area.pack_forget()

    def rearrange_file_icons(self):
        for icon in self.file_icons:
            icon.pack_forget()
        for icon in self.file_icons:
            icon.pack(side=tk.LEFT, padx=(0, 5), pady=2)
    
    def start_file_upload(self):
        if self.file_upload_queue and not hasattr(self, 'upload_thread'):
            self.upload_thread = threading.Thread(target=self.process_file_queue, daemon=True)
            self.upload_thread.start()

    def process_file_queue(self):
        while self.file_upload_queue:
            file_path, icon = self.file_upload_queue.pop(0)
            self.upload_file_background(file_path, icon)
        if hasattr(self, 'upload_thread'):
            delattr(self, 'upload_thread')
        self.root.after(0, self.update_send_button_state)

    def upload_file_background(self, file_path, icon):
        self.file_upload_in_progress = True
        self.update_send_button_state()
        file_name = os.path.basename(file_path)
        
        async def upload_task():
            try:
                mime_type, _ = mimetypes.guess_type(file_path)
                
                if mime_type in ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
                    file_content = await self.main_assistant.extract_text_from_file(file_path)
                    self.uploaded_files.append((file_name, file_content))
                else:
                    file = await self.main_assistant.upload_and_process_file(file_path, file_name)
                    self.uploaded_files.append((file_name, file))
                
                self.root.after(0, lambda: self.update_file_icon(icon, "white"))
                print(f"File uploaded: {file_name}")
            except asyncio.CancelledError:
                print(f"File upload cancelled: {file_name}")
                self.root.after(0, lambda: self.update_file_icon(icon, "gray"))
            except Exception as e:
                print(f"Error uploading file: {str(e)}")
                self.root.after(0, lambda: self.update_file_icon(icon, "red"))
            finally:
                del self.upload_tasks[file_name]
                if not self.upload_tasks:
                    self.file_upload_in_progress = False
                self.update_send_button_state()

        task = asyncio.run_coroutine_threadsafe(upload_task(), self.loop)
        self.upload_tasks[file_name] = task
    
    
    def update_file_icon(self, icon, color):
        if icon.winfo_exists():
            icon.winfo_children()[1].configure(fg_color=color)

    def process_file_input(self, file_path):
        file_name = os.path.basename(file_path)
        self.display_message(f"Processing file: {file_name}", "system")
        
        user_message = self.user_input.get("1.0", tk.END).strip()
        if not user_message:
            user_message = f"Please describe: {file_name}"
        
        self.display_message(user_message, "user")
        self.user_input.delete("1.0", tk.END)
        self.is_processing = True
        self.display_typing_indicator()

        print(f"file path: {file_path}")
        
        future = asyncio.run_coroutine_threadsafe(
            self.main_assistant.process_user_request(user_message, file_path),
            self.loop
        )
        future.add_done_callback(lambda f: self.root.after(0, self.handle_response, f))

    def toggle_tts(self):
        self.tts_enabled = self.tts_var.get()
        self.config["gui_settings"]["tts_enabled"] = self.tts_enabled
        self.save_config()
        if self.tts_enabled:
            self.display_message("Text-to-Speech enabled", "system")
            self.root.after(2000, lambda: self.remove_message("system"))
        else:
            self.stop_tts()
            self.display_message("Text-to-Speech disabled", "system")
            self.root.after(2000, lambda: self.remove_message("system"))

    def get_current_voice_name(self):
        voices = self.tts_engine.getProperty('voices')
        current_voice_id = self.tts_engine.getProperty('voice')
        for voice in voices:
            if voice.id == current_voice_id:
                return voice.name
        return "Default"

    def change_tts_voice(self, voice_name):
        voices = self.tts_engine.getProperty('voices')
        for voice in voices:
            if voice.name == voice_name:
                self.tts_engine.setProperty('voice', voice.id)
                self.config["user_preferences"]["current_voice"] = voice.id
                self.config["user_preferences"]["current_voice_name"] = voice_name
                self.save_config()
                self.current_voice = voice.id
                self.current_voice_name = voice_name
                self.voice_var.set(voice_name)
                break

    def speak_text(self, text):
        if self.tts_in_progress:
            self.stop_tts()
        self.tts_stop_event.clear()
        self.tts_thread = threading.Thread(target=self._speak_text_thread, args=(text,), daemon=True)
        self.tts_in_progress = True
        self.tts_thread.start()

    def _speak_text_thread(self, text):
        try:
            self.current_engine = pyttsx3.init()
            self.current_engine.setProperty('voice', self.current_voice)
            self.current_engine.setProperty('rate', self.tts_rate)
            
            def onWord(name, location, length):
                if self.tts_stop_event.is_set():
                    self.current_engine.stop()

            self.current_engine.connect('started-word', onWord)
            
            for sentence in text.split('.'):
                if sentence.strip():
                    if self.tts_stop_event.is_set():
                        break
                    self.current_engine.say(sentence.strip())
                    self.current_engine.runAndWait()
                if self.tts_stop_event.is_set():
                    break
        except Exception as e:
            print(f"Error in TTS: {e}")
        finally:
            self.root.after(0, self.reset_tts_state)
            if hasattr(self, 'current_engine'):
                try:
                    self.current_engine.endLoop()
                except:
                    pass

    def reset_tts_state(self):
        self.tts_in_progress = False
        self.tts_thread = None
        self.tts_stop_event.clear()

    def stop_tts(self, force=False):
        if self.tts_in_progress or force:
            self.tts_stop_event.set()
            if self.tts_thread and self.tts_thread.is_alive():
                self.tts_thread.join(timeout=2)
            self.reset_tts_state()
            if hasattr(self, 'current_engine'):
                try:
                    self.current_engine.endLoop()
                except:
                    pass

    def change_tts_speed(self, value):
        self.tts_rate = int(value)
        self.tts_engine.setProperty('rate', self.tts_rate)
        self.config["user_preferences"]["tts_rate"] = self.tts_rate
        self.save_config()
        self.speed_value_label.configure(text=f"Speed: {self.tts_rate}")

    def open_speech_control(self):
        if self.speech_control_window:
            self.speech_control_window.lift()
            return

        self.speech_control_window = ctk.CTkToplevel(self.root)
        self.speech_control_window.title("Speech Control")
        self.speech_control_window.geometry("400x550")
        self.speech_control_window.protocol("WM_DELETE_WINDOW", self.close_speech_control)
        self.speech_control_window.attributes('-topmost', True)
        self.create_speech_control_gui()

    def create_speech_control_gui(self):
        main_frame = ctk.CTkFrame(self.speech_control_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Status icon
        self.status_icon = ctk.CTkLabel(main_frame, text="")
        self.status_icon.pack(pady=10)
        self.update_status_icon("idle")

        self.speech_status_label = ctk.CTkLabel(main_frame, text="Status: Not listening")
        self.speech_status_label.pack(pady=10)

        self.start_listening_button = ctk.CTkButton(main_frame, text="Start Listening", command=self.start_speech_control)
        self.start_listening_button.pack(pady=10)

        self.stop_listening_button = ctk.CTkButton(main_frame, text="Stop Listening", command=self.stop_speech_control, state="disabled")
        self.stop_listening_button.pack(pady=10)

        self.transcript_display = ctk.CTkTextbox(main_frame, height=200, state="disabled")
        self.transcript_display.pack(fill=tk.BOTH, expand=True, pady=20)

        self.speech_control = SpeechControl(self.update_speech_indicator, self.update_speech_transcript, self.update_status_icon)

    def update_status_icon(self, status):
        if not hasattr(self, 'status_icon') or not self.status_icon.winfo_exists():
            return 

        icon_path = os.path.join("imgs", f"{status}_icon.png")
        if os.path.exists(icon_path):
            try:
                icon_image = ctk.CTkImage(light_image=Image.open(icon_path), dark_image=Image.open(icon_path), size=(50, 50))
                self.status_icon.configure(image=icon_image)
            except Exception as e:
                print(f"Error loading icon: {str(e)}")
                self.status_icon.configure(text=status.capitalize())
        else:
            self.status_icon.configure(text=status.capitalize())

    def update_speech_indicator(self, status):
        if hasattr(self, 'speech_status_label') and self.speech_status_label.winfo_exists():
            self.speech_status_label.configure(text=f"Status: {status}")
        self.update_status_icon(status)

    def start_speech_control(self):
        if self.speech_control:
            self.speech_control.start()
            self.speech_status_label.configure(text="Status: Listening")
            self.start_listening_button.configure(state="disabled")
            self.stop_listening_button.configure(state="normal")

    def stop_speech_control(self):
        if self.speech_control:
            self.speech_control.stop()
            self.speech_status_label.configure(text="Status: Not listening")
            self.start_listening_button.configure(state="normal")
            self.stop_listening_button.configure(state="disabled")

    def update_speech_indicator(self, status):
        if self.speech_status_label:
            self.speech_status_label.configure(text=f"Status: {status}")

    def update_speech_transcript(self, text, role):
        if self.transcript_display:
            self.transcript_display.configure(state="normal")
            self.transcript_display.insert(tk.END, f"{role}: {text}\n")
            self.transcript_display.configure(state="disabled")
            self.transcript_display.see(tk.END)

    def close_speech_control(self):
        if self.speech_control:
            self.speech_control.cleanup()
        if self.speech_control_window:
            self.speech_control_window.destroy()
            self.speech_control_window = None
        self.speech_control = None
        set_active_window("main_window")

    def toggle_mode(self):
        mode = "efficiency" if self.mode_var.get() else "safe"
        self.config["gui_settings"]["mode_selected"] = mode
        self.save_config()
        self.main_assistant.config = self.config 
        print(f"Switched to {mode} mode")

    def open_train_window(self):
        if self.active_window:
            self.active_window.lift()
            return
        self.active_window = ctk.CTkToplevel(self.root)
        register_window("train_window", self.active_window)
        self.active_window.bind("<FocusIn>", lambda e: set_active_window("train_window"))
        self.active_window.title("Train Function")
        self.active_window.geometry("500x400")
        self.active_window.protocol("WM_DELETE_WINDOW", self.close_active_window)
        self.active_window.transient(self.root)
        self.active_window.grab_set()

        title_label = ctk.CTkLabel(self.active_window, text="Train Function", font=("Helvetica", 16, "bold"))
        title_label.pack(pady=20)
        register_element("train_window", "title_label", title_label, "label")

        self.status_label = ctk.CTkLabel(self.active_window, textvariable=self.train_status)
        self.status_label.pack(pady=10)
        register_element("train_window", "status_label", self.status_label, "label")

        button_frame = ctk.CTkFrame(self.active_window)
        button_frame.pack(pady=20)

        self.start_train_btn = ctk.CTkButton(button_frame, text="Start Recording", command=self.start_train_recording, state=self.start_but_train)
        self.start_train_btn.pack(side=tk.LEFT, padx=10)
        register_element("train_window", "start_train_btn", self.start_train_btn, "button")

        self.stop_train_btn = ctk.CTkButton(button_frame, text="Stop Recording", command=self.stop_train_recording, state=self.stop_but_train)
        self.stop_train_btn.pack(side=tk.LEFT, padx=10)
        register_element("train_window", "stop_train_btn", self.stop_train_btn, "button")

        self.display_trained_btn = ctk.CTkButton(self.active_window, text="Display Previously Trained", command=self.display_trained_abilities)
        self.display_trained_btn.pack(pady=10)
        register_element("train_window", "display_trained_btn", self.display_trained_btn, "button")
    
    def display_trained_abilities(self):
        if hasattr(self, 'trained_abilities_window') and self.trained_abilities_window.winfo_exists():
            self.trained_abilities_window.lift()
            return
        self.trained_abilities_window = ctk.CTkToplevel(self.root)
        register_window("trained_abilities_window", self.trained_abilities_window)
        self.trained_abilities_window.bind("<FocusIn>", lambda e: set_active_window("trained_abilities_window"))
        self.trained_abilities_window.title("Previously Trained Abilities")
        self.trained_abilities_window.geometry("400x300")
        self.trained_abilities_window.protocol("WM_DELETE_WINDOW", lambda: self.close_window(self.trained_abilities_window))
        self.trained_abilities_window.transient(self.root)
        self.trained_abilities_window.grab_set()

        ability_list = ctk.CTkScrollableFrame(self.trained_abilities_window)
        ability_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        register_element("trained_abilities_window", "ability_list", ability_list, "scrollable_frame")

        ability_file_path = r'action_data\ability_memory.json'
        if os.path.exists(ability_file_path):
            with open(ability_file_path, 'r') as file:
                abilities = json.load(file)

            for ability_group in abilities:
                for ability in ability_group:
                    ability_name = ability.get('goal', 'Unnamed Ability')
                    button = ctk.CTkButton(ability_list, text=ability_name, command=lambda a=ability: self.show_ability_details(a))
                    button.pack(pady=5, padx=10, fill=tk.X)
                    register_element("trained_abilities_window", f"ability_button_{ability_name}", button, "button")
        else:
            label = ctk.CTkLabel(ability_list, text="No trained abilities found.")
            label.pack(pady=20)
            register_element("trained_abilities_window", "no_abilities_label", label, "label")

    def show_ability_details(self, ability):
        detail_window = ctk.CTkToplevel(self.active_window)
        detail_window.title("Ability Details")
        detail_window.geometry("500x400")
        detail_window.transient(self.active_window)
        detail_window.grab_set()

        detail_text = ctk.CTkTextbox(detail_window, wrap="word")
        detail_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        detail_text.insert(tk.END, f"Goal: {ability['goal']}\n\n")
        detail_text.insert(tk.END, "Actions:\n")
        for action in ability['actions']:
            detail_text.insert(tk.END, f"- {action['description']}\n")
            if 'action_type' in action:
                detail_text.insert(tk.END, f"  Type: {action['action_type']}\n")
            if 'coordinates' in action:
                detail_text.insert(tk.END, f"  Coordinates: {action['coordinates']}\n")
            if 'value' in action:
                detail_text.insert(tk.END, f"  Value: {action['value']}\n")
            if 'timestamp' in action:
                detail_text.insert(tk.END, f"  Timestamp: {action['timestamp']}\n")
        detail_text.insert(tk.END, "\nConceptual Steps:\n")
        for step in ability['conceptual_steps']:
            detail_text.insert(tk.END, f"- {step}\n")
        detail_text.insert(tk.END, f"\nReasoning:\n{ability['reasoning']}\n")

        detail_text.configure(state='disabled')

    def start_train_recording(self):
        self.train_status.set("Status: Recording...")
        self.start_but_train = "disabled"
        self.start_train_btn.configure(state="disabled")
        self.stop_but_train = "normal"
        self.stop_train_btn.configure(state="normal")
        threading.Thread(target=start_recording).start()

        # Start a thread to check for auto-stop
        threading.Thread(target=self.check_auto_stop, daemon=True).start()

    def stop_train_recording(self):
        self.train_status.set("Status: Processing...")
        self.stop_but_train = "disabled"
        self.stop_train_btn.configure(state="disabled")
        threading.Thread(target=self.process_stop_recording).start()

    def process_stop_recording(self):
        stop_recording(self.update_train_status)

    def check_auto_stop(self):
        start_time = time.time()
        while time.time() - start_time < 40 * 60:
            if self.stop_but_train == "disabled":
                return
            time.sleep(1)

        if self.stop_but_train == "normal":
            print("Auto-stopping recording after 40 minutes.")
            self.root.after(0, self.stop_train_recording)

    def update_train_status(self, status):
        self.train_status.set(f"Status: {status}")
        self.root.update_idletasks()

        if status == "Cleanup complete":
            self.root.after(2000, lambda: self.train_status.set("Status: Ready"))
            self.start_but_train = "normal"
            self.start_train_btn.configure(state="normal")
            self.stop_but_train = "disabled"
            self.stop_train_btn.configure(state="disabled")

    def open_observe_window(self):
        if self.active_window:
            self.active_window.lift()
            return
        self.active_window = ctk.CTkToplevel(self.root)
        register_window("observe_window", self.active_window)
        self.active_window.bind("<FocusIn>", lambda e: set_active_window("observe_window"))
        self.active_window.title("Observe Function")
        self.active_window.geometry("500x400")
        self.active_window.protocol("WM_DELETE_WINDOW", self.close_observe_window)
        self.active_window.transient(self.root)
        self.active_window.grab_set()

        title_label = ctk.CTkLabel(self.active_window, text="Observe Function", font=("Helvetica", 16, "bold"))
        title_label.pack(pady=20)
        register_element("observe_window", "title_label", title_label, "label")

        self.observe_status_label = ctk.CTkLabel(self.active_window, text="Status: Not observing")
        self.observe_status_label.pack(pady=10)
        register_element("observe_window", "observe_status_label", self.observe_status_label, "label")

        button_frame = ctk.CTkFrame(self.active_window)
        button_frame.pack(pady=20)

        self.start_observe_btn = ctk.CTkButton(button_frame, text="Start Observing", command=self.start_observing, state=self.start_but_observe)
        self.start_observe_btn.pack(side=tk.LEFT, padx=10)
        register_element("observe_window", "start_observe_btn", self.start_observe_btn, "button")

        self.stop_observe_btn = ctk.CTkButton(button_frame, text="Stop Observing", command=self.stop_observing, state=self.stop_but_observe)
        self.stop_observe_btn.pack(side=tk.LEFT, padx=10)
        register_element("observe_window", "stop_observe_btn", self.stop_observe_btn, "button")

        self.display_observed_btn = ctk.CTkButton(self.active_window, text="Display Previously Observed", command=self.display_observed_summary)
        self.display_observed_btn.pack(pady=10)
        register_element("observe_window", "display_observed_btn", self.display_observed_btn, "button")

        self.update_observe_window()
    
    def display_observed_summary(self):
        if hasattr(self, 'observed_summary_window') and self.observed_summary_window.winfo_exists():
            self.observed_summary_window.lift()
            return
        self.observed_summary_window = ctk.CTkToplevel(self.root)
        register_window("observed_summary_window", self.observed_summary_window)
        self.observed_summary_window.bind("<FocusIn>", lambda e: set_active_window("observed_summary_window"))
        self.observed_summary_window.title("Previously Observed Summary")
        self.observed_summary_window.geometry("600x400")
        self.observed_summary_window.protocol("WM_DELETE_WINDOW", lambda: self.close_window(self.observed_summary_window))
        self.observed_summary_window.transient(self.root)
        self.observed_summary_window.grab_set()

        summary_text = ctk.CTkTextbox(self.observed_summary_window, wrap="word")
        summary_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        register_element("observed_summary_window", "summary_text", summary_text, "textbox")

        summary_file_path = r'observe_data\observed_summary.txt'
        if os.path.exists(summary_file_path):
            with open(summary_file_path, 'r', encoding='utf-8') as file:
                summary_content = file.read()
            summary_text.insert(tk.END, summary_content)
        else:
            summary_text.insert(tk.END, "No observed summary available.")

        summary_text.configure(state='disabled')

    def close_observe_window(self):
        self.active_window.grab_release()
        self.active_window.destroy()
        self.active_window = None

    def start_observing(self):
        self.observing = True
        self.observation_active = True
        self.update_observe_status("Starting observation...")
        self.start_but_observe = "disabled"
        self.stop_but_observe = "normal"
        self.start_observe_btn.configure(state="disabled")
        self.stop_observe_btn.configure(state="normal")
        
        self.rec_thread = threading.Thread(target=self.run_observe_rec)
        self.rec_thread.start()

        self.sum_thread = threading.Thread(target=self.run_observe_sum)
        self.sum_thread.start()

        self.update_main_observe_status()
        self.check_observe_status()

    def stop_observing(self):
        self.observing = False
        self.stop_requested = True
        self.update_observe_status("Stopping recording...")
        stop_observe_recording()
        self.stop_but_observe = "disabled"
        self.stop_observe_btn.configure(state="disabled")

    def run_observe_rec(self):
        try:
            start_observe_recording()
        except Exception as e:
            self.update_observe_status(f"Error in recording: {str(e)}")

    def run_observe_sum(self):
        time.sleep(2)

        while self.observation_active:
            try:
                unprocessed_count = self.get_unprocessed_recordings_count()
                if unprocessed_count > 0 and not get_summarizing_status():
                    process_next_video()
                    self.update_observe_status(f"Processed video. Remaining: {self.get_unprocessed_recordings_count()}")
                elif self.stop_requested and unprocessed_count == 0 and not get_summarizing_status():
                    break
                else:
                    time.sleep(1)
            except Exception as e:
                self.update_observe_status(f"Error in summarization: {str(e)}")
                time.sleep(5) 

        self.observation_active = False
        self.notify_observation_complete()

    def get_unprocessed_recordings_count(self):
        finished_recordings_path = r'observe_data\finished_recordings.json'
        try:
            with open(finished_recordings_path, 'r') as f:
                recordings = json.load(f)
            return len(recordings)
        except (FileNotFoundError, json.JSONDecodeError):
            return 0
        
    def update_observe_status(self, message):
        if self.active_window and hasattr(self, 'observe_status_label'):
            self.observe_status_label.configure(text=message)
        self.update_main_observe_status()

    def update_main_observe_status(self):
        if self.observing or self.observation_active and not self.stop_requested:
            self.observe_status.configure(text="Observe: On")

        elif not self.observation_active and self.stop_requested and not self.observing:
            self.observe_status.configure(text="Observe: Off")
            self.start_but_observe = "normal"
            self.start_observe_btn.configure(state="normal")
        else:
            pass

        self.root.update_idletasks()

    def update_observe_window(self):
        if self.active_window:
            remaining = self.get_unprocessed_recordings_count()
            summarizing = get_summarizing_status()
            status = "Recording" if self.observing else "Summarizing" if remaining > 0 or summarizing else "Idle"
            detailed_status = f"Status: {status}\nRemaining recordings: {remaining}\nSummarizing: {'Yes' if summarizing else 'No'}"
            self.observe_status_label.configure(text=detailed_status)
            self.active_window.after(1000, self.update_observe_window)

    def check_observe_status(self):
        self.update_main_observe_status()
        if self.observation_active:
            self.root.after(1000, self.check_observe_status)

    def notify_observation_complete(self):
        self.update_main_observe_status()
        if self.stop_requested and not self.observation_active:
            messagebox.showinfo("Observation Complete", "All recordings have been processed and summarized. You can view the results in the summary file.")
        self.stop_requested = False
    
    def close_window(self, window):
        window_name = next((name for name, w in gui_manager.windows.items() if w() == window), None)
        if window_name:
            gui_manager.unregister_window(window_name)
        window.destroy()
        delattr(self, window_name.lower())

    def open_live_fix_window(self):
        if self.active_window:
            self.active_window.lift()
            return
        self.live_fix_initial_window = ctk.CTkToplevel(self.root)
        register_window("live_fix_initial_window", self.live_fix_initial_window)
        self.live_fix_initial_window.bind("<FocusIn>", lambda e: set_active_window("live_fix_initial_window"))
        self.live_fix_initial_window.title("Live Fix")
        self.live_fix_initial_window.geometry("300x150")
        self.live_fix_initial_window.protocol("WM_DELETE_WINDOW", self.close_active_window)
        self.live_fix_initial_window.transient(self.root)
        self.live_fix_initial_window.grab_set()
        
        start_button = ctk.CTkButton(self.live_fix_initial_window, text="Start Live Fix", command=self.start_live_fix)
        start_button.pack(expand=True)
        register_element("live_fix_initial_window", "start_button", start_button, "button")

        self.active_window = self.live_fix_initial_window

    def start_live_fix(self):
        self.live_fix_assistant = LiveFixAssistant()
        self.live_fix_assistant.set_gui_callback(self.live_fix_gui_callback)
        
        if self.live_fix_initial_window:
            self.live_fix_initial_window.grab_release()
            self.live_fix_initial_window.destroy()
            self.live_fix_initial_window = None
            self.active_window = None

        self.show_live_fix_gui()

    def show_live_fix_gui(self):
        if self.live_fix_main_window:
            self.live_fix_main_window.lift()
            return

        self.root.withdraw()

        self.live_fix_main_window = ctk.CTkToplevel()
        register_window("live_fix_main_window", self.live_fix_main_window)
        self.live_fix_main_window.bind("<FocusIn>", lambda e: set_active_window("live_fix_main_window"))
        self.live_fix_main_window.title("Live Fix Mode")
        self.live_fix_main_window.geometry("650x400")
        self.live_fix_main_window.protocol("WM_DELETE_WINDOW", self.close_live_fix)
        self.live_fix_main_window.attributes('-topmost', True)

        self.live_fix_output = ctk.CTkTextbox(self.live_fix_main_window, width=580, height=300, state="disabled")
        self.live_fix_output.pack(pady=10, padx=10)
        register_element("live_fix_main_window", "live_fix_output", self.live_fix_output, "textbox")

        self.live_fix_file_icon_area = ctk.CTkFrame(self.live_fix_main_window)
        self.live_fix_file_icon_area.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.live_fix_file_icon_area.pack_forget() 
        register_element("live_fix_main_window", "live_fix_file_icon_area", self.live_fix_file_icon_area, "frame")

        input_frame = ctk.CTkFrame(self.live_fix_main_window)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        register_element("live_fix_main_window", "input_frame", input_frame, "frame")

        self.live_fix_input = ctk.CTkEntry(input_frame, width=480)
        self.live_fix_input.pack(side=tk.LEFT, padx=(0, 5))
        self.live_fix_input.bind("<Return>", self.send_live_fix_message)
        register_element("live_fix_main_window", "live_fix_input", self.live_fix_input, "entry")

        self.send_button = ctk.CTkButton(input_frame, text="Send", width=50, command=self.send_live_fix_message)
        self.send_button.pack(side=tk.LEFT)
        register_element("live_fix_main_window", "send_button", self.send_button, "button")

        file_image = Image.open(r"imgs\\add_file_icon.png")
        file_ctk_image = ctk.CTkImage(light_image=file_image, dark_image=file_image, size=(20, 20))
        file_button = ctk.CTkButton(input_frame, image=file_ctk_image, text="", width=30, height=30, 
                                    command=self.open_live_fix_file_dialog)
        file_button.pack(side=tk.LEFT, padx=5)
        register_element("live_fix_main_window", "file_button", file_button, "button")

        # Add new screenshot button
        screenshot_image = Image.open(r"imgs\\choose_icon.png")
        screenshot_ctk_image = ctk.CTkImage(light_image=screenshot_image, dark_image=screenshot_image, size=(20, 20))
        screenshot_button = ctk.CTkButton(input_frame, image=screenshot_ctk_image, text="", width=30, height=30, 
                                          command=self.initiate_screen_capture)
        screenshot_button.pack(side=tk.LEFT, padx=5)
        register_element("live_fix_main_window", "screenshot_button", screenshot_button, "button")

        set_active_window("live_fix_main_window")
    
    def initiate_screen_capture(self):
        self.live_fix_main_window.withdraw() 
        overlay = ScreenCaptureOverlay(self.root)
        self.root.wait_window(overlay.root)
        screenshot = overlay.get_screenshot()
        if screenshot:
            self.process_screenshot(screenshot)
        self.live_fix_main_window.deiconify()
    
    def process_screenshot(self, screenshot):
        screenshot_count = len([f for f in self.live_fix_assistant.uploaded_files if f[0].startswith("screenshot")])
        screenshot_name = f"screenshot{screenshot_count + 1}.png"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
            screenshot.save(temp_file.name, format='PNG')
            screenshot_path = temp_file.name

        self.add_live_fix_file_to_queue(screenshot_path, custom_name=screenshot_name)

    def send_live_fix_message(self, event=None):
        if self.is_processing:
            return "break"
        
        user_message = self.live_fix_input.get()
        self.live_fix_input.delete(0, tk.END)
        self.append_to_live_fix_output(f"You: {user_message}")
        
        self.live_fix_input.configure(state="disabled")
        self.send_button.configure(state="disabled")
        
        asyncio.run_coroutine_threadsafe(
            self.process_live_fix_request(user_message),
            self.loop
        )

        for icon in self.live_fix_file_icons:
            icon.destroy()
        self.live_fix_file_icons.clear()
        self.live_fix_assistant.clear_uploaded_files()
        self.update_live_fix_file_icon_area()
    
    async def process_live_fix_request(self, message):
        try:
            self.live_fix_assistant.set_notification_callback(self.live_fix_notification_callback)
            response = await self.live_fix_assistant.process_user_request(message)
            self.root.after(0, self.handle_live_fix_response, response)
        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            self.root.after(0, self.handle_live_fix_response, error_message)

    def handle_live_fix_response(self, response):
        if response:
            try:
                response_dict = json.loads(response)
                user_responses = []
                
                if 'response_to_user' in response_dict:
                    user_responses.append(response_dict['response_to_user'])
                if 'task_breakdown' in response_dict:
                    for task in response_dict['task_breakdown']:
                        if 'response_to_user' in task:
                            user_responses.append(task['response_to_user'])
                
                if response_dict.get('user_request_fully_finished', False) or not response_dict.get('continue_execution', True):
                    self.enable_live_fix_input()
                    self.live_fix_assistant.reset_state()
                elif response_dict.get('continue_execution', False):
                    asyncio.run_coroutine_threadsafe(
                        self.live_fix_assistant.continue_execution(response_dict),
                        self.loop
                    )
                else:
                    self.enable_live_fix_input()
            except json.JSONDecodeError:
                self.append_to_live_fix_output(f"Assistant: {response}")
                self.show_notification(f"Assistant: {response}")
                self.enable_live_fix_input()
        else:
            self.enable_live_fix_input()
            
    def enable_live_fix_input(self):
        self.live_fix_input.configure(state="normal")
        self.send_button.configure(state="normal")
        
    async def live_fix_gui_callback(self, action: str, data: Any) -> Any:
        if action == 'confirmation':
            return await self.show_confirmation_dialog(data)
        elif action == 'input':
            return self.get_user_input(data)
        elif action == 'task_complete':
            self.root.after(0, self.enable_live_fix_input)
        elif action == 'command_result':
            self.root.after(0, self.append_to_live_fix_output, f"Command result: {data}")
    
    async def live_fix_notification_callback(self, message):
        self.root.after(0, self.append_to_live_fix_output, f"Assistant: {message}")
        self.root.after(0, self.show_notification, f"Assistant: {message}")
    
    def show_notification(self, message):
        notification_window = ctk.CTkToplevel(self.live_fix_main_window)
        notification_window.title("Live Fix Notification")
        notification_window.geometry("500x400")
        notification_window.attributes('-topmost', True)
        
        frame = ctk.CTkFrame(notification_window, corner_radius=10)
        frame.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)

        ctk.CTkLabel(frame, text="Live Fix Assistant:", font=("Helvetica", 16, "bold")).pack(pady=(10, 5))
        
        text_frame = ctk.CTkFrame(frame)
        text_frame.pack(fill=ctk.BOTH, expand=True, padx=10, pady=5)

        text_area = ctk.CTkTextbox(text_frame, wrap="word", width=360, height=180)
        text_area.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=True)
        
        scrollbar = ctk.CTkScrollbar(text_frame, command=text_area.yview)
        scrollbar.pack(side=ctk.RIGHT, fill=ctk.Y)
        
        text_area.configure(yscrollcommand=scrollbar.set)
        text_area.insert(ctk.END, message)
        text_area.configure(state="disabled")

        close_button = ctk.CTkButton(frame, text="Close", command=lambda: self.close_notification(notification_window))
        close_button.pack(pady=10)

        # Register the notification window
        window_name = f"notification_{id(notification_window)}"
        register_window(window_name, notification_window)
        set_active_window(window_name)
        register_element(window_name, "message_text", text_area, "textbox")
        register_element(window_name, "close_button", close_button, "button")

        notification_window.protocol("WM_DELETE_WINDOW", lambda: self.close_notification(notification_window))


    def close_notification(self, notification_window):
        window_name = f"notification_{id(notification_window)}"
        gui_manager.close_window(window_name)
        notification_window.destroy()
        self.enable_live_fix_input()
    
    async def show_confirmation_dialog(self, prompt: str):
        global confirmation_result
        confirmation_window = ctk.CTkToplevel(self.live_fix_main_window)
        confirmation_window.title("Confirm Action")
        confirmation_window.geometry("500x400")
        confirmation_window.attributes('-topmost', True)
        
        frame = ctk.CTkFrame(confirmation_window, corner_radius=10)
        frame.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)

        ctk.CTkLabel(frame, text="Confirmation Required:", font=("Helvetica", 16, "bold")).pack(pady=(10, 5))
        
        text_frame = ctk.CTkFrame(frame)
        text_frame.pack(fill=ctk.BOTH, expand=True, padx=10, pady=5)

        text_area = ctk.CTkTextbox(text_frame, wrap="word", width=360, height=180)
        text_area.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=True)
        
        scrollbar = ctk.CTkScrollbar(text_frame, command=text_area.yview)
        scrollbar.pack(side=ctk.RIGHT, fill=ctk.Y)
        
        text_area.configure(yscrollcommand=scrollbar.set)
        text_area.insert(ctk.END, prompt)
        text_area.configure(state="disabled")

        button_frame = ctk.CTkFrame(frame)
        button_frame.pack(pady=10)

        confirmation_result = None

        def on_allow():
            global confirmation_result
            confirmation_result = True
            confirmation_window.destroy()
            print("User allowed the action.")
            print(confirmation_result)

        def on_deny():
            global confirmation_result
            confirmation_result = False
            confirmation_window.destroy()
            print("User denied the action.")
            print(confirmation_result)
        
        ctk.CTkButton(button_frame, text="Allow", command=on_allow).pack(side=ctk.LEFT, padx=10)
        ctk.CTkButton(button_frame, text="Deny", command=on_deny).pack(side=ctk.LEFT, padx=10)

        # Register the confirmation window
        window_name = f"confirmation_{id(confirmation_window)}"
        register_window(window_name, confirmation_window)
        set_active_window(window_name)
        register_element(window_name, "message_text", text_area, "textbox")
        register_element(window_name, "allow_button", button_frame.winfo_children()[0], "button")
        register_element(window_name, "deny_button", button_frame.winfo_children()[1], "button")

        confirmation_window.protocol("WM_DELETE_WINDOW", on_deny)


        while confirmation_result is None:
            time.sleep(0.1)

        return confirmation_result
    
    def open_live_fix_file_dialog(self):
        file_paths = tk.filedialog.askopenfilenames(
            filetypes=[
                ("All supported files", "*.txt *.pdf *.docx *.png *.jpg *.jpeg *.webp *.heic *.heif *.wav *.mp3 *.aiff *.aac *.ogg *.flac *.mp4 *.mpeg *.mov *.avi *.flv *.mpg *.webm *.wmv *.3gpp"),
                ("Image files", "*.png *.jpg *.jpeg *.webp *.heic *.heif"),
                ("Audio files", "*.wav *.mp3 *.aiff *.aac *.ogg *.flac"),
                ("Video files", "*.mp4 *.mpeg *.mov *.avi *.flv *.mpg *.webm *.wmv *.3gpp"),
                ("Text files", "*.txt *.html *.css *.js *.ts *.csv *.md *.py *.json *.xml *.rtf"),
                ("PDF files", "*.pdf"),
                ("Word documents", "*.docx")
            ]
        )
        if file_paths:
            for file_path in file_paths:
                self.add_live_fix_file_to_queue(file_path)

    # Update the add_live_fix_file_to_queue method to accept a custom name
    def add_live_fix_file_to_queue(self, file_path, custom_name=None):
        file_name = custom_name or os.path.basename(file_path)
        if not any(file_name == uploaded_file[0] for uploaded_file in self.live_fix_assistant.uploaded_files):
            icon = self.create_live_fix_file_icon(file_name)
            self.live_fix_file_upload_queue.append((file_path, icon))
            self.start_live_fix_file_upload()
        else:
            print(f"File {file_name} is already uploaded.")

    def create_live_fix_file_icon(self, file_name):
        icon_frame = ctk.CTkFrame(self.live_fix_file_icon_area)
        icon_frame.pack(side=tk.LEFT, padx=(0, 5), pady=2)
        
        icon_label = ctk.CTkLabel(icon_frame, image=self.file_icon_image, text="")
        icon_label.pack(side=tk.LEFT, padx=(0, 5))
        
        name_label = ctk.CTkLabel(icon_frame, text=file_name, fg_color="gray", corner_radius=5)
        name_label.pack(side=tk.LEFT)
        
        delete_button = ctk.CTkButton(icon_frame, image=self.delete_icon_image, text="", width=15, height=15,
                                      command=lambda: self.delete_live_fix_file(icon_frame, file_name))
        delete_button.pack(side=tk.LEFT, padx=(5, 0))
        
        self.live_fix_file_icons.append(icon_frame)
        self.update_live_fix_file_icon_area()
        return icon_frame
    
    def delete_live_fix_file(self, icon_frame, file_name):
        icon_frame.destroy()
        self.live_fix_assistant.uploaded_files = [f for f in self.live_fix_assistant.uploaded_files if f[0] != file_name]
        self.live_fix_file_icons.remove(icon_frame)
        self.update_live_fix_file_icon_area()

    def update_live_fix_file_icon_area(self):
        if self.live_fix_file_icons:
            self.live_fix_file_icon_area.pack(fill=tk.X, padx=10, pady=(0, 5))
        else:
            self.live_fix_file_icon_area.pack_forget()

    def start_live_fix_file_upload(self):
        if self.live_fix_file_upload_queue and not hasattr(self, 'live_fix_upload_thread'):
            self.live_fix_upload_thread = threading.Thread(target=self.process_live_fix_file_queue, daemon=True)
            self.live_fix_upload_thread.start()
            self.send_button.configure(state="disabled")

    def process_live_fix_file_queue(self):
        while self.live_fix_file_upload_queue:
            file_path, icon = self.live_fix_file_upload_queue.pop(0)
            self.upload_live_fix_file_background(file_path, icon)
        delattr(self, 'live_fix_upload_thread')
        self.root.after(0, lambda: self.send_button.configure(state="normal"))

    def upload_live_fix_file_background(self, file_path, icon):
        try:
            file_name = os.path.basename(file_path)
            if not any(file_name == uploaded_file[0] for uploaded_file in self.live_fix_assistant.uploaded_files):
                processed_file = asyncio.run(self.live_fix_assistant.process_file(file_path))
                self.live_fix_assistant.add_file(file_name, processed_file)
                self.root.after(0, lambda: icon.winfo_children()[1].configure(fg_color="white"))
                print(f"File uploaded to Live Fix: {file_name}")
            else:
                print(f"File {file_name} is already uploaded.")
        except Exception as e:
            print(f"Error uploading file to Live Fix: {str(e)}")
            self.root.after(0, lambda: icon.winfo_children()[1].configure(fg_color="red"))

    def cancel_live_fix_task(self):
        self.live_fix_assistant.cancel_task()
        self.append_to_live_fix_output("System: Current task cancelled.")

    def close_live_fix(self):
        if hasattr(self, 'live_fix_assistant'):
            self.live_fix_assistant.cancel_task()
            del self.live_fix_assistant
        if self.live_fix_main_window:
            self.live_fix_main_window.destroy()
            gui_manager.unregister_window("live_fix_main_window")
            self.live_fix_main_window = None
        self.root.deiconify()
        set_active_window("main_window")

    def append_to_live_fix_output(self, message):
        self.live_fix_output.configure(state="normal")
        self.live_fix_output.insert(tk.END, message + "\n")
        self.live_fix_output.configure(state="disabled")
        self.live_fix_output.see(tk.END)

    async def update_live_fix_gui(self, message):
        if isinstance(message, dict) and 'user_input_required' in message:
            response = await self.get_user_input(message['user_input_required'])
            return response
        else:
            self.root.after(0, self.append_to_live_fix_output, f"System: {message}")
            return None

    async def get_user_input(self, prompt):
        future = asyncio.Future()
        self.root.after(0, self.show_user_input_dialog, prompt, future)
        return await future

    def show_user_input_dialog(self, prompt, future):
        dialog = ctk.CTkInputDialog(text=prompt, title="User Input Required")
        response = dialog.get_input()
        future.set_result(response)

    def on_closing(self):
        self.stop_tts()
        live_fix_active = hasattr(self, 'live_fix_assistant') and self.live_fix_assistant is not None
        
        if live_fix_active:
            if messagebox.askokcancel("Quit", "Live Fix is still active. Are you sure you want to quit?"):
                self.live_fix_assistant.cancel_task()
                del self.live_fix_assistant
            else:
                return
        
        if self.observation_active or get_recording_count() > 0 or get_summarizing_status():
            if messagebox.askokcancel("Quit", "Observation is still in progress. Are you sure you want to quit? This will stop all ongoing processes and can create unnecessary files."):
                self.stop_observing()
                for thread in [self.rec_thread, self.sum_thread]:
                    if thread and thread.is_alive():
                        thread.join()
            else:
                return
        
        self.main_assistant.cleanup_uploaded_files()
        self.loop.call_soon_threadsafe(self.loop.stop)
        
        if self.active_window:
            self.close_active_window()
        
        if self.vm_learn_window:
            self.close_vm_learn_window()
        
        if hasattr(self, 'trained_abilities_window'):
            self.close_window(self.trained_abilities_window)
        
        if hasattr(self, 'observed_summary_window'):
            self.close_window(self.observed_summary_window)
        
        gui_manager.unregister_window("main_window")
        self.root.quit()
        self.root.destroy()

    def show_advanced_options(self):
        if self.active_window:
            self.active_window.lift()
            return
        self.create_modal_window("Advanced Options", "500x400")
        register_window("advanced_options_window", self.active_window)
        self.active_window.bind("<FocusIn>", lambda e: set_active_window("advanced_options_window"))
        
        title_label = ctk.CTkLabel(self.active_window, text="Advanced Options", font=("Helvetica", 16, "bold"))
        title_label.pack(pady=20)
        register_element("advanced_options_window", "title_label", title_label, "label")

        vm_learn_btn = ctk.CTkButton(self.active_window, text="VM Learn", command=self.open_vm_learn)
        vm_learn_btn.pack(pady=10)
        register_element("advanced_options_window", "vm_learn_btn", vm_learn_btn, "button")

        agent_framework_btn = ctk.CTkButton(self.active_window, text="Agent Framework", command=self.open_agent_framework)
        agent_framework_btn.pack(pady=10)
        register_element("advanced_options_window", "agent_framework_btn", agent_framework_btn, "button")
    
    def create_modal_window(self, title, geometry):
        self.active_window = ctk.CTkToplevel(self.root)
        register_window(f"{title.lower().replace(' ', '_')}_window", self.active_window)
        self.active_window.bind("<FocusIn>", lambda e: set_active_window(f"{title.lower().replace(' ', '_')}_window"))
        self.active_window.title(title)
        self.active_window.geometry(geometry)
        self.active_window.protocol("WM_DELETE_WINDOW", self.close_active_window)
        self.active_window.transient(self.root)
        self.active_window.grab_set()

    def open_settings(self):
        if self.active_window:
            self.active_window.lift()
            return
        self.create_modal_window("Settings", "400x400")
        register_window("settings_window", self.active_window)
        self.active_window.bind("<FocusIn>", lambda e: set_active_window("settings_window"))
        self.populate_settings_window()
        self.refresh_voice_selection()

    def refresh_voice_selection(self):
        voices = self.tts_engine.getProperty('voices')
        voice_names = [voice.name for voice in voices]
        if self.config["user_preferences"]["current_voice_name"] in voice_names:
            self.voice_var.set(self.config["user_preferences"]["current_voice_name"])
            self.voice_menu.set(self.config["user_preferences"]["current_voice_name"])

    def reset_settings(self):
        if messagebox.askyesno("Reset Settings", "Are you sure you want to reset settings to default? This will close the settings window and restart the application."):
            self.config = self.DEFAULT_CONFIG
            self.save_config()
            self.apply_settings()
            self.close_active_window()  
            self.reinitialize_gui() 
    
    def reinitialize_gui(self):
        self.stop_tts()
        
        for widget in self.root.winfo_children():
            widget.destroy()

        # Reinitialize the attributes that need to be reset
        self.tts_engine = pyttsx3.init()
        self.tts_enabled = self.config["gui_settings"]["tts_enabled"]
        self.tts_voice = self.config["user_preferences"]["current_voice"]
        self.tts_rate = self.config["user_preferences"]["tts_rate"]
        self.tts_in_progress = False
        self.tts_thread = None
        self.tts_stop_event = threading.Event()
        self.current_voice = self.tts_voice
        self.voice_var = None
        self.current_voice_name = self.get_current_voice_name()

        # Set TTS voice and rate
        self.tts_engine.setProperty('voice', self.tts_voice)
        self.tts_engine.setProperty('rate', self.tts_rate)
        
        # Recreate the GUI elements
        self.create_gui()
        
        # Set initial states for switches and other settings
        self.tts_var.set(self.tts_enabled)
        self.memory_var.set(self.memory_enabled)
        self.mode_var.set(self.config["gui_settings"]["mode_selected"] == "efficiency")
        self.model_var.set(self.config["gui_settings"]["model_selected"])
        self.voice_var = ctk.StringVar(value=self.config["user_preferences"]["current_voice_name"])
        
        self.refresh_voice_selection()
        self.update_send_button_state()
        
        # Start processing queue
        self.root.after(100, self.process_queue)

        set_active_window("main_window")


    def apply_settings(self):
        ctk.set_appearance_mode(self.config["gui_settings"]["appearance_mode"])
        self.tts_enabled = self.config["gui_settings"]["tts_enabled"]
        self.tts_rate = self.config["user_preferences"]["tts_rate"]
        self.memory_enabled = self.config["gui_settings"]["memory_enabled"]
        self.mode_var.set(self.config["gui_settings"]["mode_selected"] == "efficiency")
        self.refresh_voice_selection()

    def populate_settings_window(self):
        title_label = ctk.CTkLabel(self.active_window, text="Settings", font=("Helvetica", 16, "bold"))
        title_label.pack(pady=20)

        theme_label = ctk.CTkLabel(self.active_window, text="Theme:")
        theme_label.pack(pady=(10, 5))
        self.theme_var = ctk.StringVar(value=self.config["gui_settings"]["appearance_mode"].capitalize())
        theme_menu = ctk.CTkOptionMenu(self.active_window, variable=self.theme_var, 
                                    values=["Light", "Dark"], 
                                    command=self.change_theme)
        theme_menu.pack(pady=(0, 10))
        register_element("settings_window", "theme_menu", theme_menu, "option_menu")

        # TTS Voice selection
        voice_label = ctk.CTkLabel(self.active_window, text="TTS Voice:")
        voice_label.pack(pady=(10, 5))
        voices = self.tts_engine.getProperty('voices')
        voice_names = [voice.name for voice in voices]
        self.voice_var = ctk.StringVar(value=self.config["user_preferences"]["current_voice_name"])
        self.voice_menu = ctk.CTkOptionMenu(self.active_window, variable=self.voice_var, 
                                            values=voice_names, 
                                            command=self.change_tts_voice)
        self.voice_menu.pack(pady=(0, 10))
        register_element("settings_window", "voice_menu", self.voice_menu, "option_menu")

        # TTS Speed slider
        speed_label = ctk.CTkLabel(self.active_window, text="TTS Speed:")
        speed_label.pack(pady=(10, 5))
        self.speed_slider = ctk.CTkSlider(self.active_window, from_=50, to=300, 
                                        number_of_steps=25, command=self.change_tts_speed)
        self.speed_slider.set(self.config["user_preferences"]["tts_rate"])
        self.speed_slider.pack(pady=(0, 10))
        self.speed_value_label = ctk.CTkLabel(self.active_window, text=f"Speed: {self.tts_rate}")
        self.speed_value_label.pack()

        # Reset Settings button
        reset_button = ctk.CTkButton(self.active_window, text="Reset Settings", command=self.reset_settings)
        reset_button.pack(pady=20)
        register_element("settings_window", "reset_button", reset_button, "button")

        # Refresh voice selection to match config
        self.refresh_voice_selection()

    def close_active_window(self):
        if self.active_window:
            window_name = next((name for name, window in gui_manager.windows.items() if window() == self.active_window), None)
            if window_name:
                gui_manager.unregister_window(window_name)
            if self.active_window == self.live_fix_initial_window:
                self.live_fix_initial_window.grab_release()
            self.active_window.destroy()
            self.active_window = None
            set_active_window("main_window")
        if self.live_fix_main_window:
            self.close_live_fix()

    def change_model(self, model_name):
        self.main_assistant.set_model(model_name)
        self.config["gui_settings"]["model_selected"] = model_name
        self.save_config()
        self.update_file_button_state(model_name)

    def change_theme(self, theme):
        ctk.set_appearance_mode(theme.lower())
        self.config["gui_settings"]["appearance_mode"] = theme.lower()
        self.save_config()
        self.root.update_idletasks()

        if self.active_window:
            geometry = self.active_window.geometry()
            self.active_window.destroy()
            self.create_modal_window("Settings", "400x300")
            self.populate_settings_window()
            self.active_window.geometry(geometry)

        if hasattr(self, 'theme_var'):
            self.theme_var.set(theme)

    def open_vm_learn(self):
        if self.active_window:
            self.close_active_window()
        
        self.vm_learn_window = VMLearningGUI(self.root, self.close_vm_learn_window)
        self.active_window = self.vm_learn_window.window
        self.active_window.transient(self.root)
        self.active_window.grab_set()
        self.active_window.focus_force()

    def close_vm_learn_window(self):
        if self.vm_learn_window:
            self.vm_learn_window.window.grab_release()
            self.vm_learn_window.window.destroy()
            self.vm_learn_window = None
            self.active_window = None

    def open_agent_framework(self):
        self.root.quit()

    def show_main_gui(self):
        self.root.deiconify()

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    chat_interface = ChatInterface({}, root)
    chat_interface.root.protocol("WM_DELETE_WINDOW", chat_interface.on_closing)
    chat_interface.root.mainloop()