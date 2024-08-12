# ag_canvas.py
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk, scrolledtext, filedialog
import json
import os
import re
from PIL import Image, ImageTk
import random
import math
import threading
import subprocess
import sys
from ag_create_tool import handle_python_indentation
from ag_canvas_workflow import generate_and_execute_workflow
from gui_element_manager import register_window, register_element, set_active_window, gui_manager

connection_mode_enabled = False

def show_open_canvas_frame(main_app):
    main_app.canvas_frame.place_forget()
    original_width = main_app.winfo_width()
    original_height = main_app.winfo_height()
    new_width = int(original_width * 1.7)
    new_height = int(original_height * 1.2)
    main_app.geometry(f"{new_width}x{new_height}")

    open_canvas_frame = tk.Frame(main_app, bg="#1e1e1e")
    open_canvas_frame.place(x=0, y=0, relwidth=1, relheight=1)

    register_window("open_canvas", open_canvas_frame)
    open_canvas_frame.bind("<FocusIn>", lambda e: set_active_window("open_canvas"))
    set_active_window("open_canvas")

    canvas = tk.Canvas(open_canvas_frame, bg=main_app.canvas_settings["bg_color"])
    canvas.place(x=10, y=40, relwidth=0.98, relheight=0.93)
    main_app.canvas = canvas
    register_element("open_canvas", "canvas", canvas, "canvas")

    canvas.nodes = {}
    canvas.connections = {}

    agent_icon = load_png_icon(r"imgs\agent_icon.png", (main_app.canvas_settings["grid_size"], main_app.canvas_settings["grid_size"]))
    tool_icon = load_png_icon(r"imgs\tool_icon.png", (main_app.canvas_settings["grid_size"], main_app.canvas_settings["grid_size"]))
    main_app.agent_icon = agent_icon
    main_app.tool_icon = tool_icon

    if main_app.canvas_settings["show_grid"]:
        draw_grid(canvas, grid_size=main_app.canvas_settings["grid_size"])

    close_button = tk.Button(
        open_canvas_frame,
        text="X",
        font=("Helvetica", 14, "bold"),
        bg="#ff5555",
        fg="white",
        command=lambda: on_canvas_window_close(main_app, open_canvas_frame, original_width, original_height)
    )
    close_button.place(x=new_width-35, y=5, width=25, height=25)
    register_element("open_canvas", "close_button", close_button, "button") 

    add_agent_button = tk.Button(
        open_canvas_frame,
        text="Add Agent",
        font=("Helvetica", 12),
        bg="#4a4a4a",
        fg="white",
        command=lambda: add_agent(canvas)
    )
    add_agent_button.place(x=10, y=5, width=100, height=30)

    add_tool_button = tk.Button(
        open_canvas_frame,
        text="Add Tool",
        font=("Helvetica", 12),
        bg="#4a4a4a",
        fg="white",
        command=lambda: add_tool(canvas)
    )
    add_tool_button.place(x=120, y=5, width=100, height=30)

    activate_selection_button = tk.Button(
        open_canvas_frame,
        text="Activate Connect",
        font=("Helvetica", 12),
        bg="#4a4a4a",
        fg="white",
        command=activate_selection_mode
    )
    activate_selection_button.place(x=230, y=5, width=150, height=30)

    deactivate_selection_button = tk.Button(
        open_canvas_frame,
        text="Deactivate Connect",
        font=("Helvetica", 12),
        bg="#4a4a4a",
        fg="white",
        command=deactivate_selection_mode
    )
    deactivate_selection_button.place(x=390, y=5, width=160, height=30)

    clear_canvas_button = tk.Button(
        open_canvas_frame,
        text="Clear Canvas",
        font=("Helvetica", 12),
        bg="#4a4a4a",
        fg="white",
        command=lambda: clear_canvas(canvas)
    )
    clear_canvas_button.place(x=560, y=5, width=120, height=30)

    execute_workflow_button = tk.Button(
        open_canvas_frame,
        text="Execute Workflow",
        font=("Helvetica", 12),
        bg="#4a4a4a",
        fg="white",
        command=lambda: execute_workflow(main_app, canvas)
    )
    execute_workflow_button.place(x=690, y=5, width=140, height=30)

    save_workflow_button = tk.Button(
        open_canvas_frame,
        text="Save Workflow",
        font=("Helvetica", 12),
        bg="#4a4a4a",
        fg="white",
        command=lambda: save_workflow(main_app, canvas)
    )
    save_workflow_button.place(x=840, y=5, width=120, height=30)

    load_workflow_button = tk.Button(
    open_canvas_frame,
    text="Load Workflow",
    font=("Helvetica", 12),
    bg="#4a4a4a",
    fg="white",
    command=lambda: load_workflow(main_app, canvas)
    )
    load_workflow_button.place(x=970, y=5, width=120, height=30)

    for button_name in ["add_agent_button", "add_tool_button", "activate_selection_button", 
                        "deactivate_selection_button", "clear_canvas_button", 
                        "execute_workflow_button", "save_workflow_button", "load_workflow_button"]:
        button = locals()[button_name]
        register_element("open_canvas", button_name, button, "button")

    main_app.protocol("WM_DELETE_WINDOW", lambda: on_canvas_window_close(main_app, open_canvas_frame, original_width, original_height))

    main_app.open_canvas_frame = open_canvas_frame


    canvas.bind("<Configure>", lambda event, c=canvas: on_canvas_resize(event, c))
    canvas.bind("<Button-1>", lambda event: deselect_all_nodes(canvas, event))
    
    for widget in open_canvas_frame.winfo_children():
        if isinstance(widget, tk.Button):
            widget.bind("<Button-1>", lambda event: deselect_all_nodes(canvas, event))

    canvas.last_selected = None

    if main_app.canvas_settings["snap_to_grid"]:
        canvas.bind("<B1-Motion>", lambda event, c=canvas: snap_to_grid(event, c))

    sliding_window = tk.Frame(open_canvas_frame, bg="#2c2c2c", width=300)
    sliding_window.place(relx=1, rely=0, relheight=1, anchor="ne")
    sliding_window.place_forget()
    main_app.sliding_window = sliding_window

