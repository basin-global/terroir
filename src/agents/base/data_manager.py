from typing import Dict, List, Optional
import asyncpg
import os
from dotenv import load_dotenv
import json
import time
import logging

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self):
        self.data_dir = "src/data"
        self.connection_string = os.getenv('DATABASE_URL')
        if not self.connection_string:
            raise ValueError("DATABASE_URL environment variable is not set")
        
        self.cache_dir = "src/data/cache"
        self.cache_file = os.path.join(self.cache_dir, "accounts_cache.json")
        self.cache_ttl = 86400  # 24 hours in seconds
        
        # Will be populated during initialization
        self.account_tables = []
        self.table_columns = {}
        self.accounts_cache = {}
        self.last_cache_update = 0

    async def initialize(self):
        """Initialize database schema and cache"""
        print("\nInitializing DataManager...")
        await self._load_schema()
        print(f"Loaded schema for {len(self.table_columns)} tables")
        print(f"Found {len(self.account_tables)} account tables")
        
        await self._refresh_cache()
        print(f"Cached {len(self.accounts_cache)} accounts")

    async def _load_schema(self):
        """Load database schema information"""
        try:
            conn = await asyncpg.connect(self.connection_string)
            try:
                # Get all tables and their columns
                schema_info = await conn.fetch("""
                    SELECT 
                        table_name,
                        array_agg(column_name::text) as columns
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    GROUP BY table_name
                """)
                
                for record in schema_info:
                    table_name = record['table_name']
                    self.table_columns[table_name] = record['columns']
                    
                # Get OG names and build account tables list
                ogs = await conn.fetch('SELECT og_name FROM situs_ogs')
                for og in ogs:
                    og_name = og['og_name'].replace('.', '')
                    self.account_tables.append(f"situs_accounts_{og_name}")
                        
            finally:
                await conn.close()
                
        except Exception as e:
            print(f"Error loading schema: {e}")
            self.table_columns = {}
            self.account_tables = []

    async def _refresh_cache(self):
        """Refresh accounts cache from database"""
        try:
            conn = await asyncpg.connect(self.connection_string)
            try:
                self.accounts_cache = {
                    "by_full_name": {},  # Store by "name.og"
                    "by_name": {}        # Store by just "name"
                }
                
                for table in self.account_tables:
                    # Get essential columns
                    select_cols = ['token_id']
                    optional_cols = ['account_name', 'tba_address', 'description']
                    columns = self.table_columns.get(table, [])
                    select_cols.extend([col for col in optional_cols if col in columns])
                    
                    # Get all accounts from this table
                    rows = await conn.fetch(f"""
                        SELECT {', '.join(select_cols)}
                        FROM {table}
                    """)
                    
                    # Store in both caches
                    og_type = table.replace('situs_accounts_', '')
                    for row in rows:
                        if 'account_name' in row:
                            account_name = row['account_name']
                            account_data = dict(row)
                            
                            # Store by full name (name.og)
                            full_name = f"{account_name}.{og_type}"
                            self.accounts_cache["by_full_name"][full_name] = account_data
                            
                            # Store by name only, grouping multiple OGs
                            if account_name not in self.accounts_cache["by_name"]:
                                self.accounts_cache["by_name"][account_name] = []
                            self.accounts_cache["by_name"][account_name].append({
                                "og": og_type,
                                **account_data
                            })
                
                # Save cache to disk
                os.makedirs(self.cache_dir, exist_ok=True)
                with open(self.cache_file, 'w') as f:
                    json.dump({
                        'timestamp': time.time(),
                        'accounts': self.accounts_cache
                    }, f, indent=2)
                    
                self.last_cache_update = time.time()
                
            finally:
                await conn.close()
                
        except Exception as e:
            print(f"Error refreshing cache: {e}")

    async def _check_cache(self):
        """Check if cache needs refresh"""
        # First check if cache file exists
        if not os.path.exists(self.cache_file):
            await self._refresh_cache()
            return
            
        # Load existing cache
        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
                self.accounts_cache = cache_data['accounts']
                self.last_cache_update = cache_data['timestamp']
        except Exception as e:
            print(f"\nError loading cache: {e}")
            await self._refresh_cache()

    async def get_account_details(self, full_name: str) -> Optional[Dict]:
        """Get account details from cache or database"""
        await self._check_cache()
        return self.accounts_cache.get(full_name)

    async def get_relevant(self, query: str) -> str:
        """Get relevant data from database based on query"""
        logger.info(f"Getting relevant data for query: {query}")
        
        # Check if query is about a wallet/TBA
        if any(word in query.lower() for word in ['wallet', 'tba', 'address']):
            # First check cache
            await self._check_cache()
            
            # Extract potential account name (e.g., "elk.basin" from query)
            words = query.lower().split()
            for word in words:
                # Check full name (e.g., "elk.basin")
                if word in self.accounts_cache["by_full_name"]:
                    account = self.accounts_cache["by_full_name"][word]
                    return f"Account {word} has TBA address {account.get('tba_address')}"
                
                # Check name without OG (e.g., "elk")
                if word in self.accounts_cache["by_name"]:
                    accounts = self.accounts_cache["by_name"][word]
                    # Return all matching accounts
                    responses = []
                    for acc in accounts:
                        og = acc["og"]
                        full_name = f"{word}.{og}"
                        tba = acc.get("tba_address")
                        if tba:
                            responses.append(f"{full_name} has TBA address {tba}")
                    if responses:
                        return "\n".join(responses)
            
            logger.info("No matching account found in cache")
            
        return ""