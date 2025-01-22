import os
import time
import logging
from web3 import Web3
from dotenv import load_dotenv
import tweepy
import random
import string
from datetime import datetime
import re

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

# Twitter API credentials for v2
bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
api_key = os.getenv("TWITTER_API_KEY")
api_secret = os.getenv("TWITTER_API_SECRET_KEY")
access_token = os.getenv("TWITTER_ACCESS_TOKEN")
access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

# Web3 and GU Factory settings for Arbitrum
web3 = Web3(Web3.HTTPProvider(os.getenv("WEB3_PROVIDER")))
private_key = os.getenv("PRIVATE_KEY")
if not private_key:
    raise ValueError("PRIVATE_KEY is not set in the environment variables.")
account = web3.eth.account.from_key(private_key)
gu_factory_address = Web3.to_checksum_address(os.getenv("GU_FACTORY_ADDRESS"))
gu_factory_abi = [
    {
        "constant": False,
        "inputs": [
            {"name": "name", "type": "string"},
            {"name": "symbol", "type": "string"},
            {"name": "description", "type": "string"},
        ],
        "name": "deploy",
        "outputs": [{"name": "", "type": "address"}],
        "payable": True,
        "stateMutability": "payable",
        "type": "function",
    }
]
gu_contract = web3.eth.contract(address=gu_factory_address, abi=gu_factory_abi)

# Authenticate with Tweepy for v2 API
client = tweepy.Client(
    bearer_token=bearer_token,
    consumer_key=api_key,
    consumer_secret=api_secret,
    access_token=access_token,
    access_token_secret=access_token_secret,
)

# Persistent storage for processed tweets
processed_tweets_file = "processed_tweets.txt"

# Load processed tweets from file
def load_processed_tweets():
    if not os.path.exists(processed_tweets_file):
        return set()
    with open(processed_tweets_file, "r") as file:
        return set(line.strip() for line in file)

# Save processed tweet ID to file
def save_processed_tweet(tweet_id):
    with open(processed_tweets_file, "a") as file:
        file.write(f"{tweet_id}\n")

processed_tweets = load_processed_tweets()

# Function to generate a unique suffix for tweets
def generate_unique_suffix():
    # Use timestamp and random characters for uniqueness
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
    return f"{timestamp}_{random_string}"

def deploy_token(name, symbol, description):
    """Interact with GUFactory to deploy a token."""
    nonce = web3.eth.get_transaction_count(account.address)

    # Build transaction
    tx = gu_contract.functions.deploy(name, symbol, description).build_transaction({
        'chainId': 42161,  # Arbitrum chain ID
        'gas': 500000,
        'gasPrice': web3.to_wei('5', 'gwei'),
        'nonce': nonce
    })

    # Sign transaction
    signed_tx = web3.eth.account.sign_transaction(tx, private_key=private_key)

    # Send transaction
    tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
    return web3.to_hex(tx_hash)

# Function to parse command from text
def parse_command(text):
    try:
        match = re.search(r"deploy token '(.*?)' with ticker '(.*?)' and description '(.*?)'", text, re.IGNORECASE)
        if not match:
            raise ValueError("Ensure the command follows the correct syntax: deploy token 'NAME' with ticker 'SYMBOL' and description 'DESCRIPTION'.")
        return match.group(1).strip(), match.group(2).strip(), match.group(3).strip()
    except Exception as e:
        raise ValueError(f"Error parsing command: {e}")

# Function to process mentions
def process_mentions():
    global processed_tweets

    # Fetch mentions from Twitter using v2 API
    bot_user_id = client.get_me().data.id
    mentions = client.get_users_mentions(bot_user_id, max_results=5)

    if mentions.data:
        for mention in mentions.data:
            tweet_id = mention.id
            text = mention.text

            # Skip already processed tweets
            if str(tweet_id) in processed_tweets:
                continue

            # Check for "deploy token" command
            if "deploy token" in text.lower():
                try:
                    # Parse token details from the tweet
                    token_name, token_symbol, token_description = parse_command(text)

                    # Deploy token
                    tx_hash = deploy_token(token_name, token_symbol, token_description)

                    # Reply to the user with the transaction hash
                    unique_suffix = generate_unique_suffix()
                    reply_text = f"Your token '{token_name}' with ticker '{token_symbol}' has been deployed! Transaction hash: {tx_hash} {unique_suffix}"
                    client.create_tweet(text=reply_text, in_reply_to_tweet_id=tweet_id)

                    logging.info(f"Processed tweet ID: {tweet_id}")
                except Exception as e:
                    # Handle errors and reply with the issue
                    unique_suffix = generate_unique_suffix()
                    error_text = f"There was an error processing your request: {e} {unique_suffix}"
                    client.create_tweet(text=error_text, in_reply_to_tweet_id=tweet_id)
            else:
                logging.info(f"Ignored tweet ID: {tweet_id}")

            # Mark the tweet as processed and save it
            processed_tweets.add(str(tweet_id))
            save_processed_tweet(tweet_id)

# Main loop to poll mentions periodically
def main():
    logging.info("Starting bot...")
    while True:
        try:
            process_mentions()
        except tweepy.TooManyRequests as e:
            logging.error(f"Rate limit exceeded. Sleeping for 15 minutes.")
            time.sleep(900)  # Wait 15 minutes
        except Exception as e:
            logging.error(f"Error: {e}")
        time.sleep(60)  # Poll every 60 seconds

if __name__ == "__main__":
    main()