def activate_selection_mode():
    global connection_mode_enabled
    connection_mode_enabled = True

def deactivate_selection_mode():
    global connection_mode_enabled
    connection_mode_enabled = False

def load_png_icon(file_name, size):
    image = Image.open(file_name)
    image = image.resize(size, Image.LANCZOS)
    return ImageTk.PhotoImage(image)

def add_agent(canvas):
    agents = load_json_file(r'agent_gen\saved_agents\agents.json')
    if agents:
        agent_name = show_selection_dialog(canvas, "Select Agent", agents)
        if agent_name:
            add_node_to_canvas(canvas, agent_name, "agent")

def add_tool(canvas):
    tools = load_json_file(r'agent_gen\saved_tools\tools.json')
    if tools:
        tool_name = show_selection_dialog(canvas, "Select Tool", tools)
        if tool_name:
            add_node_to_canvas(canvas, tool_name, "tool")

def load_json_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            data = json.load(file)
        return [item.get('Agent Name', item.get('Tool Name', 'Unnamed')) for item in data]
    else:
        print(f"File not found: {file_path}")
        return []

def show_selection_dialog(canvas, title, items):
    dialog = tk.Toplevel(canvas)
    register_window("selection_dialog", dialog)
    dialog.title(title)
    dialog.geometry("300x400")
    dialog.configure(bg="#2c2c2c")
    dialog.transient(canvas.master)
    dialog.grab_set()

    listbox = tk.Listbox(dialog, font=("Helvetica", 12), bg="#1e1e1e", fg="white")
    listbox.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
    register_element("selection_dialog", "listbox", listbox, "listbox")

    for item in items:
        listbox.insert(tk.END, item)

    selected_item = tk.StringVar()

    def on_select():
        selection = listbox.curselection()
        if selection:
            selected_item.set(listbox.get(selection[0]))
            close_dialog()

    def close_dialog():
        gui_manager.unregister_window("selection_dialog")
        dialog.destroy()

    select_button = tk.Button(
        dialog,
        text="Select",
        font=("Helvetica", 12),
        bg="#4a4a4a",
        fg="white",
        command=on_select
    )
    select_button.pack(pady=10)
    register_element("selection_dialog", "select_button", select_button, "button")

    dialog.protocol("WM_DELETE_WINDOW", close_dialog)

    dialog.wait_window()
    return selected_item.get()

def is_light_color(hex_color):
    hex_color = hex_color.lstrip('#')
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    return luminance > 128

