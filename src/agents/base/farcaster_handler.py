import httpx
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict
import logging
import asyncio

# Set up logging
logger = logging.getLogger(__name__)

class FarcasterHandler:
    def __init__(self, api_key: str, signer_uuid: str = None):
        self.api_key = api_key
        self.base_url = "https://api.neynar.com/v2"
        self.fid = "885400"  # @terroir FID
        self.signer_uuid = signer_uuid  # Use provided signer_uuid
        
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