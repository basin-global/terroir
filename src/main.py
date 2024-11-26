import asyncio
from src.config.settings import Settings
from src.agents.terroir_agent import TerroirAgent
import watchdog.observers
import watchdog.events
import sys
import os

class CodeChangeHandler(watchdog.events.FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            print("\nCode change detected. Restarting agent...")
            python = sys.executable
            os.execl(python, python, *sys.argv)

async def interactive_loop(agent):
    print("\nTerroir Agent Interactive Mode")
    print("Type 'exit' to quit")
    print("--------------------------------")
    
    while True:
        try:
            user_input = input("\nWhat would you like to know about Terroir? > ")
            
            if user_input.lower() in ['exit', 'quit']:
                print("Shutting down Terroir Agent...")
                break
                
            if user_input.strip():
                print(f"\nProcessing: {user_input}")
                response = await agent.process_query(user_input)
                print(f"\nTerroir: {response}")
                
        except KeyboardInterrupt:
            print("\nShutting down Terroir Agent...")
            break
        except Exception as e:
            print(f"Error: {e}")

async def main():
    # Set up file watcher in development
    if "--dev" in sys.argv:
        observer = watchdog.observers.Observer()
        observer.schedule(CodeChangeHandler(), path='src', recursive=True)
        observer.start()
        print("Development mode: watching for code changes...")
    
    settings = Settings()
    agent = TerroirAgent(settings)
    await interactive_loop(agent)
    
if __name__ == "__main__":
    asyncio.run(main()) 