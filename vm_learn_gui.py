# vm_learn_gui.py
import tkinter as tk
import customtkinter as ctk
import asyncio
from vm_learn_main import VMLearning
from vm_learn_loop import VMLearningLoop
from PIL import ImageTk, Image
from gui_element_manager import register_window, register_element, set_active_window, gui_manager
import os   
import shutil

class VMLearningGUI:
    def __init__(self, parent, close_callback):
        self.parent = parent
        self.close_callback = close_callback
        self.window = ctk.CTkToplevel(parent)
        self.window.title("VM Learn")
        self.window.geometry("800x600")
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)

        register_window("vm_learn", self.window)
        self.window.bind("<FocusIn>", self.on_window_focus)

        self.vm_learning = VMLearning()
        self.vm_learning_loop = None
        self.current_vm = None
        self.setup_guide_window = None
        self.generated_requests = []
        self.create_widgets()

    def on_window_focus(self, event):
        # Only set as active if no other window (like a dialog) is currently active
        if gui_manager.get_active_window() != "vm_learn" and not gui_manager.get_active_window().endswith("_dialog"):
            set_active_window("vm_learn")
        
    def create_widgets(self):
        # Main frame
        main_frame = ctk.CTkFrame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        register_element("vm_learn", "main_frame", main_frame, "frame")

        # Left frame
        left_frame = ctk.CTkFrame(main_frame, width=200)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_frame.pack_propagate(False)
        register_element("vm_learn", "left_frame", left_frame, "frame")

        # Start/Setup VM button
        self.start_vm_btn = ctk.CTkButton(left_frame, text="Start/Setup VM", command=self.start_setup_vm_and_guide)
        self.start_vm_btn.pack(pady=(0, 10), padx=10, fill=tk.X)
        register_element("vm_learn", "start_vm_btn", self.start_vm_btn, "button")

        # Generate User Query button
        self.generate_query_btn = ctk.CTkButton(left_frame, text="Generate User Query", command=self.generate_user_query)
        self.generate_query_btn.pack(pady=(0, 10), padx=10, fill=tk.X)
        register_element("vm_learn", "generate_query_btn", self.generate_query_btn, "button")

        # Show/Hide VM switch
        self.show_vm_var = ctk.BooleanVar(value=False)
        self.show_vm_switch = ctk.CTkSwitch(left_frame, text="Show VM", variable=self.show_vm_var, 
                                            command=self.toggle_vm_visibility)
        self.show_vm_switch.pack(pady=(0, 10), padx=10)
        register_element("vm_learn", "show_vm_switch", self.show_vm_switch, "switch")

        # User request display canvas
        self.user_request_frame = ctk.CTkFrame(left_frame)
        self.user_request_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        register_element("vm_learn", "user_request_frame", self.user_request_frame, "frame")

        self.user_request_canvas = ctk.CTkTextbox(self.user_request_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.user_request_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        register_element("vm_learn", "user_request_canvas", self.user_request_canvas, "textbox")

        user_request_scrollbar = ctk.CTkScrollbar(self.user_request_frame, command=self.user_request_canvas.yview)
        user_request_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        register_element("vm_learn", "user_request_scrollbar", user_request_scrollbar, "scrollbar")

        self.user_request_canvas.configure(yscrollcommand=user_request_scrollbar.set)

        # Right frame
        right_frame = ctk.CTkFrame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        register_element("vm_learn", "right_frame", right_frame, "frame")

        # Output canvas
        self.output_frame = ctk.CTkFrame(right_frame)
        self.output_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        register_element("vm_learn", "output_frame", self.output_frame, "frame")

        self.output_canvas = ctk.CTkTextbox(self.output_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.output_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        register_element("vm_learn", "output_canvas", self.output_canvas, "textbox")

        output_scrollbar = ctk.CTkScrollbar(self.output_frame, command=self.output_canvas.yview)
        output_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        register_element("vm_learn", "output_scrollbar", output_scrollbar, "scrollbar")

        self.output_canvas.configure(yscrollcommand=output_scrollbar.set)

        # Input frame
        input_frame = ctk.CTkFrame(right_frame)
        input_frame.pack(fill=tk.X)
        register_element("vm_learn", "input_frame", input_frame, "frame")

        # Input box
        self.input_box = ctk.CTkEntry(input_frame)
        self.input_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        register_element("vm_learn", "input_box", self.input_box, "entry")

        # Request button
        self.request_btn = ctk.CTkButton(input_frame, text="Request", command=self.send_request)
        self.request_btn.pack(side=tk.RIGHT)
        register_element("vm_learn", "request_btn", self.request_btn, "button")

        # Screenshot frame
        self.screenshot_frame = ctk.CTkFrame(self.window, width=780, height=200)
        register_element("vm_learn", "screenshot_frame", self.screenshot_frame, "frame")
        self.screenshot_label = ctk.CTkLabel(self.screenshot_frame, text="")
        self.screenshot_label.pack(expand=True, fill=tk.BOTH)
        register_element("vm_learn", "screenshot_label", self.screenshot_label, "label")

    def start_setup_vm_and_guide(self):
        if self.current_vm is None or not self.vm_learning.is_vm_running(self.current_vm):
            self.get_vm_name()
        else:
            self.wait_for_vm_ready()

    def get_vm_name(self):
        input_dialog = ctk.CTkInputDialog(text="Enter VM Name:", title="VM Setup")
        register_window("vm_setup_dialog", input_dialog)
        set_active_window("vm_setup_dialog")
        vm_name = input_dialog.get_input()
        gui_manager.unregister_window("vm_setup_dialog")
        set_active_window("vm_learn")
        
        if vm_name:
            result = self.vm_learning.setup_virtual_machine(vm_name)
            self.print_to_output(result["message"])
            if result["status"] == "success":
                self.current_vm = vm_name
                self.wait_for_vm_ready()
            else:
                self.show_error_and_retry(f"Failed to set up VM. {result['message']}")
        else:
            self.show_error_and_retry("VM name cannot be empty. Please try again.")

    def show_error_and_retry(self, message):
        error_dialog = ctk.CTkToplevel(self.window)
        error_dialog.title("Error")
        error_dialog.geometry("400x200")
        
        label = ctk.CTkLabel(error_dialog, text=message, wraplength=350)
        label.pack(pady=20)
        
        retry_button = ctk.CTkButton(error_dialog, text="Retry", command=lambda: [error_dialog.destroy(), self.get_vm_name()])
        retry_button.pack(pady=10)
        
        cancel_button = ctk.CTkButton(error_dialog, text="Cancel", command=error_dialog.destroy)
        cancel_button.pack(pady=10)

    def wait_for_vm_ready(self):
        if self.current_vm and self.vm_learning.is_vm_running(self.current_vm):
            self.open_setup_guide_window()
        else:
            self.window.after(1000, self.wait_for_vm_ready)

    def open_setup_guide_window(self):
        if self.setup_guide_window is None or not self.setup_guide_window.winfo_exists():
            self.setup_guide_window = VMSetupGuideWindow(self.window, self.vm_learning, self.current_vm, self.generated_requests)

    def generate_user_query(self):
        input_dialog = ctk.CTkInputDialog(text="Enter number of queries to generate:", title="Generate Queries")
        register_window("query_gen_dialog", input_dialog)
        set_active_window("query_gen_dialog")
        count = input_dialog.get_input()
        gui_manager.unregister_window("query_gen_dialog")
        set_active_window("vm_learn")
        if count is not None:
            try:
                count = int(count)
                queries = self.vm_learning.generate_user_queries(count)
                self.generated_requests.extend(queries)
                for query in queries:
                    self.print_to_user_request(query)
                self.print_to_output(f"Generated {len(queries)} user queries.")
            except ValueError:
                self.print_to_output("Invalid input. Please enter a number.")
        else:
            self.print_to_output("Query generation cancelled.")

    def toggle_vm_visibility(self):
        if not self.current_vm:
            self.print_to_output("Please start a VM first.")
            self.show_vm_var.set(False)
            return

        visibility = self.show_vm_var.get()
        result = self.vm_learning.set_vm_visibility(self.current_vm, visibility)
        self.print_to_output(result)

        if visibility:
            self.screenshot_frame.pack(fill=tk.X, pady=10, padx=10)
            self.window.geometry("800x800")
            self.window.after(1000, self.update_screenshot)
        else:
            self.screenshot_frame.pack_forget()
            self.window.geometry("800x600")
            self.screenshot_label.configure(image=None)
            self.screenshot_label.image = None

    def resize_image(self, image, max_width, max_height):
        width, height = image.size
        aspect_ratio = width / height

        if width > max_width:
            width = max_width
            height = int(width / aspect_ratio)

        if height > max_height:
            height = max_height
            width = int(height * aspect_ratio)

        return image.resize((width, height), Image.LANCZOS)

    def update_screenshot(self):
        if self.show_vm_var.get() and self.current_vm:
            screenshot = self.vm_learning.take_screenshot(self.current_vm)
            if isinstance(screenshot, Image.Image):
                resized_screenshot = self.resize_image(screenshot, 770, 190)
                photo = ImageTk.PhotoImage(resized_screenshot)
                self.screenshot_label.configure(image=photo)
                self.screenshot_label.image = photo
            elif isinstance(screenshot, str):
                self.print_to_output(f"Screenshot error: {screenshot}")
            if self.show_vm_var.get():
                self.window.after(1000, self.update_screenshot)

    def send_request(self):
        request = self.input_box.get()
        self.print_to_output(f"Sending request: {request}")
        result = self.vm_learning.process_request(request)
        self.print_to_output(result)
        self.input_box.delete(0, tk.END)

    def print_to_output(self, message):
        self.output_canvas.configure(state=tk.NORMAL)
        self.output_canvas.insert(tk.END, message + "\n")
        self.output_canvas.configure(state=tk.DISABLED)
        self.output_canvas.see(tk.END)

    def print_to_user_request(self, message):
        self.user_request_canvas.configure(state=tk.NORMAL)
        self.user_request_canvas.insert(tk.END, message + "\n")
        self.user_request_canvas.configure(state=tk.DISABLED)
        self.user_request_canvas.see(tk.END)

    def close_window(self):
        if self.current_vm:
            self.vm_learning.set_vm_visibility(self.current_vm, False)
        gui_manager.unregister_window("vm_learn")
        set_active_window("main_window")
        if self.close_callback:
            self.close_callback()

    def lift(self):
        self.window.lift()
        self.window.focus_force()

class VMSetupGuideWindow:
    def __init__(self, parent, vm_learning, vm_name, generated_requests):
        self.window = ctk.CTkToplevel(parent)
        self.window.title("VM Setup Guide")
        self.window.geometry("700x1000")
        self.vm_learning = vm_learning
        self.vm_name = vm_name
        self.generated_requests = generated_requests
        self.training_list = []
        self.vm_learning_loop = VMLearningLoop(vm_learning)
        
        register_window("vm_setup_guide", self.window)
        self.window.bind("<FocusIn>", self.on_window_focus)

        self.create_widgets()

    def on_window_focus(self, event):
        if gui_manager.get_active_window() != "vm_setup_guide":
            set_active_window("vm_setup_guide")

    def create_widgets(self):
        main_frame = ctk.CTkFrame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        step1_frame = self.create_step_frame(main_frame, "Step 1: Setup Shared Folder")
        ctk.CTkLabel(step1_frame, text="Set up 'vm_share' as the shared folder in your VM settings.").pack(pady=5)

        step2_frame = self.create_step_frame(main_frame, "Step 2: Download and Run Script")
        ctk.CTkLabel(step2_frame, text="Download the script and run it in the VM environment.").pack(pady=5)
        ctk.CTkButton(step2_frame, text="Download Script", command=self.download_script).pack(pady=5)

        requests_frame = self.create_step_frame(main_frame, "Generated User Requests")
        self.requests_listbox = self.create_scrollable_listbox(requests_frame)
        self.populate_requests_listbox()

        self.add_button = ctk.CTkButton(main_frame, text="Add to Training List", command=self.add_to_training_list)
        self.add_button.pack(pady=10)

        training_frame = self.create_step_frame(main_frame, "Training List")
        self.training_listbox = self.create_scrollable_listbox(training_frame)

        self.start_training_btn = ctk.CTkButton(main_frame, text="Start Training", command=self.start_training)
        self.start_training_btn.pack(pady=(0, 10), padx=10, fill=tk.X)
        
        self.stop_training_btn = ctk.CTkButton(main_frame, text="Stop Training", command=self.stop_training, state="disabled")
        self.stop_training_btn.pack(pady=(0, 10), padx=10, fill=tk.X)
        
        self.training_status_label = ctk.CTkLabel(main_frame, text="Training Status: Not Started")
        self.training_status_label.pack(pady=(0, 10), padx=10)

    def create_step_frame(self, parent, title):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill=tk.X, pady=10)
        ctk.CTkLabel(frame, text=title, font=("Helvetica", 16, "bold")).pack(pady=5)
        return frame

    def create_scrollable_listbox(self, parent):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        listbox = tk.Listbox(frame, selectmode=tk.SINGLE, bg="#2b2b2b", fg="white", 
                             selectbackground="#1f538d", highlightthickness=0)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ctk.CTkScrollbar(frame, command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox.config(yscrollcommand=scrollbar.set)
        
        return listbox

    def populate_requests_listbox(self):
        for request in self.generated_requests:
            self.requests_listbox.insert(tk.END, request)

    def add_to_training_list(self):
        selected_indices = self.requests_listbox.curselection()
        if selected_indices:
            selected_index = selected_indices[0]
            selected_request = self.requests_listbox.get(selected_index)
            if selected_request not in self.training_list:
                self.training_list.append(selected_request)
                self.training_listbox.insert(tk.END, selected_request)

    def download_script(self):
        script_path = os.path.join(os.path.dirname(__file__), "vm_learn_data", "vm_action_executor.py")
        if os.path.exists(script_path):
            dest_path = os.path.join(self.vm_learning.get_shared_folder_path(), "vm_action_executor.py")
            shutil.copy2(script_path, dest_path)
            self.print_to_output(f"Script downloaded to shared folder: {dest_path}")
        else:
            self.print_to_output("Error: Script executable not found.")

    def start_training(self):
        self.start_training_btn.configure(state="disabled")
        self.stop_training_btn.configure(state="normal")
        asyncio.run(self.run_training())

    async def run_training(self):
        result = await self.vm_learning_loop.start_training(self.training_list)
        self.update_training_status(result)

    def stop_training(self):
        self.stop_training_btn.configure(state="disabled")
        asyncio.run(self.stop_training_task())

    async def stop_training_task(self):
        result = await self.vm_learning_loop.stop_training()
        self.update_training_status(result)

    def update_training_status(self, result=None):
        status = self.vm_learning_loop.get_training_status()
        if status["in_progress"]:
            status_text = f"Training in progress: {status['current_index']}/{status['total_requests']}"
        elif status["stop_requested"]:
            status_text = "Training stopped"
        else:
            status_text = "Training completed"
        
        self.training_status_label.configure(text=f"Training Status: {status_text}")
        
        if not status["in_progress"] and not status["stop_requested"]:
            self.start_training_btn.configure(state="normal")
            self.stop_training_btn.configure(state="disabled")
    
    def print_to_output(self, message):
        # Will display messages in the GUI
        pass

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    app = VMLearningGUI(root, None)
    root.mainloop()