from src.config.settings import Settings
from src.agents.terroir_agent import TerroirAgent

async def update_docs():
    settings = Settings()
    agent = TerroirAgent(settings)
    await agent._load_protocol_docs()  # Refresh docs 