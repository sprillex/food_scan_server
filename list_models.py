import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Warning: GEMINI_API_KEY not found in environment variables.")

# Initialize Client
client = genai.Client(api_key=api_key)

print("Checking available models...")
try:
    # List models using the new SDK
    # The iterator returns Model objects which have a 'name' attribute
    for m in client.models.list():
        # We can optionally filter here, but listing all is safer to debug
        print(f"- {m.name}")
except Exception as e:
    print(f"Error: {e}")
