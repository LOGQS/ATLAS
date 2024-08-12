# ag_create_agent.py
import os
import json
import tkinter as tk
from tkinter import ttk, messagebox, Toplevel
import re
import threading
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from gui_element_manager import register_window, register_element, set_active_window, gui_manager

chat_history = []

def show_create_agent_frame(main_app):
    main_app.build_frame.place_forget()

    create_agent_frame = tk.Frame(main_app.main_frame, bg="#2c2c2c", bd=2, relief="ridge", padx=10, pady=10)
    create_agent_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0, relheight=1.0)

    register_window("create_agent", create_agent_frame)
    create_agent_frame.bind("<FocusIn>", lambda e: set_active_window("create_agent"))
    
    set_active_window("create_agent")

    main_app.create_agent_frame = create_agent_frame

    # Close button
    close_button = tk.Button(
        create_agent_frame,
        text="X",
        font=("Helvetica", 14, "bold"),
        bg="#ff5555",
        fg="white",
        command=lambda: close_create_agent_frame(main_app)
    )
    close_button.place(x=902, y=5, width=25, height=25)
    register_element("create_agent", "close_button", close_button, "button")

    # Reset chat button
    reset_chat_button = tk.Button(
        create_agent_frame,
        text="Reset Chat",
        font=("Helvetica", 14, "bold"),
        bg="#4a4a4a",
        fg="white",
        command=lambda: reset_chat(main_app)
    )
    reset_chat_button.place(x=335, y=5, width=200, height=25)
    register_element("create_agent", "reset_chat_button", reset_chat_button, "button")

    # Agent Tag entry
    agent_tag_entry = tk.Entry(create_agent_frame, font=("Helvetica", 16), fg="grey")
    agent_tag_entry.insert(0, "Agent Tag")
    agent_tag_entry.bind("<FocusIn>", lambda event: clear_placeholder(event, "Agent Tag"))
    agent_tag_entry.bind("<FocusOut>", lambda event: restore_text_placeholder(event, "Agent Tag"))
    agent_tag_entry.place(x=20, y=20, width=250, height=40)
    main_app.agent_tag_entry = agent_tag_entry
    register_element("create_agent", "agent_tag_entry", agent_tag_entry, "entry")

    # Agent Prompt entry
    agent_prompt_entry = tk.Text(create_agent_frame, font=("Helvetica", 16), fg="grey", wrap="word")
    agent_prompt_entry.insert(tk.END, "Agent Prompt")
    agent_prompt_entry.bind("<FocusIn>", lambda event: clear_text_placeholder(event, "Agent Prompt"))
    agent_prompt_entry.bind("<FocusOut>", lambda event: restore_text_placeholder(event, "Agent Prompt"))
    agent_prompt_entry.place(x=20, y=80, width=300, height=200)
    main_app.agent_prompt_entry = agent_prompt_entry
    register_element("create_agent", "agent_prompt_entry", agent_prompt_entry, "text")

    # Tool selection
    selected_tool = tk.StringVar(create_agent_frame)
    selected_tool.set("Select a tool")
    main_app.selected_tool = selected_tool
    register_element("create_agent", "selected_tool", selected_tool, "stringvar")

    tool_dropdown = ttk.Combobox(create_agent_frame, textvariable=selected_tool, font=("Helvetica", 14), state="readonly")
    tools_file = r'agent_gen\saved_tools\tools.json'
    try:
        with open(tools_file, 'r', encoding='utf-8') as file:
            tools = json.load(file)
        tool_names = [tool["Tool Name"] for tool in tools]
    except (FileNotFoundError, json.JSONDecodeError):
        tools = []
        tool_names = []
    tool_dropdown['values'] = tool_names
    tool_dropdown.place(x=20, y=300, width=200, height=30)
    register_element("create_agent", "tool_dropdown", tool_dropdown, "combobox")

    # Add tool button
    add_tool_button = tk.Button(
        create_agent_frame,
        text="Add",
        font=("Helvetica", 14),
        bg="#4a4a4a",
        fg="white",
        command=lambda: add_tool_to_canvas(main_app)
    )
    add_tool_button.place(x=230, y=300, width=80, height=30)
    register_element("create_agent", "add_tool_button", add_tool_button, "button")

    # Canvas tool list
    canvas_tool_list = tk.Listbox(create_agent_frame, font=("Helvetica", 14), height=5)
    canvas_tool_list.place(x=20, y=350, width=300, height=150)
    canvas_tool_list.bind('<Double-1>', lambda event: remove_tool_from_canvas(main_app))
    main_app.canvas_tool_list = canvas_tool_list
    register_element("create_agent", "canvas_tool_list", canvas_tool_list, "listbox")

    # Chatbox area
    chat_frame = tk.Frame(create_agent_frame, bg="#2c2c2c")
    chat_frame.place(x=325, y=30, width=600, height=540)

    chatbox = tk.Text(chat_frame, height=10, font=("Helvetica", 14), wrap="word", bg="#1f1f3b", fg="white")
    chatbox.pack(padx=10, pady=10, fill="both", expand=True)
    chatbox.tag_configure("user", foreground="#d10404")
    chatbox.tag_configure("agent", foreground="#02ad0a")
    main_app.chatbox = chatbox
    register_element("create_agent", "chatbox", chatbox, "text")

    scrollbar = tk.Scrollbar(chat_frame, command=chatbox.yview)
    scrollbar.pack(side="right", fill="y")
    scrollbar.place(relx=1, rely=0.02, relheight=0.96, anchor="ne")
    chatbox.config(yscrollcommand=scrollbar.set)

    # User Input Box
    user_input_frame = tk.Frame(create_agent_frame, bg="#2c2c2c")
    user_input_frame.place(x=325, y=580, width=600, height=50)

    user_input_box = tk.Entry(user_input_frame, font=("Helvetica", 16), fg="black", bg="white")
    user_input_box.pack(side="left", fill="x", expand=True, padx=10)
    user_input_box.bind("<Return>", lambda event: send_message(main_app))
    main_app.user_input_box = user_input_box
    register_element("create_agent", "user_input_box", user_input_box, "entry")

    send_button = tk.Button(user_input_frame, text="Send", font=("Helvetica", 14), command=lambda: send_message(main_app))
    send_button.pack(side="right", padx=10)
    register_element("create_agent", "send_button", send_button, "button")

    # Save Agent button
    save_agent_button = tk.Button(
        create_agent_frame,
        text="Save Agent",
        font=("Helvetica", 14),
        bg="#4a4a4a",
        fg="white",
        command=lambda: save_agent(main_app)
    )
    save_agent_button.place(x=20, y=585, width=120, height=40)
    register_element("create_agent", "save_agent_button", save_agent_button, "button")

    # Advanced button
    advanced_button = tk.Button(
        create_agent_frame,
        text="Advanced",
        font=("Helvetica", 14),
        bg="#4a4a4a",
        fg="white",
        command=lambda: open_advanced_settings(main_app)
    )
    advanced_button.place(x=200, y=585, width=120, height=40)
    register_element("create_agent", "advanced_button", advanced_button, "button")

    # Model dropdown menu
    selected_model = tk.StringVar(create_agent_frame)
    selected_model.set("Select a model")
    main_app.selected_model = selected_model

    model_dropdown = ttk.Combobox(create_agent_frame, textvariable=selected_model, font=("Helvetica", 14), state="readonly")
    model_dropdown['values'] = ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.0-pro"]
    model_dropdown.place(x=20, y=525, width=200, height=30)
    register_element("create_agent", "model_dropdown", model_dropdown, "combobox")

