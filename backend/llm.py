from openai import OpenAI, AsyncOpenAI
from dotenv import load_dotenv
from pydantic import BaseModel
import os

load_dotenv(override=True)

client = AsyncOpenAI(
    api_key=os.getenv("GOOGLE_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

class Result(BaseModel):
    content: str
    idx: int

from typing import List
import json

async def spelling_check(text: str) -> List[Result]:
    """
    Perform spelling check on a list of JSON objects in the following format:
    [
        {"idx": 1, "text": "text string to check here"},
        ...
    ]
    If the text is incorrect, correct its spelling, then add {'content': <corrected_text>, 'idx': <idx>} to the result list.
    Returns a list of Result objects for all corrected items (if no correction needed, skip).
    """
    model = "gemini-2.5-flash"

    system_prompt = (
        "You are a spelling and grammar assistant about an vietnam airline website."
        "You will receive a list of objects, each with an 'idx' and a 'text' field."
        "For each object, check the 'text' for spelling and grammar mistakes in Vietnamese or English. "
        "If the text is correct, do nothing. "
        "If the text is incorrect, rewrite it with correct spelling and grammar. "
        "Return a JSON array of objects, each with 'content' (the corrected text) and 'idx' (the original idx)"
        "for only those items that required correction and must match List[Result] format."
        "Example output:\n"
        "[{'content': 'corrected text', 'idx': 1}, ...]"
    )

    user_prompt = (
        "Check the following list for spelling and grammar mistakes. "
        "Return only the corrected items as described above.\n"
        f"{text}"
    )

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"},
    )

    # After receiving the response
    content_str = response.choices[0].message.content
    corrected_results = [Result(**item) for item in json.loads(content_str)]
    
    return corrected_results

    
def main():
    text= "Tôi là Nguyễn Hoangfd Dương, sinh năm 2000"
    response = spelling_check(text)

if __name__ == "__main__":
    main()