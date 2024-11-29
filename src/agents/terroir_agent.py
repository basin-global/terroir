from langchain_anthropic import ChatAnthropic
from anthropic import Anthropic
from src.config.personalities import TERROIR_PERSONALITY
from src.agents.base.data_manager import DataManager
from src.agents.base.doc_manager import DocManager
from src.agents.base.memory_manager import MemoryManager
from src.agents.base.command_handler import CommandHandler
from src.agents.base.farcaster_handler import FarcasterHandler
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class TerroirAgent:
    def __init__(self, config):
        self.config = config
        self.personality = TERROIR_PERSONALITY
        self._initialize_clients(config)
        
        # Initialize managers
        self.data_manager = DataManager()
        self.doc_manager = DocManager(config)
        self.memory_manager = MemoryManager()
        self.command_handler = CommandHandler()
        self.farcaster = FarcasterHandler(
            api_key=config.NEYNAR_API_KEY,
            signer_uuid=config.NEYNAR_SIGNER_UUID,
            webhook_secret=config.NEYNAR_WEBHOOK_SECRET
        )
        
        # Add memory management
        self.max_prompt_size = 2000  # Characters

    async def initialize(self):
        """Initialize async components"""
        await self.data_manager.initialize()

    def _initialize_clients(self, config):
        """Initialize Claude client"""
        self.anthropic_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.chat_model = ChatAnthropic(
            anthropic_api_key=config.ANTHROPIC_API_KEY,
            model_name="claude-3-sonnet-20240229"
        )

    async def process_query(self, query: str) -> str:
        # Process commands first
        command_response = self.command_handler.process(query)
        if command_response:
            return command_response

        # Gather context from all sources
        context = await self._gather_context(query)
        
        # Build system prompt
        system_prompt = self._build_system_prompt(context)
        
        # Get response from Claude
        message = await self.chat_model.ainvoke(
            system_prompt + "\n\nHuman: " + query
        )
        
        # Store interaction
        self.memory_manager.store(query, message.content)
        
        return message.content

    async def _gather_context(self, query: str) -> dict:
        """Gather relevant context from all available sources"""
        return {
            "docs": self.doc_manager.get_relevant(query),
            "data": await self.data_manager.get_relevant(query),
            "memory": self.memory_manager.get_context()
        }

    def _build_system_prompt(self, context: dict) -> str:
        """Build complete system prompt with personality and context"""
        prompt = f"""{self.personality['purpose']}

        {self.personality['tone']}

        Style Guidelines:
        {chr(10).join(f"- {rule}" for rule in self.personality['style'])}

        Critical Rules:
        {chr(10).join(f"- {rule}" for rule in self.personality['hard_rules'])}

        Available Information:
        - Documentation: {context['docs'] if context['docs'] else 'No relevant documentation found'}
        - Live Data: {context['data'] if context['data'] else 'No relevant data found'}
        - Context & History: {context['memory'] if context['memory'] else 'No relevant previous interactions'}
        """
        return prompt

    async def process_farcaster_query(self, query: str, reply_to: Optional[str] = None, raw: bool = False) -> str:
        """Process query and post response to Farcaster"""
        if raw:
            await self.farcaster.post_cast(
                content=query,
                agent_name="terroir",
                reply_to=reply_to
            )
            return query
            
        # Let FarcasterHandler handle the prompt preparation
        farcaster_prompt = await self.farcaster.prepare_query_prompt(
            query=query,
            memory_context=self.memory_manager.get_context(),
            reply_to=reply_to
        )
        
        # Process with Claude
        response = await self.process_query(farcaster_prompt)
        
        # Post response
        await self.farcaster.post_cast(
            content=response,
            agent_name="terroir",
            reply_to=reply_to
        )
        return response
