# ag_create_tool.py
import os
import tempfile
import json
import tkinter as tk
from tkinter import messagebox, scrolledtext
import subprocess
import threading
import ctypes
import time
from gui_element_manager import register_window, register_element, set_active_window, gui_manager

# Define necessary Windows API functions
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def get_hwnd_from_pid(pid):
    hwnd = ctypes.windll.user32.FindWindowExW(0, 0, None, None)
    while hwnd:
        hwnd_pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(hwnd_pid))
        if hwnd_pid.value == pid:
            return hwnd
        hwnd = ctypes.windll.user32.FindWindowExW(0, hwnd, None, None)
    return None

def embed_cmd(frame, proc):
    time.sleep(0.1) 

    hwnd_cmd = get_hwnd_from_pid(proc.pid)
    if hwnd_cmd:
        # Set cmd window to be a child of the Tkinter frame
        user32.SetParent(hwnd_cmd, frame.winfo_id())
        # Resize cmd window to fit the Tkinter frame
        user32.SetWindowPos(hwnd_cmd, None, 0, 0, frame.winfo_width(), frame.winfo_height(), 0)
    else:
        print("Unable to find cmd window.")

def show_create_tool_frame(main_app):
    main_app.build_frame.place_forget()

    create_tool_frame = tk.Frame(main_app.main_frame, bg="#2c2c2c", bd=2, relief="ridge", padx=10, pady=10)
    create_tool_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0, relheight=1.0)

    register_window("create_tool", create_tool_frame)
    create_tool_frame.bind("<FocusIn>", lambda e: set_active_window("create_tool"))
    set_active_window("create_tool")

    main_app.create_tool_frame = create_tool_frame

    close_button = tk.Button(
        create_tool_frame,
        text="X",
        font=("Helvetica", 14, "bold"),
        bg="#ff5555",
        fg="white",
        command=lambda: close_create_tool_frame(main_app)
    )
    close_button.place(x=902, y=5, width=25, height=25)
    register_element("create_tool", "close_button", close_button, "button")

    tool_name_entry = tk.Entry(create_tool_frame, font=("Helvetica", 16), fg="grey")
    tool_name_entry.insert(0, "Tool Name")
    tool_name_entry.bind("<FocusIn>", lambda event: clear_placeholder(event, "Tool Name"))
    tool_name_entry.bind("<FocusOut>", lambda event: restore_entry_placeholder(event, "Tool Name"))
    tool_name_entry.place(x=20, y=20, width=250, height=40)
    main_app.tool_name_entry = tool_name_entry
    register_element("create_tool", "tool_name_entry", tool_name_entry, "entry")

    tool_description_entry = tk.Text(create_tool_frame, font=("Helvetica", 16), fg="grey", wrap="word")
    tool_description_entry.insert(tk.END, "Tool Description")
    tool_description_entry.bind("<FocusIn>", lambda event: clear_text_placeholder(event, "Tool Description"))
    tool_description_entry.bind("<FocusOut>", lambda event: restore_text_placeholder(event, "Tool Description"))
    tool_description_entry.place(x=20, y=80, width=300, height=450)
    main_app.tool_description_entry = tool_description_entry
    register_element("create_tool", "tool_description_entry", tool_description_entry, "text")

    cmd_input_entry = tk.Entry(create_tool_frame, font=("Helvetica", 16), fg="grey")
    cmd_input_entry.insert(tk.END, "CMD Input")
    cmd_input_entry.bind("<FocusIn>", lambda event: clear_placeholder(event, "CMD Input"))
    cmd_input_entry.bind("<FocusOut>", lambda event: restore_entry_placeholder(event, "CMD Input"))
    cmd_input_entry.bind("<Return>", lambda event: send_cmd_to_window(main_app))
    cmd_input_entry.place(x=20, y=550, width=300, height=40)
    main_app.cmd_input_entry = cmd_input_entry
    register_element("create_tool", "cmd_input_entry", cmd_input_entry, "entry")

    code_editor = scrolledtext.ScrolledText(create_tool_frame, wrap=tk.WORD, font=("Courier", 14), bg="#1e1e1e", fg="white")
    code_editor.place(x=350, y=50, width=575, height=520)
    code_editor.bind("<Return>", lambda event: handle_python_indentation(event, code_editor))
    main_app.code_editor = code_editor
    register_element("create_tool", "code_editor", code_editor, "text")

    execute_button = tk.Button(
        create_tool_frame,
        text="Execute",
        font=("Helvetica", 14),
        bg="#4a4a4a",
        fg="white",
        command=lambda: execute_python_code(main_app)
    )
    execute_button.place(x=653.34, y=580, width=120, height=40)
    register_element("create_tool", "execute_button", execute_button, "button")

    clear_cmd_button = tk.Button(
        create_tool_frame,
        text="Clear CMD",
        font=("Helvetica", 14),
        bg="#4a4a4a",
        fg="white",
        command=lambda: clear_cmd_window(main_app)
    )
    clear_cmd_button.place(x=350, y=580, width=120, height=40)
    register_element("create_tool", "clear_cmd_button", clear_cmd_button, "button")

    open_cmd_button = tk.Button(
        create_tool_frame,
        text="Open CMD",
        font=("Helvetica", 14),
        bg="#4a4a4a",
        fg="white",
        command=lambda: open_cmd_window(main_app)
    )
    open_cmd_button.place(x=20, y=600, width=120, height=40)
    register_element("create_tool", "open_cmd_button", open_cmd_button, "button")

    clear_python_button = tk.Button(
        create_tool_frame,
        text="Clear Python",
        font=("Helvetica", 14),
        bg="#4a4a4a",
        fg="white",
        command=lambda: clear_python_output(main_app)
    )
    clear_python_button.place(x=501.67, y=580, width=120, height=40)
    register_element("create_tool", "clear_python_button", clear_python_button, "button")

    save_tool_button = tk.Button(
        create_tool_frame,
        text="Save Tool",
        font=("Helvetica", 14),
        bg="#4a4a4a",
        fg="white",
        command=lambda: save_tool(main_app)
    )
    save_tool_button.place(x=805, y=580, width=120, height=40)
    register_element("create_tool", "save_tool_button", save_tool_button, "button")

    send_cmd_button = tk.Button(
        create_tool_frame,
        text="Execute CMD",
        font=("Helvetica", 14),
        bg="#4a4a4a",
        fg="white",
        command=lambda: send_cmd_to_window(main_app)
    )
    send_cmd_button.place(x=170, y=600, width=120, height=40)
    register_element("create_tool", "send_cmd_button", send_cmd_button, "button")

    main_app.cmd_process = None
    main_app.cmd_process_id = None
    main_app.original_geometry = main_app.geometry()
    
    cmd_frame = tk.Frame(create_tool_frame, width=900, height=200, bg="white")
    cmd_frame.place(x=20, y=650)
    main_app.cmd_frame = cmd_frame
    register_element("create_tool", "cmd_frame", cmd_frame, "frame")

    main_app.after(1000, check_cmd_process, main_app)

