from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY is missing. Add it to your .env file before running this test.")

client = genai.Client(api_key=api_key)
question = "Say hello in one sentence."

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents=question,
)

print(response.text)