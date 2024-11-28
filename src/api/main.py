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
    print("Type 'cast: your message' to post to Farcaster")
    print("Type 'cast+N: your message' to schedule a cast in N hours")
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
                
            # Let command handler process all commands including casts
            if user_input:
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
    """Forward webhook to FarcasterHandler"""
    return await terroir.farcaster.process_webhook(request, terroir)

if __name__ == "__main__":
    if "--dev" in sys.argv:
        # Run both interactive mode and API server
        settings = Settings()
        agent = TerroirAgent(settings)
        
        async def run_server():
            # Try different ports if 8000 is taken
            for port in range(8000, 8010):
                try:
                    config = uvicorn.Config(
                        app=app,
                        host="0.0.0.0",
                        port=port,
                        log_level="info",
                        reload=False
                    )
                    server = uvicorn.Server(config)
                    logger.info(f"Starting server on port {port}")
                    await server.serve()
                    break
                except OSError:
                    logger.info(f"Port {port} in use, trying next port")
                    continue
            
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