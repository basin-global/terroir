import httpx
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict
import logging
import asyncio
import hmac
import hashlib
from fastapi import Request

# Set up logging
logger = logging.getLogger(__name__)

class FarcasterHandler:
    def __init__(self, api_key: str, signer_uuid: str = None, webhook_secret: str = None):
        self.api_key = api_key
        self.base_url = "https://api.neynar.com/v2"
        self.fid = "885400"  # @terroir FID
        self.signer_uuid = signer_uuid
        self.webhook_secret = webhook_secret  # Store webhook_secret
        
        # Rate limiting
        self.rate_limits = {
            'per_user': {
                'max_requests': 5,
                'window_seconds': 300  # 5 minutes
            },
            'global': {
                'max_requests': 50,
                'window_seconds': 3600  # 1 hour
            }
        }
        self.request_history = defaultdict(list)
        
    async def format_response(self, response: str, agent_name: str) -> str:
        """Format response with agent attribution for Farcaster"""
        max_length = 320
        signature = f"\n\n/s/ {agent_name}"
        content_limit = max_length - len(signature)
        
        if len(response) > content_limit:
            response = response[:content_limit-3] + "..."
            
        return response + signature
    
    async def check_rate_limit(self, user_fid: str = None) -> bool:
        """Check if request is within rate limits"""
        now = datetime.now()
        
        # Clean old requests
        self._clean_old_requests(now)
        
        # Check global limit
        global_requests = len(self.request_history['global'])
        if global_requests >= self.rate_limits['global']['max_requests']:
            return False
            
        # Check per-user limit if user_fid provided
        if user_fid:
            user_requests = len(self.request_history[user_fid])
            if user_requests >= self.rate_limits['per_user']['max_requests']:
                return False
                
        return True
        
    def _clean_old_requests(self, now: datetime):
        """Remove requests outside the time window"""
        for key in list(self.request_history.keys()):
            window = self.rate_limits['per_user' if key != 'global' else 'global']['window_seconds']
            cutoff = now - timedelta(seconds=window)
            self.request_history[key] = [
                t for t in self.request_history[key] if t > cutoff
            ]
    
    async def post_cast(self, content: str, agent_name: str, 
                       reply_to: Optional[str] = None) -> dict:
        """Post a cast using Neynar API"""
        formatted_content = await self.format_response(content, agent_name)
        
        headers = {
            "accept": "application/json",
            "api_key": self.api_key,
            "content-type": "application/json"
        }
        
        data = {
            "text": formatted_content,
            "signer_uuid": self.signer_uuid
        }
        
        if reply_to:
            # Remove '0x' prefix if present for Neynar API
            reply_to = reply_to.replace('0x', '')
            data["parent_hash"] = reply_to  # This makes it a reply
            logger.info(f"Replying to cast: {reply_to}")
        
        logger.info(f"Sending cast data: {data}")
            
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/farcaster/cast",
                headers=headers,
                json=data
            )
            logger.info(f"Cast response: {response.text}")
            return response.json()
    
    async def setup_signer(self):
        """Setup or verify signer for the Terroir account"""
        headers = {
            "accept": "application/json",
            "api_key": self.api_key,
            "content-type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            logger.info("Getting signer info...")
            # First try to get existing approved signer
            response = await client.get(
                f"{self.base_url}/farcaster/signer",
                headers=headers,
                params={"fid": int(self.fid), "status": "approved"}
            )
            signer_data = response.json()
            logger.info(f"Existing signer response: {signer_data}")
            
            if signer_data.get("signers"):
                for signer in signer_data["signers"]:
                    if signer["status"] == "approved":
                        self.signer_uuid = signer["signer_uuid"]
                        logger.info(f"Found approved signer: {self.signer_uuid}")
                        return self.signer_uuid
            
            # If no approved signer exists, create one
            logger.info("No approved signer found, creating new signer...")
            create_response = await client.post(
                f"{self.base_url}/farcaster/signer",
                headers=headers,
                json={
                    "fid": int(self.fid),
                    "custody_address": "0x848af6125f4bb94588103dfcea75c3fe28415657"
                }
            )
            create_data = create_response.json()
            logger.info(f"Create signer response: {create_data}")
            
            if create_data.get("signer_uuid"):
                self.signer_uuid = create_data["signer_uuid"]  # Set the signer_uuid even if not approved
                logger.info(f"New signer created with UUID: {self.signer_uuid}")
                logger.info("Please approve this signer in the Neynar dashboard")
                
                # Wait for potential approval
                await asyncio.sleep(2)
                
                # Check signer status
                status_response = await client.get(
                    f"{self.base_url}/farcaster/signer/{self.signer_uuid}",
                    headers=headers
                )
                status_data = status_response.json()
                logger.info(f"Signer status: {status_data}")
                
                return self.signer_uuid
                
            logger.error("Failed to get or create signer")
            return None
    
    async def handle_webhook_event(self, payload: dict) -> Optional[dict]:
        """Handle incoming Farcaster webhook events"""
        if payload.get("type") == "cast.created":
            cast_data = payload.get("data", {})
            
            should_respond = False
            parent_hash = None
            thread_context = None
            
            # Check for direct mentions
            mentioned_profiles = cast_data.get("mentioned_profiles", [])
            if any(profile.get("fid") == int(self.fid) for profile in mentioned_profiles):
                should_respond = True
                parent_hash = cast_data.get("hash")
                logger.info("Detected direct @terroir mention")
            
            # Check if this is a reply to our cast
            parent_author = cast_data.get("parent_author", {})
            if parent_author and str(parent_author.get("fid")) == self.fid:
                should_respond = True
                parent_hash = cast_data.get("hash")
                logger.info("Detected reply to our cast")
                
                # Get thread context if available
                thread_hash = cast_data.get("thread_hash")
                if thread_hash:
                    thread_context = await self.get_thread_context(thread_hash)
                    logger.info(f"Thread context: {thread_context}")
            
            if should_respond:
                logger.info(f"Will respond to cast: {cast_data.get('text')}")
                return {
                    "should_respond": True,
                    "parent_hash": parent_hash,
                    "text": cast_data.get("text"),
                    "thread_context": thread_context
                }
        
        return None
    
    async def get_thread_context(self, thread_hash: str) -> str:
        """Get previous messages in thread"""
        headers = {
            "accept": "application/json",
            "api_key": self.api_key
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/farcaster/cast/{thread_hash}",
                headers=headers
            )
            if response.status_code == 200:
                thread_data = response.json()
                # Extract relevant context
                return thread_data.get("text", "")
            return ""
    
    async def verify_webhook_signature(self, body: bytes, signature: str, secret: str) -> bool:
        """Verify Neynar webhook signature"""
        if not signature:
            return False
        
        logger.info("Verifying webhook signature...")
        try:
            computed = hmac.new(
                secret.encode('utf-8'),
                body,
                hashlib.sha512
            ).hexdigest()
            
            logger.info(f"Computed signature: {computed}")
            logger.info(f"Received signature: {signature}")
            
            return hmac.compare_digest(computed, signature)
        except Exception as e:
            logger.error(f"Error in signature verification: {e}")
            return False

    async def process_webhook(self, request: Request, agent) -> dict:
        """Process incoming webhook request"""
        # Verify signature
        signature = request.headers.get("x-neynar-signature")
        body = await request.body()
        
        if not await self.verify_webhook_signature(body, signature, self.webhook_secret):
            logger.error("Invalid webhook signature")
            return {"status": "error", "message": "Invalid signature"}
            
        payload = await request.json()
        logger.info(f"Webhook payload: {payload}")
        
        # Process the event
        event_data = await self.handle_webhook_event(payload)
        
        if event_data and event_data["should_respond"]:
            try:
                response = await agent.process_farcaster_query(
                    query=event_data["text"],
                    reply_to=event_data["parent_hash"]
                )
                logger.info(f"Response sent: {response}")
            except Exception as e:
                logger.error(f"Error processing cast: {e}")
                
        return {"status": "success"}
    
    async def process_cast_command(self, query: str) -> dict:
        """Process cast commands from CLI"""
        if "cast+raw:" in query.lower():
            # Extract message and send exactly as written
            message = query.split(":", 1)[1].strip()
            return {
                "type": "cast",
                "message": message,
                "raw": True  # Flag to skip Claude processing
            }
            
        elif "cast:" in query.lower():
            # Regular cast - will be processed by Claude
            message = query.split("cast:")[1].strip()
            return {
                "type": "cast",
                "message": message,
                "raw": False
            }
            
        # Scheduled cast handling stays the same...
        elif "cast+" in query.lower() and ":" in query.lower():
            try:
                command, message = query.split(":", 1)
                hours = int(command.replace("cast+", "").strip())
                
                return {
                    "type": "scheduled_cast",
                    "hours": hours,
                    "message": message.strip()
                }
            except Exception as e:
                return f"Error parsing scheduled cast: {e}"
                
        return None
    
    async def get_prompt(self, query: str, memory_context: str, reply_to: Optional[str] = None) -> str:
        """Get appropriate prompt based on cast type"""
        if reply_to:
            # This is a reply - be conversational
            return f"""
            Previous conversation:
            {memory_context}
            
            Provide a direct response suitable for Farcaster (max 320 chars).
            This is a reply to someone's question or comment.
            - Be conversational and engaging
            - Address their points directly
            - Encourage further discussion
            - Maintain context of the thread
            """
        else:
            # This is a new cast - be more declarative and match tone
            return """
            Provide a clear statement suitable for Farcaster (max 320 chars).
            This is a new cast, not a reply.
            
            Important:
            - Match the emotional tone of the input
            - If the input is passionate/urgent, reflect that energy
            - If the input is critical, be equally direct
            - If mentioning $ENSURE or BASIN, be enthusiastic
            - Use strong, impactful language when appropriate
            - Keep the focus on environmental and natural capital issues
            
            Style:
            - Make clear, declarative statements
            - Focus on facts and insights
            - Be bold and authentic
            - Don't use phrases like "let me explain" or "I can provide"
            """