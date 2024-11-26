from typing import Dict, List, Optional
import asyncpg
import os
from dotenv import load_dotenv
import datetime

class SQLReader:
    def __init__(self):
        load_dotenv()
        self.connection_string = os.getenv('DATABASE_URL')
        if not self.connection_string:
            raise ValueError("DATABASE_URL environment variable is not set")
        
        self.account_tables = [
            'situs_accounts_basin', 'situs_accounts_bioregion', 
            'situs_accounts_bloom', 'situs_accounts_boulder',
            'situs_accounts_earth', 'situs_accounts_ebf',
            'situs_accounts_kokonut', 'situs_accounts_mumbai',
            'situs_accounts_ogallala', 'situs_accounts_refi',
            'situs_accounts_regen', 'situs_accounts_sicilia',
            'situs_accounts_situs', 'situs_accounts_tokyo'
        ]
        
        self.ensurance_tables = [
            'ensurance', 'ensurance_arbitrum', 'ensurance_base',
            'ensurance_optimism', 'ensurance_zora'
        ]
    
    def _serialize_datetime(self, obj):
        """Convert datetime objects to ISO format strings"""
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return obj
    
    async def get_account_details(self, full_name: str) -> Optional[Dict]:
        """Get account details from full name (e.g. 'elk.basin')"""
        if '.' not in full_name:
            return None
            
        name_part, og_part = full_name.split('.')
        table_name = f"situs_accounts_{og_part}"
        
        if table_name not in self.account_tables:
            return None
            
        conn = await asyncpg.connect(self.connection_string)
        try:
            result = await conn.fetchrow(f"""
                SELECT 
                    token_id,
                    account_name,
                    created_at,
                    tba_address,
                    updated_at,
                    description
                FROM {table_name}
                WHERE account_name = $1
            """, name_part)
            
            if result:
                account_data = dict(result)
                # Serialize datetime objects
                for key, value in account_data.items():
                    account_data[key] = self._serialize_datetime(value)
                
                account_data['full_name'] = f"{account_data['account_name']}.{og_part}"
                account_data['account_type'] = og_part
                
                # Get ensurance data
                ensurance_data = await self._get_ensurance_data(conn, token_id=account_data['token_id'])
                if ensurance_data:
                    account_data['ensurance'] = ensurance_data
                
                return account_data
            
            return None
            
        finally:
            await conn.close()

    async def _get_ensurance_data(self, conn, token_id: int) -> List[Dict]:
        """Get ensurance data across all networks"""
        all_ensurance = []
        
        for table in self.ensurance_tables:
            if table == 'ensurance':
                # Main ensurance table has different structure
                results = await conn.fetch("""
                    SELECT contract_address, chain, updated_at
                    FROM ensurance
                """)
            else:
                # Network-specific ensurance tables
                results = await conn.fetch(f"""
                    SELECT 
                        token_id, name, description, 
                        image_url, video_url, audio_url,
                        creator_reward_recipient,
                        creator_reward_recipient_split,
                        token_count, updated_at,
                        uri_ipfs, image_ipfs,
                        animation_url_ipfs, mime_type
                    FROM {table}
                    WHERE token_id = $1
                """, token_id)
            
            for row in results:
                data = dict(row)
                data['network'] = table.replace('ensurance_', '') if '_' in table else 'mainnet'
                all_ensurance.append(data)
                
        return all_ensurance

    async def get_all_accounts(self, account_type: Optional[str] = None) -> List[Dict]:
        """Get all accounts, optionally filtered by type"""
        conn = await asyncpg.connect(self.connection_string)
        try:
            all_accounts = []
            tables = [f"situs_accounts_{account_type}"] if account_type else self.account_tables
            
            for table in tables:
                results = await conn.fetch(f"""
                    SELECT 
                        token_id, account_name, created_at,
                        tba_address, description
                    FROM {table}
                    ORDER BY created_at DESC
                """)
                
                for row in results:
                    account = dict(row)
                    account['account_type'] = table.replace('situs_accounts_', '')
                    all_accounts.append(account)
                    
            return all_accounts
            
        finally:
            await conn.close()

    async def get_recent_activity(self, limit: int = 10) -> List[Dict]:
        """Get recent account activity across all types"""
        conn = await asyncpg.connect(self.connection_string)
        try:
            recent_activity = []
            
            for table in self.account_tables:
                results = await conn.fetch(f"""
                    SELECT 
                        token_id, account_name, created_at,
                        tba_address, updated_at,
                        description
                    FROM {table}
                    ORDER BY updated_at DESC
                    LIMIT $1
                """, limit)
                
                for row in results:
                    activity = dict(row)
                    activity['account_type'] = table.replace('situs_accounts_', '')
                    recent_activity.append(activity)
            
            # Sort all activities by updated_at
            recent_activity.sort(key=lambda x: x['updated_at'], reverse=True)
            return recent_activity[:limit]
            
        finally:
            await conn.close()

    async def get_table_structure(self, table_name: str) -> List[Dict]:
        """Utility method to inspect table columns"""
        conn = await asyncpg.connect(self.connection_string)
        try:
            columns = await conn.fetch("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = $1
            """, table_name)
            return [dict(col) for col in columns]
        finally:
            await conn.close()