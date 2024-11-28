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
from datetime import datetime, timedelta

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
    print("Type '/cast your message' to post to Farcaster")
    print("Type '/cast+N your message' to schedule a cast in N hours")
    print("--------------------------------")
    
    scheduled_casts = []  # Store scheduled casts
    
    while True:
        try:
            user_input = input("\nWhat would you like to know about Terroir? > ").strip()
            
            if user_input.lower() in ['exit', 'quit']:
                if observer:
                    observer.stop()
                print("Shutting down Terroir Agent...")
                break
            
            if user_input.startswith('/cast+'):
                # Parse schedule time
                try:
                    parts = user_input.split(' ', 1)
                    hours = int(parts[0].replace('/cast+', ''))
                    message = parts[1].strip()
                    
                    # Calculate scheduled time
                    schedule_time = datetime.now() + timedelta(hours=hours)
                    
                    # Store scheduled cast
                    scheduled_casts.append({
                        'time': schedule_time,
                        'message': message
                    })
                    print(f"\nScheduled cast for {schedule_time}: {message}")
                    
                except Exception as e:
                    print(f"\nError scheduling cast: {e}")
                    
            elif user_input.startswith('/cast '):
                # Extract message after /cast command
                message = user_input[6:].strip()
                response = await agent.process_farcaster_query(message)
                print(f"\nPosted to Farcaster: {response}")
            elif user_input:
                response = await agent.process_query(user_input)
                print(f"\nTerroir: {response}")
            
            # Check and execute scheduled casts
            now = datetime.now()
            pending_casts = []
            for cast in scheduled_casts:
                if now >= cast['time']:
                    print(f"\nExecuting scheduled cast: {cast['message']}")
                    try:
                        response = await agent.process_farcaster_query(cast['message'])
                        print(f"Posted scheduled cast: {response}")
                    except Exception as e:
                        print(f"Error posting scheduled cast: {e}")
                else:
                    pending_casts.append(cast)
            scheduled_casts = pending_casts
                
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
    
    # Verify signature
    signature = request.headers.get("x-neynar-signature")
    body = await request.body()
    verify_signature(body, signature, settings.NEYNAR_WEBHOOK_SECRET)
    
    payload = await request.json()
    logger.info(f"Webhook payload: {payload}")
    
    # Initialize agent if needed
    if not hasattr(app, "agent_initialized"):
        await terroir.initialize()
        app.agent_initialized = True
        logger.info("Agent initialized")
    
    if payload.get("type") == "cast.created":
        cast_data = payload.get("data", {})
        
        should_respond = False
        
        # Check for direct mentions
        mentioned_profiles = cast_data.get("mentioned_profiles", [])
        if any(profile.get("fid") == 885400 for profile in mentioned_profiles):
            should_respond = True
            
        # Check if this is a reply to one of our casts
        parent_author = cast_data.get("parent_author", {})
        if parent_author.get("fid") == 885400:  # If parent cast is from @terroir
            should_respond = True
            
        if should_respond:
            logger.info(f"Processing cast: {cast_data.get('text')}")
            try:
                response = await terroir.process_farcaster_query(
                    query=cast_data.get("text"),
                    reply_to=cast_data.get("hash")
                )
                logger.info(f"Response sent: {response}")
            except Exception as e:
                logger.error(f"Error processing cast: {e}")
    
    return {"status": "success"}

def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Neynar webhook signature"""
    if not signature:
        return False
    
    logger.info(f"Verifying signature...")
    
    try:
        # The secret is already in the correct format
        computed = hmac.new(
            secret.encode('utf-8'),  # Use the secret as-is
            payload,
            hashlib.sha512
        ).hexdigest()
        
        logger.info(f"Computed signature: {computed}")
        logger.info(f"Received signature: {signature}")
        
        return hmac.compare_digest(computed, signature)
    except Exception as e:
        logger.error(f"Error in signature verification: {e}")
        return False

if __name__ == "__main__":
    if "--dev" in sys.argv:
        # Run both interactive mode and API server
        settings = Settings()
        agent = TerroirAgent(settings)
        
        async def run_server():
            # Use uvicorn programmatically but with proper config
            config = uvicorn.Config(
                app=app,
                host="0.0.0.0",
                port=8000,
                log_level="info",
                reload=False  # Important: we handle reload ourselves
            )
            server = uvicorn.Server(config)
            await server.serve()
            
        async def run_all():
            # Initialize agent
            await agent.initialize()
            
            # Start API server in background and wait a moment
            server_task = asyncio.create_task(run_server())
            await asyncio.sleep(2)  # Give server time to start
            
            # Set up watchdog
            observer = await setup_watchdog()
            
            try:
                await interactive_loop(agent, observer)
            finally:
                observer.stop()
                observer.join()
                server_task.cancel()
                
        # Run everything
        asyncio.run(run_all())
    else:
        # Run API server only
        port = int(os.getenv("PORT", 8000))
        uvicorn.run(app, host="0.0.0.0", port=port) 