import openai
import json

with open('openai_config.json') as f:
    config = json.load(f)
    client = openai.OpenAI(api_key=config['openai_api_key'])
    print("API Key impostata:", config['openai_api_key'][:10] + "...")

try:
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Ciao!"}]
    )
    print(response.choices[0].message.content)
except Exception as e:
    print("Errore:", e) 