def close_create_agent_frame(main_app):
    main_app.create_agent_frame.place_forget()
    main_app.build_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.8, relheight=0.8)
    gui_manager.unregister_window("create_agent")
    set_active_window("build_frame")

def add_tool_to_canvas(main_app):
    selected_tool = main_app.selected_tool.get()
    if selected_tool not in main_app.canvas_tool_list.get(0, tk.END) and selected_tool != "Select a tool":
        main_app.canvas_tool_list.insert(tk.END, selected_tool)

def remove_tool_from_canvas(main_app):
    selected_tool = main_app.canvas_tool_list.curselection()
    if selected_tool:
        main_app.canvas_tool_list.delete(selected_tool)

def clear_placeholder(event, placeholder):
    if event.widget.get() == placeholder:
        event.widget.delete(0, tk.END)
        event.widget.config(fg="black")

def clear_text_placeholder(event, placeholder):
    if event.widget.get("1.0", tk.END).strip() == placeholder:
        event.widget.delete("1.0", tk.END)
        event.widget.config(fg="black")

def restore_text_placeholder(event, placeholder):
    widget = event.widget
    if isinstance(widget, tk.Entry):
        if widget.get().strip() == "":
            widget.insert(0, placeholder)
            widget.config(fg="grey")
    elif isinstance(widget, tk.Text):
        if widget.get("1.0", tk.END).strip() == "":
            widget.insert(tk.END, placeholder)
            widget.config(fg="grey")

def send_message(main_app):
    user_message = main_app.user_input_box.get()
    agent_prompt = main_app.agent_prompt_entry.get("1.0", tk.END).strip()
    model_name = main_app.selected_model.get().strip()

    if not user_message.strip():
        return

    main_app.chatbox.insert(tk.END, f"You: {user_message}\n", "user")
    main_app.user_input_box.delete(0, tk.END)

    threading.Thread(target=send_message_to_model, args=(main_app, user_message, agent_prompt, model_name)).start()


