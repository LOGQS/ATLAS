# ag_canvas_settings.py
import tkinter as tk
from tkinter import colorchooser
from gui_element_manager import register_window, register_element, set_active_window, gui_manager

def show_canvas_settings_frame(main_app):
    settings_window = tk.Toplevel(main_app)
    settings_window.title("Canvas Settings")
    settings_window.geometry("400x380")
    settings_window.configure(bg="#2c2c2c")
    settings_window.resizable(False, False)

    register_window("canvas_settings", settings_window)
    settings_window.bind("<FocusIn>", lambda e: set_active_window("canvas_settings"))

    settings_window.transient(main_app)
    settings_window.grab_set()

    temp_settings = main_app.canvas_settings.copy()

    bg_color_label = tk.Label(settings_window, text="Background Color:", bg="#2c2c2c", fg="white", font=("Helvetica", 12))
    bg_color_label.pack(pady=(10, 5))
    register_element("canvas_settings", "bg_color_label", bg_color_label, "label")

    color_frame = tk.Frame(settings_window, bg="#2c2c2c")
    color_frame.pack()

    color_preview = tk.Frame(color_frame, width=20, height=20, bg=temp_settings["bg_color"])
    color_preview.pack(side=tk.LEFT, padx=(0, 10))
    register_element("canvas_settings", "color_preview", color_preview, "frame")

    bg_color_button = tk.Button(
        color_frame,
        text="Choose Color",
        command=lambda: choose_color(temp_settings, color_preview),
        bg="#444444",
        fg="white",
        activebackground="#666666",
        activeforeground="white",
        font=("Helvetica", 10)
    )
    bg_color_button.pack(side=tk.LEFT)
    register_element("canvas_settings", "bg_color_button", bg_color_button, "button")

    # Grid Options
    grid_var = tk.BooleanVar(value=temp_settings["show_grid"])
    grid_checkbutton = tk.Checkbutton(
        settings_window,
        text="Show Grid",
        variable=grid_var,
        bg="#2c2c2c",
        fg="white",
        selectcolor="#1e1e1e",
        activebackground="#2c2c2c",
        activeforeground="white",
        font=("Helvetica", 12)
    )
    grid_checkbutton.pack(pady=10)
    register_element("canvas_settings", "grid_checkbutton", grid_checkbutton, "checkbutton")

    # Snap to Grid
    snap_var = tk.BooleanVar(value=temp_settings["snap_to_grid"])
    snap_checkbutton = tk.Checkbutton(
        settings_window,
        text="Snap to Grid",
        variable=snap_var,
        bg="#2c2c2c",
        fg="white",
        selectcolor="#1e1e1e",
        activebackground="#2c2c2c",
        activeforeground="white",
        font=("Helvetica", 12)
    )
    snap_checkbutton.pack(pady=10)
    register_element("canvas_settings", "snap_checkbutton", snap_checkbutton, "checkbutton")

    # Grid Size
    grid_size_label = tk.Label(settings_window, text="Grid Size:", bg="#2c2c2c", fg="white", font=("Helvetica", 12))
    grid_size_label.pack(pady=5)
    register_element("canvas_settings", "grid_size_label", grid_size_label, "label")

    grid_size_var = tk.IntVar(value=temp_settings.get("grid_size", 20))
    grid_size_entry = tk.Entry(settings_window, textvariable=grid_size_var, width=5, font=("Helvetica", 12))
    grid_size_entry.pack()
    register_element("canvas_settings", "grid_size_entry", grid_size_entry, "entry")

    # Save Button
    save_button = tk.Button(
        settings_window,
        text="Save Settings",
        command=lambda: save_settings(main_app, settings_window, temp_settings, grid_var.get(), snap_var.get(), grid_size_var.get()),
        bg="#4a4a4a",
        fg="white",
        activebackground="#666666",
        activeforeground="white",
        font=("Helvetica", 12, "bold")
    )
    save_button.pack(pady=20)
    register_element("canvas_settings", "save_button", save_button, "button")

    settings_window.protocol("WM_DELETE_WINDOW", lambda: on_closing(main_app, settings_window))

    set_active_window("canvas_settings")

    return settings_window

def choose_color(temp_settings, color_preview):
    color = colorchooser.askcolor(title="Choose canvas background color", initialcolor=temp_settings["bg_color"])
    if color[1]:
        temp_settings["bg_color"] = color[1]
        color_preview.configure(bg=color[1])

def save_settings(main_app, settings_window, temp_settings, grid, snap, grid_size):
    main_app.canvas_settings = temp_settings.copy()
    main_app.canvas_settings["show_grid"] = grid
    main_app.canvas_settings["snap_to_grid"] = snap
    main_app.canvas_settings["grid_size"] = grid_size
    settings_window.destroy()
    main_app.canvas_settings_window = None
    
    update_canvas(main_app)

def update_canvas(main_app):
    for widget in main_app.winfo_children():
        if isinstance(widget, tk.Frame) and widget.winfo_class() == "Frame":
            for child in widget.winfo_children():
                if isinstance(child, tk.Canvas):
                    child.configure(bg=main_app.canvas_settings["bg_color"])
                    if main_app.canvas_settings["show_grid"]:
                        draw_grid(child, grid_size=main_app.canvas_settings["grid_size"])
                    else:
                        child.delete("grid")
                    child.bind("<Configure>", lambda event, canvas=child: on_canvas_resize(event, canvas))
                    break
            break

def on_closing(main_app, settings_window):
    settings_window.destroy()
    main_app.canvas_settings_window = None

def draw_grid(canvas, grid_size=20, line_color="#3c3c3c"):
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