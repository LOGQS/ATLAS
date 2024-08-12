# ag_main.py
import os
import json
import tkinter as tk
from tkinter import messagebox
from ag_create_agent import show_create_agent_frame
from ag_create_tool import show_create_tool_frame
from ag_builder_bot import show_builder_bot_frame
from ag_canvas import show_open_canvas_frame
from ag_canvas_settings import show_canvas_settings_frame 
from gui_element_manager import register_window, register_element, set_active_window, gui_manager

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()

        # Configure window
        self.title("Agent Framework")
        self.geometry("1000x700")
        self.configure(bg="#1e1e1e")
        self.resizable(False, False)
        self.advanced_window_open = False

        # Register main window
        register_window("agent_framework_main", self)

        # Create a main frame to hold all content
        self.main_frame = tk.Frame(self, bg="#1e1e1e")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Create and register frames for each mode
        self.canvas_frame = self.create_frame()
        self.build_frame = self.create_frame()
        register_window("canvas_frame", self.canvas_frame)
        register_window("build_frame", self.build_frame)

        # Create mode switcher
        self.create_mode_switch()

        # Populate frames
        self.populate_canvas_frame()
        self.populate_build_frame()

        # Initialize advanced settings
        self.advanced_settings = self.load_advanced_settings()

        sliding_window_width = 700 
        self.sliding_window = tk.Frame(self, bg="#2c2c2c", width=sliding_window_width)
        self.sliding_window.place(relx=1, rely=0, relheight=1, width=sliding_window_width, anchor="ne")
        self.sliding_window.place_forget()

        self.canvas_settings_window = None
        # Initialize canvas settings
        self.canvas_settings = {
            "show_grid": False,
            "snap_to_grid": False,
            "bg_color": "#2c2c2c",
            "grid_size": 100  
        }

        self.current_mode = None
        self.switch_mode("CANVAS")
    
    def create_frame(self):
        return tk.Frame(self.main_frame, bg="#2c2c2c", bd=2, relief="ridge", padx=10, pady=10)
    
    def populate_canvas_frame(self):
        button_container = tk.Frame(self.canvas_frame, bg="#2c2c2c")
        button_container.place(relx=0.5, rely=0.5, anchor="center")

        open_canvas_button = self.add_styled_button(button_container, "Open Canvas", self.open_canvas)
        canvas_settings_button = self.add_styled_button(button_container, "Canvas Settings", self.open_canvas_settings)

        register_element("canvas_frame", "open_canvas_button", open_canvas_button, "button")
        register_element("canvas_frame", "canvas_settings_button", canvas_settings_button, "button")

    def populate_build_frame(self):
        button_container = tk.Frame(self.build_frame, bg="#2c2c2c")
        button_container.place(relx=0.5, rely=0.5, anchor="center")

        button_data = [
            ("Create Agent", lambda: show_create_agent_frame(self)),
            ("Create Tool", lambda: show_create_tool_frame(self)),
            ("Builder Bot", lambda: show_builder_bot_frame(self))
        ]

        for text, command in button_data:
            button = self.add_styled_button(button_container, text, command)
            register_element("build_frame", f"{text.lower().replace(' ', '_')}_button", button, "button")

    
    def interact_with_element(self, window_name, element_name, action, **kwargs):
        try:
            return gui_manager.interact_with_element(window_name, element_name, action, **kwargs)
        except Exception as e:
            print(f"Error interacting with element {element_name} in {window_name}: {e}")
    
    def open_canvas(self):
        if hasattr(self, 'open_canvas_frame'):
            self.open_canvas_frame.lift()
        else:
            show_open_canvas_frame(self)
        set_active_window("canvas_window")

    def create_mode_switch(self):
        # Create a frame for mode switch buttons
        self.mode_switch_frame = tk.Frame(self.main_frame, bg="#1e1e1e")
        self.mode_switch_frame.pack(pady=10)

        # CANVAS button
        self.canvas_button = tk.Button(
            self.mode_switch_frame,
            text="CANVAS",
            font=("Helvetica", 16, "bold"),
            bg="#333333",
            fg="white",
            activebackground="#4a4a4a",
            activeforeground="white",
            command=lambda: self.switch_mode("CANVAS"),
            bd=0,
            relief="flat",
            padx=20,
            pady=5
        )
        self.canvas_button.grid(row=0, column=0)
        register_element("agent_framework_main", "canvas_button", self.canvas_button, "button")

        # BUILD button
        self.build_button = tk.Button(
            self.mode_switch_frame,
            text="BUILD",
            font=("Helvetica", 16, "bold"),
            bg="#4a4a4a",
            fg="white",
            activebackground="#666666",
            activeforeground="white",
            command=lambda: self.switch_mode("BUILD"),
            bd=0,
            relief="flat",
            padx=20,
            pady=5
        )
        self.build_button.grid(row=0, column=1, padx=(2, 0))
        register_element("agent_framework_main", "build_button", self.build_button, "button")

        self.canvas_button.config(command=lambda: self.switch_mode("CANVAS"))
        self.build_button.config(command=lambda: self.switch_mode("BUILD"))

        register_element("agent_framework_main", "canvas_button", self.canvas_button, "button")
        register_element("agent_framework_main", "build_button", self.build_button, "button")

    def add_styled_button(self, parent, text, command):
        button = tk.Button(
            parent,
            text=text,
            font=("Helvetica", 18, "bold"),
            bg="#444444",
            fg="white",
            activebackground="#666666",
            activeforeground="white",
            bd=5,
            relief="raised",
            command=command,
            width=20,
            height=2
        )
        button.pack(pady=25)
        return button

    def open_canvas(self):
        show_open_canvas_frame(self)

    def open_canvas_settings(self):
        if self.canvas_settings_window is None or not self.canvas_settings_window.winfo_exists():
            self.canvas_settings_window = show_canvas_settings_frame(self)
            register_window("canvas_settings_window", self.canvas_settings_window)
            self.canvas_settings_window.bind("<FocusIn>", lambda e: set_active_window("canvas_settings"))
            self.canvas_settings_window.protocol("WM_DELETE_WINDOW", self.on_canvas_settings_close)
        else:
            messagebox.showerror("Error", "Canvas Settings window is already open.")
            self.canvas_settings_window.focus_force()
        
        set_active_window("canvas_settings")

    def on_canvas_settings_close(self):
        if self.canvas_settings_window:
            self.canvas_settings_window.destroy()
            self.canvas_settings_window = None
            gui_manager.unregister_window("canvas_settings_window")
            set_active_window("canvas_frame")

    def switch_mode(self, mode):
        if mode == self.current_mode:
            return

        self.current_mode = mode
        self.canvas_frame.place_forget()
        self.build_frame.place_forget()

        if mode == "CANVAS":
            self.canvas_button.config(bg="#333333", activebackground="#4a4a4a")
            self.build_button.config(bg="#4a4a4a", activebackground="#666666")
            self.canvas_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.8, relheight=0.8)
            set_active_window("canvas_frame")
        elif mode == "BUILD":
            self.build_button.config(bg="#333333", activebackground="#4a4a4a")
            self.canvas_button.config(bg="#4a4a4a", activebackground="#666666")
            self.build_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.8, relheight=0.8)
            set_active_window("build_frame")

        if self.canvas_settings_window and self.canvas_settings_window.winfo_exists():
            self.on_canvas_settings_close()

    def load_advanced_settings(self):
        settings_file = r'agent_gen\saved_agents\advanced_settings.json'
        if os.path.exists(settings_file):
            with open(settings_file, 'r', encoding='utf-8') as file:
                return json.load(file)
        else:
            return {
                "Top p": 1.0,
                "Top k": 50,
                "Temperature": 1.0,
                "Max output length": 8000
            }


if __name__ == "__main__":
    app = MainApp()
    app.mainloop()