def send_message_to_model(main_app, user_message, agent_prompt, model_name):
    def chatbot_thread():
        try:
            response = call_gemini_model(main_app, user_message, agent_prompt, model_name)
            main_app.chatbox.insert(tk.END, f"Agent: {response}\n", "agent")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")

    threading.Thread(target=chatbot_thread).start()

def save_agent(main_app):
    agent_tag = main_app.agent_tag_entry.get().strip()
    agent_prompt = main_app.agent_prompt_entry.get("1.0", tk.END).strip()
    tools = list(main_app.canvas_tool_list.get(0, tk.END))
    model = main_app.selected_model.get().strip()

    if not agent_tag or agent_tag == "Agent Tag":
        messagebox.showerror("Error", "Agent tag is required.")
        return

    if not agent_prompt or agent_prompt == "Agent Prompt":
        messagebox.showerror("Error", "Agent prompt is required.")
        return

    if model == "Select a model":
        messagebox.showerror("Error", "You must select a model.")
        return

    if not tools:
        tools = ["None"]

    advanced_settings = get_advanced_settings(main_app)

    agent_data = {
        "Agent Name": agent_tag,
        "Model": model,
        "Agent Prompt": agent_prompt,
        "Tools": tools,
        "Advanced Settings": advanced_settings
    }

    agents_file = r'agent_gen\saved_agents\agents.json'
    if not os.path.exists(os.path.dirname(agents_file)):
        os.makedirs(os.path.dirname(agents_file))

    if os.path.exists(agents_file):
        with open(agents_file, 'r', encoding='utf-8') as file:
            existing_agents = json.load(file)
    else:
        existing_agents = []

    for agent in existing_agents:
        if agent["Agent Name"] == agent_data["Agent Name"]:
            messagebox.showerror("Error", "Agent with the same name exists.")
            return
        if agent["Agent Prompt"] == agent_data["Agent Prompt"]:
            messagebox.showerror("Error", "Agent with the same prompt exists.")
            return

    existing_agents.append(agent_data)

    with open(agents_file, 'w', encoding='utf-8') as file:
        json.dump(existing_agents, file, ensure_ascii=False, indent=4)

    messagebox.showinfo("Success", "Agent saved successfully.")


def get_advanced_settings(main_app):
    default_settings = {
        "Top p": 1.0,
        "Top k": 50,
        "Temperature": 1.0,
        "Max output length": 8000
    }

    advanced_settings_file = r'agent_gen\saved_agents\advanced_settings.json'
    file_advanced_settings = {}

    if os.path.exists(advanced_settings_file):
        with open(advanced_settings_file, 'r', encoding='utf-8') as file:
            file_advanced_settings = json.load(file)

    advanced_settings = {**default_settings, **file_advanced_settings}

    for key in default_settings.keys():
        value = main_app.advanced_vars.get(key, None) if hasattr(main_app, 'advanced_vars') else None
        if value:
            advanced_settings[key] = float(value.get())

    return advanced_settings


def open_advanced_settings(main_app):
    if main_app.advanced_window_open:
        messagebox.showerror("Error", "An advanced settings window is already open.")
        return
    main_app.advanced_window_open = True
    advanced_window = Toplevel(main_app)
    advanced_window.title("Advanced Settings")
    advanced_window.geometry("300x300")
    advanced_window.configure(bg="#2c2c2c")

    register_window("advanced_settings", advanced_window)
    
    set_active_window("advanced_settings")

    def on_advanced_window_close():
        main_app.advanced_window_open = False
        main_app.advanced_vars.clear()
        gui_manager.unregister_window("advanced_settings")
        advanced_window.destroy()
        set_active_window("create_agent")

    advanced_window.protocol("WM_DELETE_WINDOW", on_advanced_window_close)

    advanced_label = tk.Label(advanced_window, text="Advanced Settings", font=("Helvetica", 16), bg="#2c2c2c", fg="white")
    advanced_label.pack(pady=10)

    options = [
        ("Top p", 1.0),
        ("Top k", 50),
        ("Temperature", 1.0),
        ("Max output length", 8000)
    ]

    main_app.advanced_vars = {}

    for idx, (label, default_value) in enumerate(options):
        frame = tk.Frame(advanced_window, bg="#2c2c2c")
        frame.pack(pady=5)

        lbl = tk.Label(frame, text=label, font=("Helvetica", 14), bg="#2c2c2c", fg="white")
        lbl.pack(side="left", padx=10)

        if isinstance(default_value, float):
            spinbox = ttk.Spinbox(frame, from_=0.0, to=1.0, increment=0.1, format="%.1f", width=10)
        else:
            spinbox = ttk.Spinbox(frame, from_=0, to=10000, increment=1, width=10)

        spinbox.set(main_app.advanced_settings.get(label, default_value))
        spinbox.pack(side="left")
        main_app.advanced_vars[label] = spinbox

        register_element("advanced_settings", f"{label.lower().replace(' ', '_')}_spinbox", spinbox, "spinbox")

    save_button = tk.Button(
        advanced_window,
        text="Save",
        font=("Helvetica", 14),
        bg="#4a4a4a",
        fg="white",
        command=lambda: save_advanced_settings(main_app)
    )
    save_button.pack(pady=20)
    register_element("advanced_settings", "save_button", save_button, "button")

    advanced_window.bind("<FocusIn>", lambda e: set_active_window("advanced_settings"))

    advanced_window.transient(main_app)
    advanced_window.grab_set()

