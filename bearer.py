import os
import requests
from dotenv import load_dotenv

load_dotenv()

bearer_token = os.getenv('TWITTER_BEARER_TOKEN')

url = "https://api.twitter.com/2/tweets/search/stream/rules"
headers = {
    "Authorization": f"Bearer {bearer_token}",
}

response = requests.get(url, headers=headers)

print("Status Code:", response.status_code)
print("Response:", response.json())
