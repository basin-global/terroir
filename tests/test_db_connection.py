import asyncio
import os
from dotenv import load_dotenv
import asyncpg

async def test_db_connection():
    """Test database connection and table access"""
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')
    
    if not connection_string:
        print("Error: DATABASE_URL environment variable is not set")
        return
        
    try:
        conn = await asyncpg.connect(connection_string)
        try:
            # Test basic connection
            version = await conn.fetchval('SELECT version()')
            print(f"\nConnected to PostgreSQL: {version}")
            
            # Get columns from situs_ogs
            og_columns = await conn.fetch("""
                SELECT column_name, data_type 
                FROM information_schema.columns
                WHERE table_name = 'situs_ogs'
                ORDER BY ordinal_position;
            """)
            print("\nSitus OGs Table Structure:")
            for col in og_columns:
                print(f"- {col['column_name']}: {col['data_type']}")
            
            # Get actual OGs
            print("\nAvailable OGs and Account Tables:")
            ogs = await conn.fetch('SELECT og_name FROM situs_ogs')
            for og in ogs:
                # Remove any dots from OG name
                og_name = og['og_name'].replace('.', '')
                table = f"situs_accounts_{og_name}"
                
                # Get columns for this account table
                account_columns = await conn.fetch("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns
                    WHERE table_name = $1
                    ORDER BY ordinal_position;
                """, table)
                
                count = await conn.fetchval(f'SELECT COUNT(*) FROM {table}')
                print(f"\n{table}: {count} accounts")
                print("Columns:")
                for col in account_columns:
                    print(f"- {col['column_name']}: {col['data_type']}")
                
        finally:
            await conn.close()
            
    except Exception as e:
        print(f"\nDatabase connection error: {e}")

if __name__ == "__main__":
    asyncio.run(test_db_connection()) 