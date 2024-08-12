# memory_gui.py
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from memory_main import MemoryManager
import json
from typing import List, Dict, Any
from gui_element_manager import register_window, register_element, set_active_window, gui_manager
import os

class MemoryGUI:
    def __init__(self, root, close_callback):
        self.root = root
        self.close_callback = close_callback
        self.memory_manager = MemoryManager()
        
        register_window("memory_gui", self.root)
        self.root.bind("<FocusIn>", lambda e: set_active_window("memory_gui"))
        set_active_window("memory_gui")

        self.setup_styles()
        self.create_widgets()
        self.load_memory()

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        bg_color = "#2b2b2b"
        fg_color = "#ffffff"
        accent_color = "#3a7ebf"
        
        self.style.configure("TNotebook", background=bg_color)
        self.style.configure("TNotebook.Tab", background=bg_color, foreground=fg_color, padding=[10, 5])
        self.style.map("TNotebook.Tab", background=[("selected", accent_color)])
        
        self.style.configure("Treeview", 
                             background=bg_color, 
                             foreground=fg_color, 
                             rowheight=25, 
                             fieldbackground=bg_color)
        self.style.map("Treeview", background=[("selected", accent_color)])
        
        self.style.configure("Treeview.Heading", 
                             background=accent_color, 
                             foreground=fg_color, 
                             relief="flat")
        self.style.map("Treeview.Heading", 
                       background=[("active", accent_color)])

    def create_widgets(self):
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(expand=True, fill='both', padx=10, pady=10)
        register_element("memory_gui", "main_frame", main_frame, "frame")

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(expand=True, fill='both', padx=10, pady=10)
        register_element("memory_gui", "notebook", self.notebook, "notebook")
        
        self.long_term_frame = ttk.Frame(self.notebook)
        self.short_term_frame = ttk.Frame(self.notebook)
        self.abilities_frame = ttk.Frame(self.notebook)
        self.user_preferences_frame = ttk.Frame(self.notebook)
        
        self.notebook.add(self.long_term_frame, text='Long-Term Memory')
        self.notebook.add(self.short_term_frame, text='Short-Term Memory')
        self.notebook.add(self.abilities_frame, text='Abilities')
        self.notebook.add(self.user_preferences_frame, text='User Preferences')
        
        self.long_term_memory_tree = self.create_treeview(self.long_term_frame, ['Content', 'Importance', 'Context'])
        self.short_term_memory_tree = self.create_treeview(self.short_term_frame, ['Content', 'Expiry', 'Context'])
        self.abilities_tree = self.create_treeview(self.abilities_frame, ['Name', 'Description', 'Steps', 'Usage Example'])
        self.user_preferences_tree = self.create_treeview(self.user_preferences_frame, ['Preference', 'Value', 'Context'])
        
        self.create_control_buttons(main_frame)

    def create_treeview(self, parent, columns):
        tree = ttk.Treeview(parent, columns=columns, show='headings')
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=200)
        
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side="left", expand=True, fill='both')
        scrollbar.pack(side="right", fill="y")
        
        tree.bind("<Double-1>", self.on_double_click)
        register_element("memory_gui", f"{parent.winfo_name()}_tree", tree, "treeview")
        register_element("memory_gui", f"{parent.winfo_name()}_scrollbar", scrollbar, "scrollbar")
        return tree
    
    def create_control_buttons(self, parent):
        button_frame = ctk.CTkFrame(parent)
        button_frame.pack(fill='x', padx=10, pady=10)
        register_element("memory_gui", "button_frame", button_frame, "frame")
        
        buttons = [
            ("Refresh", self.load_memory),
            ("Add Memory", self.add_memory),
            ("Edit Memory", self.edit_memory),
            ("Delete Memory", self.delete_memory),
            ("Feed File", self.open_feed_file_window)
        ]
        
        for text, command in buttons:
            button = ctk.CTkButton(button_frame, text=text, command=command)
            button.pack(side='left', padx=5)
            register_element("memory_gui", f"{text.lower()}_button", button, "button")

    def load_memory(self):
        all_memory = self.memory_manager.get_all_memory()
        print(f"Loaded memory: {json.dumps(all_memory, indent=2)}")
        
        self.update_treeview(self.long_term_memory_tree, all_memory['long_term_memory'], ['content', 'importance', 'context'])
        self.update_treeview(self.short_term_memory_tree, all_memory['short_term_memory'], ['content', 'expiry', 'context'])
        self.update_treeview(self.abilities_tree, all_memory['abilities'], ['name', 'description', 'steps', 'usage_example'])
        self.update_treeview(self.user_preferences_tree, all_memory['user_preferences'], ['preference', 'value', 'context'])

    def update_treeview(self, tree, data, columns):
        tree.delete(*tree.get_children())
        for item in data:
            values = [item.get(col, '') for col in columns]
            tree.insert('', 'end', values=values)

    def on_double_click(self, event):
        tree = event.widget
        item = tree.selection()[0]
        values = tree.item(item, "values")
        self.show_memory_details(values)

    def show_memory_details(self, values):
        details_window = ctk.CTkToplevel(self.root)
        register_window("memory_details", details_window)
        details_window.title("Memory Details")
        details_window.geometry("400x300")
        details_window.bind("<FocusIn>", lambda e: set_active_window("memory_details"))
        set_active_window("memory_details")
        
        for i, value in enumerate(values):
            label = ctk.CTkLabel(details_window, text=f"{self.get_column_name(i)}: {value}", wraplength=380)
            label.pack(pady=5, padx=10, anchor="w")
            register_element("memory_details", f"label_{i}", label, "label")

    def get_column_name(self, index):
        current_tab = self.notebook.tab(self.notebook.select(), "text")
        if current_tab == "Long-Term Memory":
            return ["Content", "Importance", "Context"][index]
        elif current_tab == "Short-Term Memory":
            return ["Content", "Expiry", "Context"][index]
        elif current_tab == "Abilities":
            return ["Name", "Description", "Steps", "Usage Example"][index]
        elif current_tab == "User Preferences":
            return ["Preference", "Value", "Context"][index]

    def add_memory(self):
        add_window = ctk.CTkToplevel(self.root)
        register_window("add_memory", add_window)
        add_window.title("Add Memory")
        add_window.geometry("400x700")
        add_window.resizable(True, True)
        add_window.grab_set()
        add_window.lift()
        add_window.bind("<FocusIn>", lambda e: set_active_window("add_memory"))
        set_active_window("add_memory")

        main_frame = ctk.CTkFrame(add_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        register_element("add_memory", "main_frame", main_frame, "frame")

        memory_type_var = ctk.StringVar(value="long_term_memory")
        ctk.CTkLabel(main_frame, text="Memory Type:").pack(pady=(0, 5))
        memory_type_menu = ctk.CTkOptionMenu(main_frame, variable=memory_type_var, 
                        values=["long_term_memory", "short_term_memory", "abilities", "user_preferences"],
                        command=lambda _: self.update_add_window(main_frame, memory_type_var.get()))
        memory_type_menu.pack(pady=(0, 10))
        register_element("add_memory", "memory_type_menu", memory_type_menu, "optionmenu")

        self.content_frame = ctk.CTkFrame(main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        register_element("add_memory", "content_frame", self.content_frame, "frame")

        self.update_add_window(main_frame, "long_term_memory")

    def update_add_window(self, parent, memory_type):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        if memory_type == "long_term_memory":
            self.create_long_term_memory_fields(self.content_frame)
        elif memory_type == "short_term_memory":
            self.create_short_term_memory_fields(self.content_frame)
        elif memory_type == "abilities":
            self.create_abilities_fields(self.content_frame)
        elif memory_type == "user_preferences":
            self.create_user_preferences_fields(self.content_frame)

        add_save_button = ctk.CTkButton(self.content_frame, text="Save", command=lambda: self.save_memory(memory_type))
        add_save_button.pack(pady=10, padx=10, fill=tk.X)
        register_element("add_memory", "add_save_button", add_save_button, "button")

    def create_long_term_memory_fields(self, parent):
        ctk.CTkLabel(parent, text="Content:").pack(pady=(10, 5), padx=10, anchor="w")
        self.content_entry = ctk.CTkTextbox(parent, height=150)
        self.content_entry.pack(pady=(0, 10), padx=10, fill=tk.BOTH, expand=True)
        register_element("add_memory", "content_entry", self.content_entry, "textbox")

        ctk.CTkLabel(parent, text="Importance (1-10):").pack(pady=(0, 5), padx=10, anchor="w")
        self.importance_entry = ctk.CTkEntry(parent)
        self.importance_entry.pack(pady=(0, 10), padx=10, fill=tk.X)
        register_element("add_memory", "importance_entry", self.importance_entry, "entry")

        ctk.CTkLabel(parent, text="Context:").pack(pady=(0, 5), padx=10, anchor="w")
        self.context_entry = ctk.CTkEntry(parent)
        self.context_entry.pack(pady=(0, 10), padx=10, fill=tk.X)
        register_element("add_memory", "context_entry", self.context_entry, "entry")

    def create_short_term_memory_fields(self, parent):
        ctk.CTkLabel(parent, text="Content:").pack(pady=(10, 5), padx=10, anchor="w")
        self.content_entry = ctk.CTkTextbox(parent, height=150)
        self.content_entry.pack(pady=(0, 10), padx=10, fill=tk.BOTH, expand=True)
        register_element("add_memory", "content_entry", self.content_entry, "textbox")

        ctk.CTkLabel(parent, text="Expiry (YYYY-MM-DD):").pack(pady=(0, 5), padx=10, anchor="w")
        self.expiry_entry = ctk.CTkEntry(parent)
        self.expiry_entry.pack(pady=(0, 10), padx=10, fill=tk.X)
        register_element("add_memory", "expiry_entry", self.expiry_entry, "entry")

        ctk.CTkLabel(parent, text="Context:").pack(pady=(0, 5), padx=10, anchor="w")
        self.context_entry = ctk.CTkEntry(parent)
        self.context_entry.pack(pady=(0, 10), padx=10, fill=tk.X)
        register_element("add_memory", "context_entry", self.context_entry, "entry")

    def create_abilities_fields(self, parent):
        ctk.CTkLabel(parent, text="Name:").pack(pady=(10, 5), padx=10, anchor="w")
        self.name_entry = ctk.CTkEntry(parent)
        self.name_entry.pack(pady=(0, 10), padx=10, fill=tk.X)
        register_element("add_memory", "name_entry", self.name_entry, "entry")

        ctk.CTkLabel(parent, text="Description:").pack(pady=(0, 5), padx=10, anchor="w")
        self.description_entry = ctk.CTkTextbox(parent, height=100)
        self.description_entry.pack(pady=(0, 10), padx=10, fill=tk.BOTH, expand=True)
        register_element("add_memory", "description_entry", self.description_entry, "textbox")

        ctk.CTkLabel(parent, text="Steps:").pack(pady=(0, 5), padx=10, anchor="w")
        self.steps_entry = ctk.CTkTextbox(parent, height=100)
        self.steps_entry.pack(pady=(0, 10), padx=10, fill=tk.BOTH, expand=True)
        register_element("add_memory", "steps_entry", self.steps_entry, "textbox")

        ctk.CTkLabel(parent, text="Usage Example:").pack(pady=(0, 5), padx=10, anchor="w")
        self.usage_example_entry = ctk.CTkEntry(parent)
        self.usage_example_entry.pack(pady=(0, 10), padx=10, fill=tk.X)
        register_element("add_memory", "usage_example_entry", self.usage_example_entry, "entry")

    def create_user_preferences_fields(self, parent):
        ctk.CTkLabel(parent, text="Preference:").pack(pady=(10, 5), padx=10, anchor="w")
        self.preference_entry = ctk.CTkEntry(parent)
        self.preference_entry.pack(pady=(0, 10), padx=10, fill=tk.X)
        register_element("add_memory", "preference_entry", self.preference_entry, "entry")

        ctk.CTkLabel(parent, text="Value:").pack(pady=(0, 5), padx=10, anchor="w")
        self.value_entry = ctk.CTkEntry(parent)
        self.value_entry.pack(pady=(0, 10), padx=10, fill=tk.X)
        register_element("add_memory", "value_entry", self.value_entry, "entry")

        ctk.CTkLabel(parent, text="Context:").pack(pady=(0, 5), padx=10, anchor="w")
        self.context_entry = ctk.CTkEntry(parent)
        self.context_entry.pack(pady=(0, 10), padx=10, fill=tk.X)
        register_element("add_memory", "context_entry", self.context_entry, "entry")


    def save_memory(self, memory_type):
        new_memory = {}

        if memory_type == "long_term_memory":
            try:
                importance_value = int(self.importance_entry.get()) if self.importance_entry.get().isdigit() else 5
            except ValueError:
                importance_value = 5

            new_memory = {
                "content": self.content_entry.get("1.0", tk.END).strip(),
                "importance": importance_value,
                "context": self.context_entry.get()
            }
        elif memory_type == "short_term_memory":
            new_memory = {
                "content": self.content_entry.get("1.0", tk.END).strip(),
                "expiry": self.expiry_entry.get(),
                "context": self.context_entry.get()
            }
        elif memory_type == "abilities":
            new_memory = {
                "name": self.name_entry.get(),
                "description": self.description_entry.get("1.0", tk.END).strip(),
                "steps": self.steps_entry.get("1.0", tk.END).strip(),
                "usage_example": self.usage_example_entry.get()
            }
        elif memory_type == "user_preferences":
            new_memory = {
                "preference": self.preference_entry.get(),
                "value": self.value_entry.get(),
                "context": self.context_entry.get()
            }

        if not new_memory.get("content") and not new_memory.get("name") and not new_memory.get("preference"):
            messagebox.showerror("Error", "Main content cannot be empty")
            return

        all_memory = self.memory_manager.get_memory(memory_type)
        print(f"Current {memory_type}: {json.dumps(all_memory, indent=2)}")

        if memory_type == "long_term_memory":
            if not any(mem["content"] == new_memory["content"] and mem["importance"] == new_memory["importance"] and mem["context"] == new_memory["context"] for mem in all_memory):
                all_memory.append(new_memory)
        elif memory_type == "short_term_memory":
            if not any(mem["content"] == new_memory["content"] and mem["expiry"] == new_memory["expiry"] and mem["context"] == new_memory["context"] for mem in all_memory):
                all_memory.append(new_memory)
        elif memory_type == "abilities":
            if not any(mem["name"] == new_memory["name"] and mem["description"] == new_memory["description"] and mem["steps"] == new_memory["steps"] and mem["usage_example"] == new_memory["usage_example"] for mem in all_memory):
                all_memory.append(new_memory)
        elif memory_type == "user_preferences":
            if not any(mem["preference"] == new_memory["preference"] and mem["value"] == new_memory["value"] and mem["context"] == new_memory["context"] for mem in all_memory):
                all_memory.append(new_memory)

        self.save_memory_gui(memory_type, all_memory)
        self.load_memory()

        gui_manager.unregister_window("add_memory")
        self.content_frame.master.master.destroy()


    def save_memory_gui(self, memory_type: str, data: List[Dict[str, Any]]):
        file_path = {
            "long_term_memory": "memory_data/long_term_memory.json",
            "short_term_memory": "memory_data/short_term_memory.json",
            "abilities": "memory_data/abilities_memory.json",
            "user_preferences": "memory_data/user_preferences.json"
        }.get(memory_type)

        if not file_path:
            raise ValueError(f"Invalid memory type: {memory_type}")

        with self.memory_manager.lock: 
            with open(file_path, 'w') as f: 
                json.dump(data, f, indent=4)
        print(f"Memory saved for {memory_type}: {json.dumps(data, indent=2)}") 


    def edit_memory(self):
        selected_tab = self.notebook.tab(self.notebook.select(), "text").lower().replace(" ", "_").replace("-", "_")
        tree_name = f"{selected_tab}_tree"
        if hasattr(self, tree_name):
            tree = getattr(self, tree_name)
            selected_items = tree.selection()
            if not selected_items:
                messagebox.showerror("Error", "Please select a memory to edit")
                return
            item = selected_items[0]
            values = tree.item(item, "values")
            self.open_edit_window(selected_tab, values)
        else:
            messagebox.showerror("Error", f"No tree view found for {selected_tab}")

    def open_edit_window(self, memory_type, values):
        edit_window = ctk.CTkToplevel(self.root)
        register_window("edit_memory", edit_window)
        edit_window.title("Edit Memory")
        edit_window.geometry("400x700")
        edit_window.resizable(True, True)
        edit_window.grab_set()
        edit_window.lift()
        edit_window.bind("<FocusIn>", lambda e: set_active_window("edit_memory"))
        set_active_window("edit_memory")

        main_frame = ctk.CTkFrame(edit_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        register_element("edit_memory", "main_frame", main_frame, "frame")

        self.content_frame = ctk.CTkFrame(main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        register_element("edit_memory", "content_frame", self.content_frame, "frame")

        self.update_edit_window(main_frame, memory_type, values)

    def update_edit_window(self, parent, memory_type, values):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        if memory_type == "long_term_memory":
            self.create_long_term_memory_fields(self.content_frame)
            self.content_entry.insert("1.0", values[0])
            self.importance_entry.insert(0, values[1])
            self.context_entry.insert(0, values[2])
        elif memory_type == "short_term_memory":
            self.create_short_term_memory_fields(self.content_frame)
            self.content_entry.insert("1.0", values[0])
            self.expiry_entry.insert(0, values[1])
            self.context_entry.insert(0, values[2])
        elif memory_type == "abilities":
            self.create_abilities_fields(self.content_frame)
            self.name_entry.insert(0, values[0])
            self.description_entry.insert("1.0", values[1])
            self.steps_entry.insert("1.0", values[2])
            self.usage_example_entry.insert(0, values[3])
        elif memory_type == "user_preferences":
            self.create_user_preferences_fields(self.content_frame)
            self.preference_entry.insert(0, values[0])
            self.value_entry.insert(0, values[1])
            self.context_entry.insert(0, values[2])

        edit_save_button = ctk.CTkButton(self.content_frame, text="Save", command=lambda: self.save_edited_memory(memory_type, values[0], values))
        edit_save_button.pack(pady=10, padx=10, fill=tk.X)
        register_element("edit_memory", "edit_save_button", edit_save_button, "button")

    def save_edited_memory(self, memory_type, original_content, original_values):
        new_memory = {}
        try:
            importance_value = int(self.importance_entry.get()) if self.importance_entry.get().isdigit() else 5
        except ValueError:
            importance_value = 5

        if memory_type == "long_term_memory":
            new_memory = {
                "content": self.content_entry.get("1.0", tk.END).strip(),
                "importance": importance_value,
                "context": self.context_entry.get()
            }
        elif memory_type == "short_term_memory":
            new_memory = {
                "content": self.content_entry.get("1.0", tk.END).strip(),
                "expiry": self.expiry_entry.get(),
                "context": self.context_entry.get()
            }
        elif memory_type == "abilities":
            new_memory = {
                "name": self.name_entry.get(),
                "description": self.description_entry.get("1.0", tk.END).strip(),
                "steps": self.steps_entry.get("1.0", tk.END).strip(),
                "usage_example": self.usage_example_entry.get()
            }
        elif memory_type == "user_preferences":
            new_memory = {
                "preference": self.preference_entry.get(),
                "value": self.value_entry.get(),
                "context": self.context_entry.get()
            }

        if not new_memory.get("content") and not new_memory.get("name") and not new_memory.get("preference"):
            messagebox.showerror("Error", "Main content cannot be empty")
            return

        all_memory = self.memory_manager.get_memory(memory_type)
        print(f"Editing {memory_type} before save: {json.dumps(all_memory, indent=2)}")
        for i, memory in enumerate(all_memory):
            if (memory_type == "long_term_memory" and memory["content"] == original_content and str(memory["importance"]) == original_values[1] and memory["context"] == original_values[2]) or \
            (memory_type == "short_term_memory" and memory["content"] == original_content and memory["expiry"] == original_values[1] and memory["context"] == original_values[2]) or \
            (memory_type == "abilities" and memory["name"] == original_content and memory["description"] == original_values[1] and memory["steps"] == original_values[2] and memory["usage_example"] == original_values[3]) or \
            (memory_type == "user_preferences" and memory["preference"] == original_content and memory["value"] == original_values[1] and memory["context"] == original_values[2]):
                all_memory[i] = new_memory
                break

        self.save_memory_gui(memory_type, all_memory)
        self.load_memory()
        
        gui_manager.unregister_window("edit_memory")
        self.content_frame.master.master.destroy()


    def delete_memory(self):
        selected_tab = self.notebook.tab(self.notebook.select(), "text").lower().replace(" ", "_").replace("-", "_")
        tree_name = f"{selected_tab}_tree"
        print(f"Selected tab: {selected_tab}") 
        if hasattr(self, tree_name):
            tree = getattr(self, tree_name)
            selected_items = tree.selection()
            print(f"Selected items: {selected_items}") 
            if not selected_items:
                messagebox.showerror("Error", "Please select a memory to delete")
                return
            if messagebox.askyesno("Confirm Deletion", "Are you sure you want to delete the selected memory?"):
                item = selected_items[0]
                values = tree.item(item, "values")
                print(f"Deleting memory from {selected_tab}: {values}") 
                self.perform_delete(selected_tab, values)
        else:
            messagebox.showerror("Error", f"No tree view found for {selected_tab}")

    def perform_delete(self, memory_type, values):
        all_memory = self.memory_manager.get_memory(memory_type)
        print(f"Deleting from {memory_type} before: {json.dumps(all_memory, indent=2)}") 

        if memory_type == "long_term_memory":
            all_memory = [memory for memory in all_memory if not (memory["content"] == values[0] and str(memory["importance"]) == values[1] and memory["context"] == values[2])]
        elif memory_type == "short_term_memory":
            all_memory = [memory for memory in all_memory if not (memory["content"] == values[0] and memory["expiry"] == values[1] and memory["context"] == values[2])]
        elif memory_type == "abilities":
            all_memory = [memory for memory in all_memory if memory["name"] != values[0]]
        elif memory_type == "user_preferences":
            all_memory = [memory for memory in all_memory if not (memory["preference"] == values[0] and memory["value"] == values[1] and memory["context"] == values[2])]

        print(f"Deleting from {memory_type} after: {json.dumps(all_memory, indent=2)}")  

        self.save_memory_gui(memory_type, all_memory) 
        print(f"Memory after save for {memory_type}: {json.dumps(self.memory_manager.get_memory(memory_type), indent=2)}") 

        self.load_memory()

    def open_feed_file_window(self):
        feed_window = ctk.CTkToplevel(self.root)
        feed_window.title("Feed File")
        feed_window.geometry("300x200")
        feed_window.grab_set()
        feed_window.lift()

        ctk.CTkButton(feed_window, text="Train Data", command=lambda: self.feed_file("train")).pack(pady=10)
        ctk.CTkButton(feed_window, text="Observe Data", command=lambda: self.feed_file("observe")).pack(pady=10)
        ctk.CTkButton(feed_window, text="External File", command=lambda: self.feed_file("external")).pack(pady=10)

    def feed_file(self, file_type):
        if file_type == "train":
            file_path = r'action_data\ability_memory.json'
            if os.path.exists(file_path):
                with open(file_path, 'r') as file:
                    data = json.load(file)
                self.memory_manager.append_to_full_memory("TRAIN DATA", json.dumps(data))
                messagebox.showinfo("Success", "Train data has been fed to memory successfully.")
            else:
                messagebox.showwarning("File Not Found", "Train data file does not exist.")
        elif file_type == "observe":
            file_path = r'observe_data\observed_summary.txt'
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as file:
                    data = file.read()
                self.memory_manager.append_to_full_memory("OBSERVE DATA", data)
                messagebox.showinfo("Success", "Observe data has been fed to memory successfully.")
            else:
                messagebox.showwarning("File Not Found", "Observe data file does not exist.")
        else:
            file_path = tk.filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as file:
                    data = file.read()
                self.memory_manager.append_to_full_memory("EXTERNAL FILE", data)
                messagebox.showinfo("Success", "External file has been fed to memory successfully.")
            else:
                messagebox.showinfo("Cancelled", "No file was selected.")