def add_node_to_canvas(canvas, name, node_type, position=None, node_id=None):
    grid_size = canvas.master.master.canvas_settings["grid_size"]
    if position:
        x, y = position
    else:
        x = (canvas.winfo_width() // grid_size // 2) * grid_size
        y = (canvas.winfo_height() // grid_size // 2) * grid_size
    
    if node_type == "agent":
        icon = canvas.master.master.agent_icon
    else:
        icon = canvas.master.master.tool_icon
    
    if node_id is None:
        node_id = f"{node_type}_{len(canvas.nodes) + 1}" 
    
    node = canvas.create_image(x, y, image=icon, tags=(node_type, "node"))
    
    bg_color = canvas.master.master.canvas_settings["bg_color"]
    text_color = "black" if is_light_color(bg_color) else "white"
    
    text = canvas.create_text(x, y + grid_size // 2 + 10, text=name, font=("Helvetica", 10), fill=text_color, tags=(node_type, "node"))

    canvas.nodes[node_id] = {"id": node_id, "canvas_id": node, "text_id": text, "connections": [], "type": node_type, "name": name}

    canvas.tag_bind(node, "<ButtonPress-1>", lambda event, n=node_id: on_node_press(event, canvas, n))
    canvas.tag_bind(node, "<B1-Motion>", lambda event, n=node_id: on_node_drag(event, canvas, n))
    canvas.tag_bind(node, "<ButtonRelease-1>", lambda event, n=node_id: on_node_release(event, canvas, n))
    canvas.tag_bind(node, "<Double-Button-1>", lambda event, n=node_id: on_node_double_click(event, canvas, n))
    canvas.tag_bind(node, "<ButtonPress-3>", lambda event, n=node_id: on_node_right_click(event, canvas, n))

    return node_id

def on_node_press(event, canvas, node_id):
    canvas.startx = event.x
    canvas.starty = event.y
    toggle_node_selection(canvas, node_id)
    return "break"

def on_node_drag(event, canvas, node_id):
    dx = event.x - canvas.startx
    dy = event.y - canvas.starty
    
    node = canvas.nodes[node_id]["canvas_id"]
    x, y = canvas.coords(node)

    new_x = x + dx
    new_y = y + dy

    icon_width = canvas.master.master.canvas_settings["grid_size"]
    icon_height = canvas.master.master.canvas_settings["grid_size"]

    canvas_left = icon_width / 2
    canvas_right = canvas.winfo_width() - icon_width / 2
    canvas_top = icon_height / 2
    canvas_bottom = canvas.winfo_height() - icon_height / 2

    new_x = max(canvas_left, min(new_x, canvas_right))
    new_y = max(canvas_top, min(new_y, canvas_bottom))

    dx = new_x - x
    dy = new_y - y

    canvas.move(node, dx, dy)
    canvas.move(canvas.nodes[node_id]["text_id"], dx, dy)

    if canvas.find_withtag(f"highlight_{node_id}"):
        canvas.move(f"highlight_{node_id}", dx, dy)
    
    update_node_connections(canvas, node_id)
    
    canvas.startx = event.x
    canvas.starty = event.y

def on_node_release(event, canvas, node_id):
    if canvas.master.master.canvas_settings["snap_to_grid"]:
        snap_node_to_grid(canvas, node_id)

def snap_node_to_grid(canvas, node_id):
    grid_size = canvas.master.master.canvas_settings["grid_size"]
    node = canvas.nodes[node_id]["canvas_id"]
    x, y = canvas.coords(node)
    new_x = round(x / grid_size) * grid_size
    new_y = round(y / grid_size) * grid_size
    
    dx = new_x - x
    dy = new_y - y
    
    canvas.move(node, dx, dy)
    canvas.move(canvas.nodes[node_id]["text_id"], dx, dy)
    
    if canvas.find_withtag(f"highlight_{node_id}"):
        canvas.move(f"highlight_{node_id}", dx, dy)
    
    update_node_connections(canvas, node_id)

def on_node_double_click(event, canvas, node_id):
    remove_node_and_connections(canvas, node_id)

def on_node_right_click(event, canvas, node_id):
    node_info = canvas.nodes[node_id]
    show_sliding_window(canvas.master.master, node_info["type"], node_info["name"])

def show_sliding_window(main_app, node_type, node_name):
    sliding_window = main_app.sliding_window
    sliding_window_width = 700
    sliding_window.configure(width=sliding_window_width)
    sliding_window.place(relx=1, rely=0, relheight=1, width=sliding_window_width, anchor="ne")
    
    register_window("sliding_window", sliding_window)
    sliding_window.bind("<FocusIn>", lambda e: set_active_window("sliding_window"))
    set_active_window("sliding_window")

    for widget in sliding_window.winfo_children():
        widget.destroy()

    close_button = tk.Button(
        sliding_window,
        text="X",
        font=("Helvetica", 12, "bold"),
        bg="#ff5555",
        fg="white",
        command=lambda: sliding_window.place_forget(),
        bd=0
    )
    close_button.place(x=sliding_window_width-30, y=5, width=25, height=25)
    register_element("sliding_window", "close_button", close_button, "button")

    title_label = tk.Label(sliding_window, text=f"{node_type.capitalize()} Information", font=("Helvetica", 16), bg="#2c2c2c", fg="white")
    title_label.pack(pady=(10, 20))
    register_element("sliding_window", "title_label", title_label, "label")

    content_frame = tk.Frame(sliding_window, bg="#2c2c2c")
    content_frame.pack(pady=10, padx=20, fill="both", expand=True)
    register_element("sliding_window", "content_frame", content_frame, "frame")

    if node_type == "agent":
        show_agent_info(main_app, content_frame, node_name)
    elif node_type == "tool":
        show_tool_info(main_app, content_frame, node_name)

    button_frame = tk.Frame(sliding_window, bg="#2c2c2c")
    button_frame.pack(pady=(0, 20))
    register_element("sliding_window", "button_frame", button_frame, "frame")

    save_button = tk.Button(
        button_frame,
        text="Save Changes",
        font=("Helvetica", 12),
        bg="#4a4a4a",
        fg="white",
        command=lambda: save_changes(main_app, node_type, node_name)
    )
    save_button.pack(side=tk.LEFT, padx=(0, 10))
    register_element("sliding_window", "save_button", save_button, "button")

    save_as_new_button = tk.Button(
        button_frame,
        text="Save as New",
        font=("Helvetica", 12),
        bg="#4a4a4a",
        fg="white",
        command=lambda: save_as_new(main_app, node_type, node_name)
    )
    save_as_new_button.pack(side=tk.LEFT)
    register_element("sliding_window", "save_as_new_button", save_as_new_button, "button")

def show_agent_info(main_app, parent_frame, agent_name):
    agent_data = load_agent_data(agent_name)
    
    tk.Label(parent_frame, text="Agent Name:", bg="#2c2c2c", fg="white", font=("Helvetica", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 10))
    name_entry = tk.Entry(parent_frame, font=("Helvetica", 12), width=40)
    name_entry.insert(0, agent_data["Agent Name"])
    name_entry.grid(row=0, column=1, pady=(0, 10), padx=(10, 0))

    tk.Label(parent_frame, text="Model:", bg="#2c2c2c", fg="white", font=("Helvetica", 12, "bold")).grid(row=1, column=0, sticky="w", pady=(0, 10))
    model_var = tk.StringVar(value=agent_data["Model"])
    model_dropdown = ttk.Combobox(parent_frame, textvariable=model_var, values=["gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.0-pro"], state="readonly", width=38)
    model_dropdown.grid(row=1, column=1, pady=(0, 10), padx=(10, 0))

    tk.Label(parent_frame, text="Agent Prompt:", bg="#2c2c2c", fg="white", font=("Helvetica", 12, "bold")).grid(row=2, column=0, sticky="nw", pady=(0, 10))
    prompt_text = tk.Text(parent_frame, font=("Helvetica", 12), height=10, width=40)
    prompt_text.insert("1.0", agent_data["Agent Prompt"])
    prompt_text.grid(row=2, column=1, pady=(0, 10), padx=(10, 0))

    prompt_scrollbar = tk.Scrollbar(parent_frame, orient="vertical", command=prompt_text.yview)
    prompt_scrollbar.grid(row=2, column=2, sticky="ns")
    prompt_text.config(yscrollcommand=prompt_scrollbar.set)

    tk.Label(parent_frame, text="Advanced Settings:", bg="#2c2c2c", fg="white", font=("Helvetica", 12, "bold")).grid(row=3, column=0, sticky="nw", pady=(0, 5))
    advanced_frame = tk.Frame(parent_frame, bg="#2c2c2c")
    advanced_frame.grid(row=3, column=1, sticky="w", pady=(0, 5), padx=(10, 0))

    for i, (key, value) in enumerate(agent_data["Advanced Settings"].items()):
        tk.Label(advanced_frame, text=key, bg="#2c2c2c", fg="white", font=("Helvetica", 10)).grid(row=i, column=0, sticky="w", pady=2)
        entry = tk.Entry(advanced_frame, font=("Helvetica", 10), width=15)
        entry.insert(0, str(value))
        entry.grid(row=i, column=1, pady=2, padx=(5, 0))

    for widget_name, widget in [("name_entry", name_entry), ("model_dropdown", model_dropdown), 
                                ("prompt_text", prompt_text), ("advanced_frame", advanced_frame)]:
        register_element("sliding_window", widget_name, widget, get_widget_type(widget))

    main_app.temp_agent_data = {
        "name_entry": name_entry,
        "model_var": model_var,
        "prompt_text": prompt_text,
        "advanced_entries": advanced_frame.winfo_children()[1::2]
    }
    
def show_tool_info(main_app, parent_frame, tool_name):
    tool_data = load_tool_data(tool_name)
    
    tk.Label(parent_frame, text="Tool Name:", bg="#2c2c2c", fg="white", font=("Helvetica", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 10))
    name_entry = tk.Entry(parent_frame, font=("Helvetica", 12), width=40) 
    name_entry.insert(0, tool_data["Tool Name"])
    name_entry.grid(row=0, column=1, pady=(0, 10), padx=(10, 0))

    tk.Label(parent_frame, text="Tool Description:", bg="#2c2c2c", fg="white", font=("Helvetica", 12, "bold")).grid(row=1, column=0, sticky="nw", pady=(0, 10))
    description_text = tk.Text(parent_frame, font=("Helvetica", 12), height=3, width=40) 
    description_text.insert("1.0", tool_data["Tool Description"])
    description_text.grid(row=1, column=1, pady=(0, 10), padx=(10, 0))

    tk.Label(parent_frame, text="Tool Code:", bg="#2c2c2c", fg="white", font=("Helvetica", 12, "bold")).grid(row=2, column=0, sticky="nw", pady=(0, 10))
    code_text = tk.Text(parent_frame, font=("Courier", 12), height=15, width=40)  
    code_text.insert("1.0", tool_data["Tool Code"])
    code_text.grid(row=2, column=1, pady=(0, 10), padx=(10, 0))

    code_scrollbar = tk.Scrollbar(parent_frame, orient="vertical", command=code_text.yview)
    code_scrollbar.grid(row=2, column=2, sticky="ns")
    code_text.config(yscrollcommand=code_scrollbar.set)

    code_text.bind("<Return>", lambda event: handle_python_indentation(event, code_text))

    for widget_name, widget in [("name_entry", name_entry), ("description_text", description_text), 
                                ("code_text", code_text)]:
        register_element("sliding_window", widget_name, widget, get_widget_type(widget))

    main_app.temp_tool_data = {
        "name_entry": name_entry,
        "description_text": description_text,
        "code_text": code_text
    }

def get_widget_type(widget):
    if isinstance(widget, tk.Entry):
        return "entry"
    elif isinstance(widget, tk.Text):
        return "text"
    elif isinstance(widget, ttk.Combobox):
        return "combobox"
    elif isinstance(widget, tk.Frame):
        return "frame"
    else:
        return "widget"

def save_as_new(main_app, node_type, node_name):
    if node_type == "agent":
        new_data = save_agent_changes(main_app, node_name)
        new_name = new_data["Agent Name"]
        if not is_name_unique(new_name, "agent"):
            messagebox.showerror("Error", f"An agent with the name '{new_name}' already exists!")
            return
        update_agent_data(new_name, new_data, is_new=True)
    elif node_type == "tool":
        new_data = save_tool_changes(main_app, node_name)
        new_name = new_data["Tool Name"]
        if not is_name_unique(new_name, "tool"):
            messagebox.showerror("Error", f"A tool with the name '{new_name}' already exists!")
            return
        update_tool_data(new_name, new_data, is_new=True)
    
    add_node_to_canvas(main_app.canvas, new_name, node_type)
    
    messagebox.showinfo("Success", f"New {node_type} '{new_name}' created successfully!")

def is_name_unique(name, node_type):
    if node_type == "agent":
        agents_file = r'agent_gen\saved_agents\agents.json'
        with open(agents_file, 'r') as f:
            agents = json.load(f)
        return not any(agent["Agent Name"] == name for agent in agents)
    elif node_type == "tool":
        tools_file = r'agent_gen\saved_tools\tools.json'
        with open(tools_file, 'r') as f:
            tools = json.load(f)
        return not any(tool["Tool Name"] == name for tool in tools)
    
def save_changes(main_app, node_type, node_name):
    if node_type == "agent":
        new_data = save_agent_changes(main_app, node_name)
        update_agent_data(node_name, new_data)
    elif node_type == "tool":
        new_data = save_tool_changes(main_app, node_name)
        update_tool_data(node_name, new_data)
    
    update_canvas_element(main_app.canvas, node_type, node_name, new_data)
    
    messagebox.showinfo("Success", f"{node_type.capitalize()} '{node_name}' updated successfully!")

def save_agent_changes(main_app, agent_name, new_name=None):
    temp_data = main_app.temp_agent_data

    new_agent_data = {
        "Agent Name": new_name or temp_data["name_entry"].get(),
        "Model": temp_data["model_var"].get(),
        "Agent Prompt": temp_data["prompt_text"].get("1.0", tk.END).strip(),
        "Advanced Settings": {}
    }

    advanced_settings = {
        "Top p": float(temp_data["advanced_entries"][0].get().strip() or 0),
        "Top k": int(temp_data["advanced_entries"][1].get().strip() or 0),
        "Temperature": float(temp_data["advanced_entries"][2].get().strip() or 0),
        "Max output length": int(temp_data["advanced_entries"][3].get().strip() or 0)
    }

    new_agent_data["Advanced Settings"] = advanced_settings

    return new_agent_data

def save_tool_changes(main_app, tool_name, new_name=None):
    temp_data = main_app.temp_tool_data
    new_tool_data = {
        "Tool Name": new_name or temp_data["name_entry"].get(),
        "Tool Description": temp_data["description_text"].get("1.0", tk.END).strip(),
        "Tool Code": temp_data["code_text"].get("1.0", tk.END).strip()
    }
    return new_tool_data

def update_canvas_element(canvas, node_type, old_name, new_data):
    for node_id, node_info in canvas.nodes.items():
        if node_info["type"] == node_type and node_info["name"] == old_name:
            # Update the node name in the canvas
            new_name = new_data[f"{node_type.capitalize()} Name"]
            canvas.itemconfig(node_info["text_id"], text=new_name)
            
            # Update the node information in the canvas.nodes dictionary
            canvas.nodes[node_id]["name"] = new_name
            
            # Force a redraw of the canvas
            canvas.update_idletasks()
            break

def load_agent_data(agent_name):
    agents_file = r'agent_gen\saved_agents\agents.json'
    with open(agents_file, 'r') as f:
        agents = json.load(f)
    return next((agent for agent in agents if agent["Agent Name"] == agent_name), None)

def load_tool_data(tool_name):
    tools_file = r'agent_gen\saved_tools\tools.json'
    with open(tools_file, 'r') as f:
        tools = json.load(f)
    return next((tool for tool in tools if tool["Tool Name"] == tool_name), None)

def update_agent_data(agent_name, new_data, is_new=False):
    agents_file = r'agent_gen\saved_agents\agents.json'
    with open(agents_file, 'r') as f:
        agents = json.load(f)
    
    if is_new:
        agents.append(new_data)
    else:
        for i, agent in enumerate(agents):
            if agent["Agent Name"] == agent_name:
                agents[i] = new_data
                break
    
    with open(agents_file, 'w') as f:
        json.dump(agents, f, indent=4)

def update_tool_data(tool_name, new_data, is_new=False):
    tools_file = r'agent_gen\saved_tools\tools.json'
    with open(tools_file, 'r') as f:
        tools = json.load(f)
    
    if is_new:
        tools.append(new_data)
    else:
        for i, tool in enumerate(tools):
            if tool["Tool Name"] == tool_name:
                tools[i] = new_data
                break
    
    with open(tools_file, 'w') as f:
        json.dump(tools, f, indent=4)

def clear_canvas(canvas):
    for item in canvas.find_all():
        if "grid" not in canvas.gettags(item):
            canvas.delete(item)
    canvas.nodes.clear()
    canvas.connections.clear()
    canvas.last_selected = None

def remove_node_and_connections(canvas, node_id):
    node = canvas.nodes[node_id]["canvas_id"]
    for connection in canvas.nodes[node_id]["connections"]:
        other_node_id = canvas.connections[connection]["nodes"][0] if canvas.connections[connection]["nodes"][1] == node_id else canvas.connections[connection]["nodes"][1]
        canvas.nodes[other_node_id]["connections"].remove(connection)
        canvas.delete(connection)
        del canvas.connections[connection]
    
    canvas.delete(node)
    canvas.delete(canvas.nodes[node_id]["text_id"])
    canvas.delete(f"highlight_{node_id}")
    
    del canvas.nodes[node_id]
    
    if canvas.last_selected == node_id:
        canvas.last_selected = None

def toggle_node_selection(canvas, node_id):
    if canvas.last_selected == node_id:
        deselect_node(canvas, node_id)
        canvas.last_selected = None
    elif canvas.last_selected is None:
        deselect_all_nodes(canvas, None)
        select_node(canvas, node_id)
        canvas.last_selected = node_id
    else:
        if connection_mode_enabled:
            connect_nodes(canvas, canvas.last_selected, node_id)
        deselect_node(canvas, canvas.last_selected)
        canvas.last_selected = None

def select_node(canvas, node_id):
    node = canvas.nodes[node_id]["canvas_id"]
    x1, y1, x2, y2 = canvas.bbox(node)
    highlight = canvas.create_rectangle(x1-2, y1-2, x2+2, y2+2, outline="lime", width=2, tags=(f"highlight_{node_id}", "highlight"))
    canvas.tag_lower(highlight, node)

def deselect_node(canvas, node_id):
    canvas.delete(f"highlight_{node_id}")

def deselect_all_nodes(canvas, event=None):
    if event is None or not canvas.find_overlapping(event.x - 1, event.y - 1, event.x + 1, event.y + 1):
        for item in canvas.find_withtag("highlight"):
            canvas.delete(item)
        canvas.last_selected = None  

def get_unique_color(canvas):
    while True:
        color = f"#{random.randint(0, 0xFFFFFF):06x}"
        if not any(conn["color"] == color for conn in canvas.connections.values()):
            return color

def connect_nodes(canvas, node1_id, node2_id, var1=None, var2=None):
    print(f"Debug: Attempting to connect node {node1_id} to node {node2_id}")
    node1 = canvas.nodes[node1_id]
    node2 = canvas.nodes[node2_id]

    print(f"Debug: Node 1 type: {node1['type']}, Node 2 type: {node2['type']}")

    # Case 1: Connecting tool to agent
    if node1['type'] == "tool" and node2['type'] == "agent":
        print("Debug: Case 1 - Connecting tool to agent")
        tool_output_vars = extract_tool_output_variables(node1['name'])
        agent_prompt_vars = extract_agent_prompt_variables(node2['name'])
        
        print(f"Debug: Tool output variables: {tool_output_vars}")
        print(f"Debug: Agent prompt variables: {agent_prompt_vars}")

        if var1 and var2:
            print(f"Debug: Using predefined variables: {var1}, {var2}")
            finalize_connection(canvas, node1_id, node2_id, var1, var2)
        else:
            matching_vars = set(tool_output_vars) & set(agent_prompt_vars)
            if matching_vars:
                var_to_connect = list(matching_vars)[0] if len(matching_vars) == 1 else prompt_user_for_variable("Select the variable to connect:", list(matching_vars))
                if var_to_connect:
                    print(f"Debug: Connecting with variable: {var_to_connect}")
                    finalize_connection(canvas, node1_id, node2_id, var_to_connect, var_to_connect)
                else:
                    print("Debug: Connection aborted by user")
            else:
                print("Debug: No matching variables found")
                show_error("No matching variables found between tool output and agent prompt")

    # Case 2: Connecting agent to tool
    elif node1['type'] == "agent" and node2['type'] == "tool":
        print("Debug: Case 2 - Connecting agent to tool")
        tool_input_vars = extract_tool_input_variables(node2['name'])
        
        print(f"Debug: Tool input variables: {tool_input_vars}")
        
        if var1 and var2:
            print(f"Debug: Using predefined variables: {var1}, {var2}")
            finalize_connection(canvas, node1_id, node2_id, var1, var2)
        elif tool_input_vars:
            var_to_connect = prompt_user_for_variable("Select the tool input variable:", tool_input_vars)
            if var_to_connect:
                print(f"Debug: Connecting with variable: {var_to_connect}")
                finalize_connection(canvas, node1_id, node2_id, "agent_output", var_to_connect)
            else:
                print("Debug: Connection aborted by user")
        else:
            print("Debug: No input variables found in tool")
            show_error("No input variables found in the selected tool")

    # Case 3: Connecting tool to tool
    elif node1['type'] == "tool" and node2['type'] == "tool":
        print("Debug: Case 3 - Connecting tool to tool")
        tool1_output_vars = extract_tool_output_variables(node1['name'])
        tool2_input_vars = extract_tool_input_variables(node2['name'])
        
        print(f"Debug: Tool 1 output variables: {tool1_output_vars}")
        print(f"Debug: Tool 2 input variables: {tool2_input_vars}")

        if var1 and var2:
            print(f"Debug: Using predefined variables: {var1}, {var2}")
            finalize_connection(canvas, node1_id, node2_id, var1, var2)
        else:
            matching_vars = set(tool1_output_vars) & set(tool2_input_vars)
            if matching_vars:
                var_to_connect = list(matching_vars)[0] if len(matching_vars) == 1 else prompt_user_for_variable("Select the variable to connect:", list(matching_vars))
                if var_to_connect:
                    print(f"Debug: Connecting with variable: {var_to_connect}")
                    finalize_connection(canvas, node1_id, node2_id, var_to_connect, var_to_connect)
                else:
                    print("Debug: Connection aborted by user")
            else:
                print("Debug: No matching variables found")
                show_error("No matching variables found between tool output and tool input")

    # Case 4: Connecting agent to agent
    elif node1['type'] == "agent" and node2['type'] == "agent":
        print("Debug: Case 4 - Connecting agent to agent")
        agent2_prompt_vars = extract_agent_prompt_variables(node2['name'])
        
        print(f"Debug: Agent 2 prompt variables: {agent2_prompt_vars}")

        if var1 and var2:
            print(f"Debug: Using predefined variables: {var1}, {var2}")
            finalize_connection(canvas, node1_id, node2_id, var1, var2)
        elif agent2_prompt_vars:
            var_to_connect = prompt_user_for_variable("Select the variable in the second agent's prompt:", agent2_prompt_vars)
            if var_to_connect:
                print(f"Debug: Connecting with variable: {var_to_connect}")
                finalize_connection(canvas, node1_id, node2_id, "agent_output", var_to_connect)
            else:
                print("Debug: Connection aborted by user")
        else:
            print("Debug: No variables found in the second agent's prompt")
            show_error("No variables found in the second agent's prompt")

    else:
        print(f"Debug: Invalid connection type: {node1['type']} to {node2['type']}")
        show_error("Invalid Connection: Unsupported connection type.")

def extract_tool_output_variables(tool_name):
    tools_file = r'agent_gen\saved_tools\tools.json'
    with open(tools_file, 'r') as f:
        tools = json.load(f)
    
    tool = next((t for t in tools if t['Tool Name'] == tool_name), None)
    if tool:
        code = tool['Tool Code']
        return_match = re.search(r'return\s+(.+)', code)
        if return_match:
            return [var.strip() for var in return_match.group(1).split(',')]
    return []

def extract_tool_input_variables(tool_name):
    tools_file = r'agent_gen\saved_tools\tools.json'
    with open(tools_file, 'r') as f:
        tools = json.load(f)
    
    tool = next((t for t in tools if t['Tool Name'] == tool_name), None)
    if tool:
        code = tool['Tool Code']
        input_match = re.search(r'def\s+\w+\((.*?)\)\s*:', code)
        if input_match:
            return [var.strip() for var in input_match.group(1).split(',')]
    return []

def extract_agent_prompt_variables(agent_name):
    agents_file = r'agent_gen\saved_agents\agents.json'
    with open(agents_file, 'r') as f:
        agents = json.load(f)
    
    agent = next((a for a in agents if a['Agent Name'] == agent_name), None)
    if agent:
        prompt = agent['Agent Prompt']
        return re.findall(r'\{(\w+)\}', prompt)
    return []

def prompt_user_for_variable(prompt, variables):
    root = tk.Tk()
    root.withdraw()
    variable = simpledialog.askstring("Select Variable", prompt, initialvalue=variables[0] if variables else "")
    if variable in variables:
        return variable
    return None

def show_error(message):
    messagebox.showerror("Connection Error", message)

def finalize_connection(canvas, node1_id, node2_id, var1, var2):
    color = get_unique_color(canvas)
    connection_id = draw_connection_line(canvas, node1_id, node2_id, color)
    canvas.nodes[node1_id]["connections"].append(connection_id)
    canvas.nodes[node2_id]["connections"].append(connection_id)
    canvas.connections[connection_id] = {"nodes": (node1_id, node2_id), "color": color, "var1": var1, "var2": var2}
    print(f"Debug: Connection finalized between {node1_id} and {node2_id} with variables {var1}, {var2}")

def draw_connection_line(canvas, node1_id, node2_id, color):
    node1 = canvas.nodes[node1_id]["canvas_id"]
    node2 = canvas.nodes[node2_id]["canvas_id"]
    x1, y1 = get_node_right_middle(canvas, node1)
    x2, y2 = get_node_left_middle(canvas, node2)

    connection_id = f"connection_{node1_id}_{node2_id}"

    line = canvas.create_line(x1, y1, x2, y2, fill=color, width=2, tags=("connection_line", connection_id))

    draw_arrowhead(canvas, x1, y1, x2, y2, color, connection_id)

    return connection_id

def draw_arrowhead(canvas, x1, y1, x2, y2, color, connection_id):
    angle = math.atan2(y2 - y1, x2 - x1)
    arrow_length = 15
    arrow_x = x2 - arrow_length * math.cos(angle)
    arrow_y = y2 - arrow_length * math.sin(angle)

    arrowhead = canvas.create_polygon(
        [x2, y2, 
         arrow_x - 8 * math.cos(angle - math.pi/6), arrow_y - 8 * math.sin(angle - math.pi/6),
         arrow_x - 8 * math.cos(angle + math.pi/6), arrow_y - 8 * math.sin(angle + math.pi/6)],
        fill=color, outline=color, tags=("connection_arrow", connection_id)
    )
    return arrowhead

def update_node_connections(canvas, node_id):
    for connection_id in canvas.nodes[node_id]["connections"]:
        if connection_id in canvas.connections:
            node1_id, node2_id = canvas.connections[connection_id]["nodes"]
            color = canvas.connections[connection_id]["color"]
            
            canvas.delete(connection_id)
            
            new_connection_id = draw_connection_line(canvas, node1_id, node2_id, color)
            canvas.connections[new_connection_id] = canvas.connections.pop(connection_id)
            canvas.nodes[node1_id]["connections"].remove(connection_id)
            canvas.nodes[node1_id]["connections"].append(new_connection_id)
            canvas.nodes[node2_id]["connections"].remove(connection_id)
            canvas.nodes[node2_id]["connections"].append(new_connection_id)

def get_node_right_middle(canvas, node):
    x1, y1, x2, y2 = canvas.bbox(node)
    return x2, (y1 + y2) / 2

def get_node_left_middle(canvas, node):
    x1, y1, x2, y2 = canvas.bbox(node)
    return x1, (y1 + y2) / 2

def draw_grid(canvas, grid_size=100, line_color="#3c3c3c"):
    canvas_width = canvas.winfo_width()
    canvas_height = canvas.winfo_height()
    canvas.delete("grid")
    for x in range(0, canvas_width, grid_size):
        canvas.create_line(x, 0, x, canvas_height, fill=line_color, tags="grid")
    for y in range(0, canvas_height, grid_size):
        canvas.create_line(0, y, canvas_width, y, fill=line_color, tags="grid")

def on_canvas_resize(event, canvas):
    if canvas.master.master.canvas_settings["show_grid"]:
        draw_grid(canvas, grid_size=canvas.master.master.canvas_settings["grid_size"])

def on_canvas_window_close(main_app, open_canvas_frame, original_width, original_height):
    if hasattr(main_app, 'canvas'):
        clear_canvas(main_app.canvas)
    
    close_open_canvas_frame(main_app, open_canvas_frame, original_width, original_height)

    
    set_active_window("canvas_frame")
    
    main_app.protocol("WM_DELETE_WINDOW", main_app.destroy)

def snap_to_grid(event, canvas):
    grid_size = canvas.master.master.canvas_settings["grid_size"]
    x = round(event.x / grid_size) * grid_size
    y = round(event.y / grid_size) * grid_size

def close_open_canvas_frame(main_app, open_canvas_frame, original_width, original_height):
    open_canvas_frame.destroy()
    main_app.geometry(f"{original_width}x{original_height}")
    main_app.canvas_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.8, relheight=0.8)
    
    if hasattr(main_app, 'open_canvas_frame'):
        del main_app.open_canvas_frame

def save_workflow(main_app, canvas):
    workflow_name = simpledialog.askstring("Save Workflow", "Enter a name for this workflow:", parent=main_app)
    if not workflow_name:
        return  

    workflow_data = {
        "agents": [],
        "tools": [],
        "connections": []
    }

    for node_id, node_info in canvas.nodes.items():
        if node_info["type"] == "agent":
            workflow_data["agents"].append({
                "id": node_id,
                "name": node_info["name"],
                "position": canvas.coords(node_info["canvas_id"])
            })
        elif node_info["type"] == "tool":
            workflow_data["tools"].append({
                "id": node_id,
                "name": node_info["name"],
                "position": canvas.coords(node_info["canvas_id"])
            })

    for connection_id, connection_info in canvas.connections.items():
        workflow_data["connections"].append({
            "id": connection_id,
            "nodes": list(connection_info["nodes"]),
            "var1": connection_info["var1"],
            "var2": connection_info["var2"]
        })

    workflows_dir = r'agent_gen\saved_workflows'
    os.makedirs(workflows_dir, exist_ok=True)
    workflow_file = os.path.join(workflows_dir, f"{workflow_name}.json")

    with open(workflow_file, 'w', encoding='utf-8') as f:
        json.dump(workflow_data, f, ensure_ascii=False, indent=4)

    messagebox.showinfo("Success", f"Workflow '{workflow_name}' saved successfully.")

def load_workflow(main_app, canvas):
    workflows_dir = r'agent_gen\saved_workflows'
    workflow_file = filedialog.askopenfilename(
        title="Select Workflow to Load",
        initialdir=workflows_dir,
        filetypes=[("JSON files", "*.json")]
    )
    if not workflow_file:
        return 

    try:
        with open(workflow_file, 'r', encoding='utf-8') as f:
            workflow_data = json.load(f)
        
        clear_canvas(canvas)
        
        # Load agents
        for agent in workflow_data['agents']:
            add_node_to_canvas(canvas, agent['name'], 'agent', position=agent['position'], node_id=agent['id'])
        
        # Load tools
        for tool in workflow_data['tools']:
            add_node_to_canvas(canvas, tool['name'], 'tool', position=tool['position'], node_id=tool['id'])
        
        # Load connections
        for connection in workflow_data['connections']:
            node1_id = connection['nodes'][0]
            node2_id = connection['nodes'][1]
            connect_nodes(canvas, node1_id, node2_id, var1=connection['var1'], var2=connection['var2'])
        
        workflow_name = os.path.splitext(os.path.basename(workflow_file))[0]
        messagebox.showinfo("Success", f"Workflow '{workflow_name}' loaded successfully.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load workflow: {str(e)}")

def choose_execution_environment(main_app):
    use_venv = messagebox.askyesno("Execution Environment", "Do you want to execute the workflow in a virtual environment?")
    if use_venv:
        venv_path = filedialog.askdirectory(title="Select Virtual Environment Directory")
        if not venv_path:
            return None  
        
        # Validate if the selected directory is a valid venv
        activate_script = os.path.join(venv_path, "Scripts", "activate.bat") if sys.platform == "win32" else os.path.join(venv_path, "bin", "activate")
        if not os.path.exists(activate_script):
            messagebox.showerror("Invalid Virtual Environment", "The selected directory does not appear to be a valid virtual environment.")
            return None
        
        return venv_path
    else:
        return "default"

def execute_workflow_in_environment(workflow_data, update_output, venv_path=None):
    if venv_path and venv_path != "default":
        if sys.platform == "win32":
            activate_script = os.path.join(venv_path, "Scripts", "activate.bat")
            python_executable = os.path.join(venv_path, "Scripts", "python.exe")
        else:
            activate_script = os.path.join(venv_path, "bin", "activate")
            python_executable = os.path.join(venv_path, "bin", "python")
        
        script = f"""
import sys
sys.path.append('.')
from ag_canvas_workflow import generate_and_execute_workflow
workflow_data = {workflow_data}
generate_and_execute_workflow(workflow_data, print)
"""
        
        temp_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_workflow_script.py")
        with open(temp_script_path, "w") as temp_file:
            temp_file.write(script)
        
        try:
            if sys.platform == "win32":
                process = subprocess.Popen(f'"{activate_script}" && "{python_executable}" "{temp_script_path}"', 
                                           shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            else:
                process = subprocess.Popen(f'source "{activate_script}" && "{python_executable}" "{temp_script_path}"', 
                                           shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, executable="/bin/bash")
            
            for line in process.stdout:
                update_output(line.strip())
            for line in process.stderr:
                update_output(f"Error: {line.strip()}")
            
            process.wait()
            if process.returncode != 0:
                update_output(f"Execution failed with return code {process.returncode}")
        finally:
            if os.path.exists(temp_script_path):
                os.remove(temp_script_path)
    else:
        generate_and_execute_workflow(workflow_data, update_output)
        
def execute_workflow(main_app, canvas):
    workflow_data = {
        "agents": [],
        "tools": [],
        "connections": []
    }

    for node_id, node_info in canvas.nodes.items():
        if node_info["type"] == "agent":
            workflow_data["agents"].append({
                "id": node_id,
                "name": node_info["name"],
            })
        elif node_info["type"] == "tool":
            workflow_data["tools"].append({
                "id": node_id,
                "name": node_info["name"],
            })

    for connection_id, connection_info in canvas.connections.items():
        workflow_data["connections"].append({
            "id": connection_id,
            "nodes": list(connection_info["nodes"]),
            "var1": connection_info.get("var1", ""),
            "var2": connection_info.get("var2", "")
        })

    venv_path = choose_execution_environment(main_app)
    if venv_path is None:
        return 

    output_window = tk.Toplevel(main_app)
    output_window.title("Workflow Execution")
    output_window.geometry("800x600")

    output_text = scrolledtext.ScrolledText(output_window, wrap=tk.WORD, bg="#1f1f3b", fg="white", font=("Helvetica", 12))
    output_text.pack(expand=True, fill="both", padx=10, pady=10)

    def update_output(text):
        output_text.insert(tk.END, text + "\n")
        output_text.see(tk.END)
        output_text.update()

    def run_workflow():
        execute_workflow_in_environment(workflow_data, update_output, venv_path)

    threading.Thread(target=run_workflow, daemon=True).start()