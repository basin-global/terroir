from neynar.api import NeynarAPIClient
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict

class FarcasterHandler:
    def __init__(self, api_key: str):
        self.client = NeynarAPIClient(api_key=api_key)
        self.fid = "885400"  # Terroir Terminal FID
        
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
        signature = f"\n\n- via {agent_name}"
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
                       reply_to: Optional[str] = None,
                       user_fid: Optional[str] = None) -> dict:
        """Post a cast with rate limiting"""
        if not await self.check_rate_limit(user_fid):
            return {
                "error": "Rate limit exceeded. Please try again later."
            }
            
        # Record the request
        now = datetime.now()
        self.request_history['global'].append(now)
        if user_fid:
            self.request_history[user_fid].append(now)
            
        formatted_content = await self.format_response(content, agent_name)
        
        if reply_to:
            return await self.client.post_cast(
                text=formatted_content,
                reply_to=reply_to
            )
        return await self.client.post_cast(text=formatted_content) 