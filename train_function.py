# train_function.py
import os
import re
import json
import time
import threading
import pyautogui
import cv2
import numpy as np
from pynput import mouse, keyboard
import google.generativeai as genai
from memory_main import MemoryManager

# Configure API key
config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
genai.configure(api_key=json.loads(open(config_path).read())['api_keys']['GEMINI_API_KEY'])

# Initialize the models
model1 = genai.GenerativeModel(model_name="models/gemini-1.5-pro")
model2 = genai.GenerativeModel(model_name="gemini-1.5-flash")

generation_config = genai.types.GenerationConfig(
    temperature=1,
    max_output_tokens=3000,
)

# Define paths
action_data_path = r"action_data\\user_actions.json"
formatted_data_path = r"action_data\\formatted_events.json"
ability_memory_path = r"action_data\\ability_memory.json"
video_path = r"action_data\\screen_recording.avi"

# Global variables for recording
mouse_events = []
keyboard_events = []
recording = False
lock = threading.Lock()
auto_stop_timer = None

def start_recording():
    global recording, auto_stop_timer
    recording = True

    # Clear previous data
    if os.path.exists(action_data_path):
        os.remove(action_data_path)
    if os.path.exists(video_path):
        os.remove(video_path)

    threading.Thread(target=record_mouse_keyboard).start()
    threading.Thread(target=screen_recorder).start()

    # Start the auto-stop timer
    auto_stop_timer = threading.Timer(40 * 60, auto_stop_recording)
    auto_stop_timer.start()

def auto_stop_recording():
    stop_recording()

def stop_recording(status_callback=None):
    global recording, auto_stop_timer
    recording = False
    
    if auto_stop_timer and auto_stop_timer.is_alive():
        auto_stop_timer.cancel()
    
    time.sleep(1)

    if status_callback:
        status_callback("Saving data...")

    # Remove the last click event to avoid the stop button click being recorded
    with lock:
        if mouse_events and mouse_events[-1]['event'] == 'click':
            mouse_events.pop()

        data = {
            'mouse_events': mouse_events,
            'keyboard_events': keyboard_events,
        }
        with open(action_data_path, 'w') as file:
            json.dump(data, file, indent=4)
    
    if status_callback:
        status_callback("Formatting data...")
    
    format_data(action_data_path, formatted_data_path)
    process_model(status_callback)

def record_mouse_keyboard():
    mouse_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll)
    keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)

    mouse_listener.start()
    keyboard_listener.start()

    mouse_listener.join()
    keyboard_listener.join()

def screen_recorder():
    global recording
    screen_size = pyautogui.size()
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    out = cv2.VideoWriter(video_path, fourcc, 20.0, screen_size)

    try:
        while recording:
            img = pyautogui.screenshot()
            frame = np.array(img)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            out.write(frame)
    except Exception as e:
        print(f"Error during screen recording: {e}")
    finally:
        out.release()

def on_click(x, y, button, pressed):
    if not recording:
        return False
    with lock:
        event = {
            'event': 'click',
            'x': x,
            'y': y,
            'button': str(button),
            'pressed': pressed,
            'time': time.time()
        }
        mouse_events.append(event)

def on_scroll(x, y, dx, dy):
    if not recording:
        return False
    with lock:
        event = {
            'event': 'scroll',
            'x': x,
            'y': y,
            'dx': dx,
            'dy': dy,
            'time': time.time()
        }
        mouse_events.append(event)

def on_press(key):
    if not recording:
        return False
    with lock:
        event = {
            'event': 'press',
            'key': str(key),
            'time': time.time()
        }
        keyboard_events.append(event)

def on_release(key):
    if not recording:
        return False
    with lock:
        event = {
            'event': 'release',
            'key': str(key),
            'time': time.time()
        }
        keyboard_events.append(event)

