# observe_func_rec.py
import cv2
import numpy as np
import pyautogui
import time
import os
import json
import threading

# Global variables
recording = False
recording_interval = 60
recording_counter = 1
stop_requested = False
fps = 20
output_path = r'observe_data'
finished_recordings_path = os.path.join(output_path, "finished_recordings.json")
recording_count = 0

if not os.path.exists(output_path):
    os.makedirs(output_path)

def get_recording_count():
    global recording_count
    return recording_count

def increment_recording_count():
    global recording_count
    recording_count += 1

def load_finished_recordings():
    if os.path.exists(finished_recordings_path):
        with open(finished_recordings_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    return []

def save_finished_recordings(recordings):
    with open(finished_recordings_path, 'w', encoding='utf-8') as file:
        json.dump(recordings, file, ensure_ascii=False, indent=4)

def screen_recorder():
    global recording, recording_counter, stop_requested, recording_count
    screen_size = pyautogui.size()
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    frame_duration = 1 / fps

    while recording or not stop_requested:
        video_filename = os.path.join(output_path, f"Recording{recording_counter}.avi")
        out = cv2.VideoWriter(video_filename, fourcc, fps, screen_size)
        start_time = time.time()
        last_timestamp = start_time
        

        while (recording or not stop_requested) and (time.time() - start_time) < recording_interval:
            frame_start_time = time.time()
            img = pyautogui.screenshot()
            frame = np.array(img)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            out.write(frame)

            current_time = time.time()
            if current_time - last_timestamp >= 1:
                elapsed_time = current_time - start_time
                last_timestamp = current_time

            time_to_sleep = frame_duration - (time.time() - frame_start_time)
            if time_to_sleep > 0:
                time.sleep(time_to_sleep)

        out.release()
        
        recordings = load_finished_recordings()
        recordings.append(f"Recording{recording_counter}.avi")
        save_finished_recordings(recordings)
        recording_counter += 1
        increment_recording_count()

    if stop_requested:
        last_video_filename = os.path.join(output_path, f"Recording{recording_counter}.avi")
        if os.path.exists(last_video_filename):
            print(f"Recording {recording_counter} finished and saved to {last_video_filename}")

def start_recording():
    global recording, recording_counter
    recording = True
    recording_counter = 1
    threading.Thread(target=screen_recorder).start()

def stop_recording():
    global recording, stop_requested
    stop_requested = True
    recording = False