def close_cmd_window(main_app):
    if main_app.cmd_process:
        main_app.cmd_process.terminate()
        main_app.cmd_process = None
        main_app.cmd_process_id = None
        main_app.geometry("1000x700")

def clear_cmd_window(main_app):
    close_cmd_window(main_app)
    time.sleep(0.1)
    open_cmd_window(main_app)

def send_cmd_to_window(main_app):
    if main_app.cmd_process and main_app.cmd_process.poll() is None:
        cmd_input = main_app.cmd_input_entry.get().strip()
        if cmd_input:
            try:
                main_app.cmd_process.stdin.write(f'{cmd_input}\n')
                main_app.cmd_process.stdin.flush()
                main_app.cmd_input_entry.delete(0, tk.END)
            except AttributeError as e:
                messagebox.showerror("Error", f"Error: {e}. CMD process might not be running or stdin is not accessible.")
    else:
        messagebox.showerror("Error", "CMD process is not running. Open a CMD window first.")

def check_cmd_process(main_app):
    if main_app.cmd_process and main_app.cmd_process.poll() is not None:
        main_app.cmd_process = None
        main_app.cmd_process_id = None
        main_app.geometry(main_app.original_geometry)

    main_app.after(1000, check_cmd_process, main_app)

def close_create_tool_frame(main_app):
    main_app.create_tool_frame.place_forget()
    main_app.build_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.8, relheight=0.8)
    gui_manager.unregister_window("create_tool")
    set_active_window("build_frame")

def clear_placeholder(event, placeholder):
    if event.widget.get() == placeholder:
        event.widget.delete(0, tk.END)
        event.widget.config(fg="black")

def clear_text_placeholder(event, placeholder):
    if event.widget.get("1.0", tk.END).strip() == placeholder:
        event.widget.delete("1.0", tk.END)
        event.widget.config(fg="black")

def restore_entry_placeholder(event, placeholder):
    if not event.widget.get():
        event.widget.insert(0, placeholder)
        event.widget.config(fg="grey")

def restore_text_placeholder(event, placeholder):
    if not event.widget.get("1.0", tk.END).strip():
        event.widget.insert("1.0", placeholder)
        event.widget.config(fg="grey")

def clear_python_output(main_app):
    main_app.code_editor.delete("1.0", tk.END)

