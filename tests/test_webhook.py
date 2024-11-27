import asyncio
import json
import hmac
import hashlib
from httpx import AsyncClient
from src.config.settings import Settings
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_server():
    """Check if the server is running"""
    try:
        async with AsyncClient() as client:
            # Add timeout to avoid hanging
            response = await client.get("http://localhost:8000/", timeout=5.0)
            logger.info(f"Server check response: {response.status_code}")
            return True  # If we can connect at all, consider server running
    except Exception as e:
        logger.error(f"Server check error: {e}")
        return False

async def test_webhook():
    logger.info("Starting webhook test")
    
    # Wait a bit for server to be ready
    await asyncio.sleep(2)
    
    # Check if server is running
    server_running = await check_server()
    if not server_running:
        logger.error("Server is not running! Please start the server first with: python -m src.api.main --dev")
        return
    
    logger.info("Server is running, proceeding with test")
    
    settings = Settings()
    logger.info("Settings loaded")
    
    # Your webhook payload
    payload = {
        "type": "mention",
        "cast": {
            "text": "@terroir what is wine?",
            "hash": "0x123",
            "mentions": ["885400"]
        }
    }
    
    logger.info(f"Using payload: {payload}")
    
    # Calculate signature using your actual webhook secret
    payload_bytes = json.dumps(payload).encode()
    signature = hmac.new(
        settings.NEYNAR_WEBHOOK_SECRET.encode(),
        payload_bytes,
        hashlib.sha512
    ).hexdigest()
    
    logger.info("Signature calculated")
    
    try:
        async with AsyncClient() as client:
            logger.info("Sending request to localhost:8000")
            response = await client.post(
                "http://localhost:8000/api/farcaster/webhook",
                json=payload,
                headers={
                    "x-neynar-signature": signature,
                    "Content-Type": "application/json"
                }
            )
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response content: {response.json()}")
    except Exception as e:
        logger.error(f"Error during request: {e}")

if __name__ == "__main__":
    asyncio.run(test_webhook()) 