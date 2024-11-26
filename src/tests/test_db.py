import asyncio
from src.data.sql_reader import SQLReader

async def test_database_connection():
    print("\nTesting Database Connection...")
    sql_reader = SQLReader()
    
    # Test: Get elk.basin TBA
    print("\nGetting TBA for 'elk.basin'...")
    account = await sql_reader.get_account_details("elk.basin")
    if account:
        print(f"✓ Found account: {account['full_name']}")
        print(f"TBA Address: {account['tba_address']}")
        print(f"Token ID: {account['token_id']}")
    else:
        print("✗ Account not found")

if __name__ == "__main__":
    asyncio.run(test_database_connection()) 