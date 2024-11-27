from fastapi import FastAPI, WebSocket, Request
from src.config.settings import Settings
from src.agents.terroir_agent import TerroirAgent
import uvicorn
import os
import asyncio
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import hmac
import hashlib
import logging

app = FastAPI()
settings = Settings()
terroir = TerroirAgent(settings)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CodeChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            print("\nCode change detected. Restarting...")
            os.execv(sys.executable, ['python'] + sys.argv)

async def setup_watchdog():
    """Set up file watching in dev mode"""
    event_handler = CodeChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path='src', recursive=True)
    observer.start()
    return observer

async def interactive_loop(agent, observer=None):
    """CLI interface for local development"""
    print("\nTerroir Agent Interactive Mode")
    print("Type 'exit' to quit")
    print("--------------------------------")
    
    while True:
        try:
            user_input = input("\nWhat would you like to know about Terroir? > ").strip()
            
            if user_input.lower() in ['exit', 'quit']:
                if observer:
                    observer.stop()
                print("Shutting down Terroir Agent...")
                break
                
            if user_input:
                response = await agent.process_query(user_input)
                print(f"\nTerroir: {response}")
                
        except KeyboardInterrupt:
            if observer:
                observer.stop()
            print("\nShutting down Terroir Agent...")
            break

@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections"""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            response = await terroir.process_query(
                data["query"],
                source=data.get("source")
            )
            await websocket.send_json({"response": response})
    except Exception as e:
        print(f"WebSocket error: {e}")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "Terroir is running"}

@app.post("/api/farcaster/webhook")
async def farcaster_webhook(request: Request):
    """Handle incoming Farcaster events"""
    logger.info("Received webhook request")
    
    # Verify webhook signature
    signature = request.headers.get("x-neynar-signature")
    body = await request.body()
    
    if not verify_signature(body, signature, settings.NEYNAR_WEBHOOK_SECRET):
        logger.error(f"Invalid signature. Got: {signature}")
        logger.error(f"Headers: {request.headers}")
        return {"status": "error", "message": "Invalid signature"}, 401
        
    payload = await request.json()
    logger.info(f"Webhook payload: {payload}")
    
    # Initialize agent if needed
    if not hasattr(app, "agent_initialized"):
        await terroir.initialize()
        app.agent_initialized = True
        logger.info("Agent initialized")
    
    # Handle mentions and replies
    if payload["type"] in ["mention", "reply"]:
        logger.info(f"Processing mention/reply: {payload['cast']['text']}")
        try:
            response = await terroir.process_farcaster_query(
                query=payload["cast"]["text"],
                reply_to=payload["cast"]["hash"]
            )
            logger.info(f"Response sent: {response}")
        except Exception as e:
            logger.error(f"Error processing cast: {e}")
    
    return {"status": "success"}

def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Neynar webhook signature"""
    if not signature:
        return False
    
    computed = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed, signature)

if __name__ == "__main__":
    if "--dev" in sys.argv:
        # Run interactive mode with file watching
        settings = Settings()
        agent = TerroirAgent(settings)
        asyncio.run(agent.initialize())  # Initialize async components
        observer = asyncio.run(setup_watchdog())
        try:
            asyncio.run(interactive_loop(agent, observer))
        finally:
            observer.stop()
            observer.join()
    else:
        # Initialize agent before running API server
        asyncio.run(terroir.initialize())
        asyncio.run(terroir.farcaster.setup_signer())
        port = int(os.getenv("PORT", 8000))
        uvicorn.run(app, host="0.0.0.0", port=port) 