def handle_python_indentation(event, code_editor):
    if event.keysym == "Return":
        current_line = code_editor.index("insert").split(".")[0]
        line_text = code_editor.get(f"{current_line}.0", f"{current_line}.end")

        current_indentation = len(line_text) - len(line_text.lstrip())

        if line_text.strip().endswith(":"):
            new_indentation = current_indentation + 4 
        else:
            dedent_keywords = ['return', 'break', 'continue', 'pass', 'raise']
            if any(line_text.strip().startswith(kw) for kw in dedent_keywords):
                new_indentation = max(0, current_indentation - 4)
            else:
                prev_line = code_editor.get(f"{current_line}.0 - 1 line", f"{current_line}.end")
                prev_indentation = len(prev_line) - len(prev_line.lstrip())

                if prev_line.strip().endswith(":"):
                    new_indentation = prev_indentation + 4
                else:
                    new_indentation = current_indentation
        
        code_editor.insert("insert", "\n" + " " * new_indentation)
        
        return "break"
    
def execute_python_code(main_app):
    python_code = main_app.code_editor.get("1.0", tk.END).strip()
    if python_code:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.py') as temp_file:
            temp_file.write(python_code.encode('utf-8'))
            temp_file_path = temp_file.name

        if main_app.cmd_process and main_app.cmd_process.poll() is None:
            print("Executing code in existing CMD window.")
            threading.Thread(target=run_python_code, args=(main_app, temp_file_path, main_app.cmd_process)).start()
        else:
            print("No existing CMD window. Opening new CMD window.")
            threading.Thread(target=open_and_execute_in_new_cmd, args=(main_app, temp_file_path)).start()

def run_python_code(main_app, temp_file_path, cmd_process):
    if cmd_process:
        try:
            print(f"Executing code from file: {temp_file_path}")
            cmd_process.stdin.write(f'python {temp_file_path}\n')
            cmd_process.stdin.flush()
            cmd_process.wait()
        except AttributeError as e:
            print(f"Error: {e}. CMD process might not be running or stdin is not accessible.")
    else:
        print("CMD process is not initialized.")
        print("Executing code in new process.")
        result = subprocess.run(['python', temp_file_path], capture_output=True, text=True)
        print(result.stdout, result.stderr)

    os.remove(temp_file_path)
    print(f"Deleted temporary file: {temp_file_path}")

def open_cmd_window(main_app):
    if main_app.cmd_process and main_app.cmd_process.poll() is None:
        print(f"CMD window already open with PID: {main_app.cmd_process_id}")
        return

    main_app.geometry("1000x900")

    main_app.cmd_process = subprocess.Popen(
        ['cmd', '/K'], creationflags=subprocess.CREATE_NEW_CONSOLE, stdin=subprocess.PIPE, text=True
    )
    main_app.cmd_process_id = main_app.cmd_process.pid
    print(f"Opened CMD window with PID: {main_app.cmd_process_id}")

    threading.Thread(target=embed_cmd, args=(main_app.cmd_frame, main_app.cmd_process)).start()

def close_cmd_window(main_app):
    if main_app.cmd_process:
        main_app.cmd_process.terminate()
        main_app.cmd_process = None
        main_app.cmd_process_id = None
        main_app.geometry(main_app.original_geometry)

def open_and_execute_in_new_cmd(main_app, temp_file_path):
    open_cmd_window(main_app)
    run_python_code(main_app, temp_file_path, main_app.cmd_process)

def save_tool(main_app):
    tool_name = main_app.tool_name_entry.get().strip()
    tool_description = main_app.tool_description_entry.get("1.0", tk.END).strip()
    tool_code = main_app.code_editor.get("1.0", tk.END).strip()

    if not tool_name or tool_name == "Tool Name":
        messagebox.showerror("Error", "Tool name is required.")
        return

    if not tool_description or tool_description == "Tool Description":
        messagebox.showerror("Error", "Tool description is required.")
        return

    if not tool_code:
        messagebox.showerror("Error", "Tool code is required.")
        return

    tool_data = {
        "Tool Name": tool_name,
        "Tool Description": tool_description,
        "Tool Code": tool_code
    }

    tools_file = r'agent_gen\saved_tools\tools.json'
    if not os.path.exists(os.path.dirname(tools_file)):
        os.makedirs(os.path.dirname(tools_file))

    if os.path.exists(tools_file):
        with open(tools_file, 'r', encoding='utf-8') as file:
            existing_tools = json.load(file)
    else:
        existing_tools = []

    for tool in existing_tools:
        if tool["Tool Name"] == tool_data["Tool Name"]:
            messagebox.showerror("Error", "Tool with the same name exists.")
            return

    existing_tools.append(tool_data)

    with open(tools_file, 'w', encoding='utf-8') as file:
        json.dump(existing_tools, file, ensure_ascii=False, indent=4)

    messagebox.showinfo("Success", "Tool saved successfully.")