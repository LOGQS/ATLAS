# length_limiter.py
import os
import google.generativeai as genai

class LengthLimiter:
    def __init__(self, api_key):
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.generation_config = genai.types.GenerationConfig(
            temperature=1,
            top_p=1,
            top_k=1,
            max_output_tokens=8000,
        )
        self.prompt = """
        Summarize the following content in great detail, maintaining as much important information as possible. 
        The summary should be comprehensive and capture all key points, examples, and nuances from the original text. 
        Aim for a summary of around {max_length} characters.

        Content to summarize:
        {content}
        """

    async def summarize(self, content, max_length):
        if len(content) <= max_length:
            print("Content is already within the desired length.")
            return content
        
        print("Generating summary...")
        response = await self.model.generate_content_async(
            self.prompt.format(content=content, max_length=max_length),
            generation_config=self.generation_config
        )
        print("Summary generated.")
        return response.text

length_limiter = LengthLimiter(os.environ.get("GEMINI_API_KEY"))