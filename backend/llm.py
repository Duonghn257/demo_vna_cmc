from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel
import os

load_dotenv(override=True)

client = OpenAI(
    api_key=os.getenv("GOOGLE_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

class Result(BaseModel):
    content: str
    check: bool

def spelling_check(text: str) -> Result:
    """
    This function checks the spelling of the input text and rewrites it if there are any spelling mistakes.
    Returns a Result object with the corrected content and a boolean indicating if changes were made.
    The 'check' field is True if the text was already correct (no changes needed), and False if corrections were made.
    """
    model = "gemini-2.5-flash"
    system_prompt = (
        "You are a spelling and grammar assistant. "
        "Check the user's text for spelling mistakes. "
        "If the text is already correct, return it as is and set 'check' to true. "
        "If there are any spelling or grammar mistakes, rewrite the text with correct spelling and grammar, and set 'check' to false. "
        "Respond in the following JSON format:\n"
        "{'content': '<corrected or original text>', 'check': <true if nothing has to change, false if spelling is not correct>}"
    )
    response = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": text,
            }
        ],
        response_format=Result
    )
    return response.choices[0].message.content

def main():
    text= "Tôi là Nguyễn Hoangfd Dương, sinh năm 2000"
    response = spelling_check(text)

if __name__ == "__main__":
    main()