def save_advanced_settings(main_app):
    for key, spinbox in main_app.advanced_vars.items():
        main_app.advanced_settings[key] = float(spinbox.get())
    save_advanced_settings_to_file(main_app)
    messagebox.showinfo("Success", "Advanced settings saved.")

def save_advanced_settings_to_file(main_app):
    settings_file = r'agent_gen\saved_agents\advanced_settings.json'
    os.makedirs(os.path.dirname(settings_file), exist_ok=True)
    with open(settings_file, 'w', encoding='utf-8') as file:
        json.dump(main_app.advanced_settings, file, ensure_ascii=False, indent=4)

def extract_variables(prompt):
    variables = re.findall(r'\{(\w+)\}', prompt)
    return variables

def prompt_for_variables(main_app, variables):
    var_window = Toplevel(main_app)
    var_window.title("Enter Variables")
    var_window.geometry("300x400")
    var_window.configure(bg="#2c2c2c")

    main_app.var_entries = {}

    for idx, var in enumerate(variables):
        var_frame = tk.Frame(var_window, bg="#2c2c2c")
        var_frame.pack(pady=10, padx=10, fill='x')

        var_label = tk.Label(var_frame, text=var, font=("Helvetica", 14), bg="#2c2c2c", fg="white")
        var_label.pack(side='left', padx=10)

        var_entry = tk.Entry(var_frame, font=("Helvetica", 14))
        var_entry.pack(side='right', fill='x', expand=True)
        main_app.var_entries[var] = var_entry

    submit_button = tk.Button(
        var_window,
        text="Submit",
        font=("Helvetica", 14),
        bg="#4a4a4a",
        fg="white",
        command=lambda: submit_variables(main_app, var_window)
    )
    submit_button.pack(pady=20)

def submit_variables(main_app, var_window):
    variable_values = {var: entry.get() for var, entry in main_app.var_entries.items()}
    var_window.destroy()
    replace_variables_in_prompt(main_app, variable_values)

def replace_variables_in_prompt(main_app, variable_values):
    agent_prompt = main_app.agent_prompt_entry.get("1.0", tk.END).strip()
    for var, value in variable_values.items():
        agent_prompt = agent_prompt.replace(f'{{{var}}}', value)
    main_app.agent_prompt_entry.delete("1.0", tk.END)
    main_app.agent_prompt_entry.insert(tk.END, agent_prompt)

    user_message = main_app.user_input_box.get()
    model_name = main_app.selected_model.get().strip()
    send_message_to_model(main_app, user_message, agent_prompt, model_name)

def call_gemini_model(main_app, user_request, system_prompt, model_name):
    global chat_history
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
    genai.configure(api_key=json.loads(open(config_path).read())['api_keys']['GEMINI_API_KEY'])

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    generation_config = genai.types.GenerationConfig(
        temperature=main_app.advanced_settings["Temperature"],
        max_output_tokens=int(main_app.advanced_settings["Max output length"]),
        top_p=main_app.advanced_settings["Top p"],
        top_k=int(main_app.advanced_settings["Top k"]),
    )

    if model_name == "gemini-1.0-pro":
        model = genai.GenerativeModel(model_name=model_name)
        chat = model.start_chat(history=chat_history)
        prompt = f"System: {system_prompt}\nUser: {user_request}"
    else:
        model = genai.GenerativeModel(model_name=model_name, system_instruction=system_prompt)
        chat = model.start_chat(history=chat_history)
        prompt = f"User: {user_request}"

    chat_response = chat.send_message(content=prompt, generation_config=generation_config, safety_settings=safety_settings)
    chat_history = chat.history

    return chat_response.text

def reset_chat(main_app):
    global chat_history
    chat_history = []
    main_app.chatbox.delete("1.0", tk.END)