def load_data(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

def format_event(event):
    if event['event'] == 'click' and event['pressed']:
        return f"Mouse click at ({event['x']}, {event['y']}), button: {event['button']}"
    elif event['event'] == 'press' and event['key'].startswith("Key."):
        return f"Key click: {event['key']}"
    return None

def create_sequential_list(data):
    events = data['mouse_events'] + data['keyboard_events']
    events.sort(key=lambda x: x['time'])

    formatted_events = []
    last_time = None
    word = ""

    for event in events:
        if last_time is not None:
            interval = f"{event['time'] - last_time:.6f} seconds"
        else:
            interval = "0 seconds"

        event_desc = format_event(event)

        if event_desc:
            if word:
                formatted_events.append({
                    "event": f"Typed word: {word}",
                    "interval": interval
                })
                word = ""
            formatted_events.append({
                "event": event_desc,
                "interval": interval
            })
        else:
            if event['event'] == 'press' and not event['key'].startswith("Key."):
                word += event['key'].replace("'", "")

        last_time = event['time']

    if word:
        formatted_events.append({
            "event": f"Typed word: {word}",
            "interval": interval
        })

    return formatted_events

def save_data(data, file_path):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

def format_data(input_file, output_file):
    data = load_data(input_file)
    formatted_events = create_sequential_list(data)
    save_data(formatted_events, output_file)

def process_model(status_callback=None):
    if status_callback:
        status_callback("Processing data...")

    if os.path.exists(ability_memory_path):
        with open(ability_memory_path, 'r') as file:
            existing_data = json.load(file)
    else:
        existing_data = []

    formatted_events = load_data(formatted_data_path)
    formatted_events_str = json.dumps(formatted_events, indent=4)

    if status_callback:
        status_callback("Uploading video...")

    video_name = "User's screen recording"
    video = genai.upload_file(path=video_path, display_name=video_name)

    while video.state.name == "PROCESSING":
        time.sleep(10)
        video = genai.get_file(video.name)

    if video.state.name == "FAILED":
        raise ValueError(video.state.name)
    
    if status_callback:
        status_callback("Generating content...")

    content1 = f"""
    -------------------------------------------------------------------------
    events: {formatted_events_str}
    -------------------------------------------------------------------------
    Analyze the "events" section and the provided video to identify distinct user goals and create step-by-step action lists. Follow these guidelines:

    1. Identify all unique actions, even if they seem unrelated or mistaken.
    2. Group related actions into distinct goals.
    3. For each goal, provide:

    Goal: [Concise description of the user's intention]
    Steps to reach the goal:
    [Detailed steps with xy locations and time intervals]
    Conceptually what happened:
    [High-level description of user actions, focusing on intentions rather than specific clicks/keys]
    Reasoning:
    [Explain your analysis, including how you determined these actions and the observed screen changes]

    Separate each goal with a line of 10 hyphens (----------).

    Be thorough, logical, and accurate in your analysis. Consider all actions, even if they seem irrelevant or mistaken. Avoid duplicating goals or steps.
    """


    response = model1.generate_content([content1, video], generation_config=generation_config)
    genai.delete_file(video.name)

    unformatted_action = response.text

    if status_callback:
        status_callback("Refining content...")

    content2 = f"""
    -------------------------------------------------------------------------
    Unformatted_action: {unformatted_action}
    -------------------------------------------------------------------------
    Review the "Unformatted_action" section carefully and create a structured, non-redundant list of user goals and actions. Follow these criteria:

    1. Ensure each goal is unique and clearly defined.
    2. Include only the necessary steps to achieve each goal.
    3. Eliminate any duplicate goals or redundant steps.
    4. Format actions to be easily executable by automation tools.
    5. Provide clear, concise conceptual steps for each goal.

    For each unique goal, use the following format:

    goal: [Concise goal description]
    actions:
    - description: [Step description]
        action_type: [rightclick, leftclick, scroll, type, shortcut, etc.]
        coordinates: [xy coordinates if applicable/None if not](give without brackets e.g. 100, 200)
        value: [text value if applicable/None if not]
        timestamp: [cumulative timestamp]
    conceptual_steps:
    - step: [High-level step description]
    reasoning: [Explain your analysis and any significant screen changes]

    Separate each goal with a line of 10 hyphens (----------).
    """

    response = model2.generate_content(content2, generation_config=generation_config)

    structured_responses = convert_to_structured_format(response.text)

    if status_callback:
        status_callback("Saving ability memory...")

    # Load existing ability memory
    if os.path.exists(ability_memory_path):
        with open(ability_memory_path, 'r') as file:
            existing_abilities = json.load(file)
    else:
        existing_abilities = []

    # Append new abilities as a new group
    existing_abilities.append(structured_responses)

    with open(ability_memory_path, 'w') as file:
        json.dump(existing_abilities, file, indent=4)

    if MemoryManager.memory_enabled:
        memory_manager = MemoryManager()
        for response in structured_responses:
            memory_manager.append_to_full_memory("SAVED ABILITIES", json.dumps(response))
    
    if status_callback:
        status_callback("Processing complete")
    
    if status_callback:
        status_callback("Cleaning up temporary files...")

    cleanup_files = [action_data_path, formatted_data_path, video_path]
    for file_path in cleanup_files:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file {file_path}: {str(e)}")

    if status_callback:
        status_callback("Cleanup complete")

def convert_to_structured_format(text):
    goal_sections = re.split(r'-{10,}', text)
    
    structured_responses = []
    
    for section in goal_sections:
        if not section.strip():
            continue
        
        goal_match = re.search(r'goal:\s*(.+?)(?=\n\s*actions:|\n\s*conceptual_steps:|\n\s*reasoning:|\Z)', section, re.IGNORECASE | re.DOTALL)
        
        actions_match = re.search(r'actions:(.*?)(?=\n\s*conceptual_steps:|\n\s*reasoning:|\Z)', section, re.IGNORECASE | re.DOTALL)
        
        conceptual_steps_match = re.search(r'conceptual_steps:(.*?)(?=\n\s*reasoning:|\Z)', section, re.IGNORECASE | re.DOTALL)
        
        reasoning_match = re.search(r'reasoning:\s*(.+?)(?=\n{2,}|\Z)', section, re.IGNORECASE | re.DOTALL)

        if goal_match:
            goal = goal_match.group(1).strip()
            
            actions = []
            if actions_match:
                action_blocks = re.findall(r'-\s*description:.+?(?=\n\s*-|\Z)', actions_match.group(1), re.DOTALL)
                actions = [parse_action(block) for block in action_blocks if parse_action(block)]
            
            conceptual_steps = []
            if conceptual_steps_match:
                conceptual_steps = [step.strip() for step in re.findall(r'-\s*(.+)', conceptual_steps_match.group(1))]
            
            reasoning = reasoning_match.group(1).strip() if reasoning_match else ""

            structured_responses.append({
                "goal": goal,
                "actions": actions,
                "conceptual_steps": conceptual_steps,
                "reasoning": reasoning
            })

    return structured_responses

def parse_action(action_text):
    action_pattern = re.compile(
        r'description:\s*(.+?)\n'
        r'(?:\s*action_type:\s*(.+?)\n)?'
        r'(?:\s*coordinates:\s*(.+?)\n)?'
        r'(?:\s*value:\s*(.+?)\n)?'
        r'(?:\s*timestamp:\s*(.+?)(?:\n|$))',
        re.DOTALL
    )
    
    match = action_pattern.search(action_text)
    if match:
        return {
            "description": match.group(1).strip(),
            "action_type": match.group(2).strip() if match.group(2) else None,
            "coordinates": parse_coordinates(match.group(3)),
            "value": parse_value(match.group(4)),
            "timestamp": parse_timestamp(match.group(5))
        }
    return None

def parse_coordinates(coord_str):
    if coord_str and coord_str.lower() != 'none':
        match = re.match(r'(\d+),\s*(\d+)', coord_str)
        if match:
            return [int(match.group(1)), int(match.group(2))]
    return None

def parse_value(value_str):
    if value_str:
        return None if value_str.lower() in ['none', 'null', ''] else value_str.strip('"')
    return None

def parse_timestamp(timestamp_str):
    if timestamp_str:
        match = re.match(r'(\d+):(\d+)', timestamp_str)
        if match:
            minutes, seconds = map(int, match.groups())
            return minutes * 60 + seconds
    return None