# live_fix_monitor.py
import google.generativeai as genai
from PIL import ImageGrab
import os
import json
import re
from json_fixer_prompt import json_fixer_prompt

class LiveFixMonitor:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-1.5-flash', system_instruction="""
        You are an AI assistant that analyzes screenshots. Your task is to:
        1. Describe the relevant parts of the screenshot based on the given instruction.
        2. Determine if the condition specified in the instruction is EXACTLY met.

        Provide your response in the following format:
        {
            "screen_description_no_further_thinking": "Description of relevant parts of the screenshot based on the instruction.",
            "screen_description": "Detailed description of relevant parts of the screenshot and if the condition is met: describe that condition is met then how and why.",
            "thoughts": Thoughts on if the condition is met or not. Does the screenshot meet the condition? Why or why not?",
            "detailed_reasoning": "Detailed reasoning for your thoughts and enabling true/false decision. Does the screenshot meet the condition for sure? If yes, why? If no, why not?",
            "condition_met": true/false
            
        }
        """)
        self.screenshot_path = os.path.join('imgs', 'current_screen', 'current_screen.png')
        os.makedirs(os.path.dirname(self.screenshot_path), exist_ok=True)
        self.json_fixer_model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=json_fixer_prompt)

    def parse_json_response(self, response):
        if isinstance(response, dict):
            return response
        
        def fix_json_issues(bad_json):
            bad_json = re.sub(r'(?<!")(\b\w+\b)(?=\s*:)', r'"\1"', bad_json)
            bad_json = re.sub(r'\\(?![\\"])', r'\\\\', bad_json)
            bad_json = re.sub(r'\\[^\\"]', r'', bad_json)
            bad_json = re.sub(r'(?<=\w)(\s*)(?=")', r',\1', bad_json)
            if bad_json.count('{') > bad_json.count('}'):
                bad_json += '}'
            if bad_json.count('[') > bad_json.count(']'):
                bad_json += ']'
            bad_json = re.sub(r',(\s*[}\]])', r'\1', bad_json)
            bad_json = re.sub(r':(\S)', r': \1', bad_json)
            bad_json = re.sub(r'\bNone\b', 'null', bad_json)
            bad_json = re.sub(r'\bTrue\b', 'true', bad_json)
            bad_json = re.sub(r'\bFalse\b', 'false', bad_json)
            return bad_json

        cleaned_response = re.sub(r'^```json\n|```$', '', response).strip()
        cleaned_response = cleaned_response.replace("```", "")

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            cleaned_response = fix_json_issues(cleaned_response)
            try:
                return json.loads(cleaned_response)
            except json.JSONDecodeError:
                return self.fix_json_with_model(cleaned_response)

    async def fix_json_with_model(self, bad_json):
        try:
            response = await self.json_fixer_model.generate_content_async(
                f"Fix this JSON:\n\n{bad_json}",
                generation_config={"temperature": 1, "max_output_tokens": 3000}
            )
            fixed_json = response.text
            print(f"Monitor response: {fixed_json}")
            cleaned_fixed_json = re.sub(r'^```json\n|```$', '', fixed_json).strip()
            cleaned_fixed_json = cleaned_fixed_json.replace("```", "")
            return json.loads(cleaned_fixed_json)
        except Exception as e:
            print(f"Error fixing JSON with model: {str(e)}")
            return None

    async def analyze_screenshot(self, instruction):
        screenshot = ImageGrab.grab()
        screenshot.save(self.screenshot_path)

        try:
            image = genai.upload_file(path=self.screenshot_path, display_name="current_screen.png")
            response = await self.model.generate_content_async(
                [f"Instruction: {instruction}", image],
                generation_config={"temperature": 1}
            )
            parsed_response = self.parse_json_response(response.text)
            if parsed_response and isinstance(parsed_response, dict):
                return parsed_response
            else:
                print("Failed to parse response as JSON")
                return None
        except Exception as e:
            print(f"Error analyzing screenshot: {str(e)}")
            return None

live_fix_monitor = LiveFixMonitor()