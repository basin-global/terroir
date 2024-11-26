from fastapi import FastAPI, WebSocket
from src.config.settings import Settings
from src.agents.terroir_agent import TerroirAgent
import uvicorn
import os
import asyncio
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time

app = FastAPI()

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
            user_input = input("\nWhat would you like to know about Terroir? > ")
            
            if user_input.lower() in ['exit', 'quit']:
                if observer:
                    observer.stop()
                print("Shutting down Terroir Agent...")
                break
                
            if user_input.strip():
                print(f"\nProcessing: {user_input}")
                response = await agent.process_query(user_input)
                print(f"\nTerroir: {response}")
                
        except KeyboardInterrupt:
            if observer:
                observer.stop()
            print("\nShutting down Terroir Agent...")
            break
        except Exception as e:
            print(f"Error: {e}")

@app.post("/api/query")
async def process_query(query: str):
    """Handle regular HTTP queries"""
    response = await terroir.process_query(query)
    return {"response": response}

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

if __name__ == "__main__":
    if "--dev" in sys.argv:
        # Run interactive mode with file watching
        settings = Settings()
        agent = TerroirAgent(settings)
        observer = asyncio.run(setup_watchdog())
        try:
            asyncio.run(interactive_loop(agent, observer))
        finally:
            observer.stop()
            observer.join()
    else:
        # Run API server
        port = int(os.getenv("PORT", 8000))
        uvicorn.run(app, host="0.0.0.0", port=port) 