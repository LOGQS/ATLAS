# observe_func_sum.py
import os
import time
import google.generativeai as genai
import cv2
import json
from memory_main import MemoryManager

# API Configuration
config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
genai.configure(api_key=json.loads(open(config_path).read())['api_keys']['GEMINI_API_KEY'])
model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest")
generation_config = genai.types.GenerationConfig(
    temperature=1,
    max_output_tokens=8000,
)

output_path = r'observe_data'
summary_file_path = os.path.join(output_path, "observed_summary.txt")
finished_recordings_path = os.path.join(output_path, "finished_recordings.json")
is_summarizing = False

def get_summarizing_status():
    global is_summarizing
    return is_summarizing

def set_summarizing_status(status):
    global is_summarizing
    is_summarizing = status

def load_finished_recordings():
    if os.path.exists(finished_recordings_path):
        with open(finished_recordings_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    return []

def save_finished_recordings(recordings):
    with open(finished_recordings_path, 'w', encoding='utf-8') as file:
        json.dump(recordings, file, ensure_ascii=False, indent=4)

def compress_video(video_filename):
    compressed_filename = video_filename.replace(".avi", "_compressed.avi")
    try:
        cap = cv2.VideoCapture(video_filename)
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        out = cv2.VideoWriter(compressed_filename, fourcc, 60, (int(cap.get(3)), int(cap.get(4))))

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            out.write(frame)
        
        cap.release()
        out.release()

        os.remove(video_filename)
        return compressed_filename
    except Exception as e:
        print(f"Error compressing video {video_filename}: {e}")
        return None

def process_recording(video_path):
    try:
        compressed_video = compress_video(video_path)
        if not compressed_video:
            return

        video_name = "User's screen recording"
        video = genai.upload_file(path=compressed_video, display_name=video_name)

        while video.state.name == "PROCESSING":
            time.sleep(10)
            video = genai.get_file(video.name)

        if video.state.name == "FAILED":
            raise ValueError(video.state.name)

        content = """
        Summarize the video down to last detail. Describe scene changes, everything that happen in the screen without missing anything. 
        Big or small include everything down to last speck of detail while writing everything around 6000 words. ALWAYS INCLUDE EVERYTHING THAT HAPPENED IN THE VIDEO.
        The information SHOULD ALWAYS BE detailed, logical, and informative. Describe it in a way that it is easy to understand and follow. These will be user actions,
        screen changes and the content of the screen. TRY TO DESCRIBE AS MUCH AS YOU CAN DOWN TO SMALLEST DETAIL ABOUT CONTENT OF THE SCREEN WHILE ALWAYS 
        INCLUDING EVERYTHING THAT HAPPENED IN THE VIDEO. IN YOUR FINAL RESPONSE DO NOT REPEAT YOURSELF. IF YOUR SENTENCES ARE EXACTLY IDENTICAL, REMOVE THE DUPLICATES. 
        BE HIGHLY INTELLIGENT AND ANALYTICAL WHILE SUMMARIZING THE VIDEO FULLY. DESCRIBE THE VIDEO AS IF YOU ARE SEEING IT RATHER THAN YOU WATCHING IT. WHEN SOMETHING IS 
        REPEATING WITH A PATTERN YOU CAN DESCRIBE IT ONCE THEN DEFINE HOW IT IS REPEATED, THEN DESCRIBE THE CHANGES IN THE PATTERN. ALWAYS INCLUDE EVERYTHING THAT HAPPENED 
        IN THE VIDEO.
        """

        response = model.generate_content([content, video], generation_config=generation_config)

        with open(summary_file_path, 'a', encoding='utf-8') as f:
            f.write(f"\nSummary of {os.path.basename(video_path)}:\n")
            f.write(response.text)
            f.write("\n" + "="*80 + "\n")

        genai.delete_file(video.name)
        os.remove(compressed_video)

        if MemoryManager.memory_enabled:
            memory_manager = MemoryManager()
            memory_manager.append_to_full_memory("OBSERVED USER BEHAVIOUR", response.text)

        recordings = load_finished_recordings()
        if os.path.basename(video_path) in recordings:
            recordings.remove(os.path.basename(video_path))
        save_finished_recordings(recordings)
    except Exception as e:
        print(f"Error processing recording {video_path}: {e}")

def process_next_video():
    global is_summarizing
    is_summarizing = True
    recordings = load_finished_recordings()
    if recordings:
        smallest_recording = sorted(recordings)[0]
        process_recording(os.path.join(output_path, smallest_recording))
    is_summarizing = False

if __name__ == "__main__":
    process_next_video()
