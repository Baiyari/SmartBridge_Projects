from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
resp = client.chat.completions.create(
    model='llama-3.3-70b-versatile',
    max_tokens=10,
    messages=[{'role': 'user', 'content': 'ping'}]
)
print("Groq API connected successfully!")
print("Response:", resp.choices[0].message.content)