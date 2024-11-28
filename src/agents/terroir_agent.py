from langchain_anthropic import ChatAnthropic
from anthropic import Anthropic
from src.config.instructions import TERROIR_PURPOSE
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
        self._initialize_clients(config)
        
        # Initialize managers
        self.data_manager = DataManager()
        self.doc_manager = DocManager(config)
        self.memory_manager = MemoryManager()
        self.command_handler = CommandHandler()
        self.farcaster = FarcasterHandler(
            config.NEYNAR_API_KEY,
            signer_uuid=config.NEYNAR_SIGNER_UUID
        )

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
        # Process any commands first
        command_response = self.command_handler.process(query)
        logger.info(f"Command response: {command_response}")
        
        # If command_handler returns None, check if it's a cast command
        if command_response is None and ("cast:" in query.lower() or "cast+" in query.lower()):
            logger.info("Checking FarcasterHandler for cast command")
            cast_response = await self.farcaster.process_cast_command(query)
            if cast_response:
                logger.info(f"Cast command detected: {cast_response}")
                if cast_response["type"] == "cast":
                    if cast_response.get("raw"):
                        logger.info("Processing raw cast")
                        # Just post the raw message directly
                        await self.farcaster.post_cast(
                            content=cast_response["message"],
                            agent_name="terroir"
                        )
                        return cast_response["message"]
                    else:
                        return await self.process_farcaster_query(
                            query=cast_response["message"]
                        )
                elif cast_response["type"] == "scheduled_cast":
                    return f"Scheduled cast for {cast_response['hours']} hours from now: {cast_response['message']}"
        elif command_response:
            return command_response

        # Gather all available context
        context = []
        
        # Add verified facts and corrections from memory
        memory_context = self.memory_manager.get_context()
        if memory_context:
            context.append(memory_context)
            
        # Add live data if available
        data_context = await self.data_manager.get_relevant(query)
        if data_context:
            context.append(data_context)
            
        # Add relevant docs if available
        doc_context = self.doc_manager.get_relevant(query)
        if doc_context:
            context.append(doc_context)
        
        # Build system prompt that gives Claude more agency
        system_prompt = f"""{TERROIR_PURPOSE}

        Here is information that may be relevant to the query:
        {chr(10).join(context)}
        
        You can be direct or detailed as appropriate. Feel free to:
        - Focus on what's most relevant
        - Express uncertainty when needed
        - Ask clarifying questions
        - Correct misconceptions
        - Provide additional context when helpful"""

        # Get response from Claude
        message = await self.chat_model.ainvoke(
            system_prompt + "\n\nHuman: " + query
        )
        
        # Store interaction
        self.memory_manager.store(query, message.content)
        
        return message.content

    async def process_farcaster_query(self, query: str, reply_to: Optional[str] = None, raw: bool = False) -> str:
        """Process query and post response to Farcaster"""
        if raw:
            # Skip Claude processing, post exactly as written
            await self.farcaster.post_cast(
                content=query,
                agent_name="terroir",
                reply_to=reply_to
            )
            return query
            
        # Regular processing for non-raw casts...
        memory_context = self.memory_manager.get_context()
        farcaster_prompt = await self.farcaster.get_prompt(query, memory_context, reply_to)
        response = await self.process_query(query + "\n\n" + farcaster_prompt)
        await self.farcaster.post_cast(
            content=response,
            agent_name="terroir",
            reply_to=reply_to
        )
        return response
