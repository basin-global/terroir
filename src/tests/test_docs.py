import asyncio
from src.agents.terroir_agent import TerroirAgent
from src.config.settings import Settings

async def test_doc_loading():
    print("\nTesting Documentation Loading...")
    
    # Initialize agent
    settings = Settings()
    agent = TerroirAgent(settings)
    
    # Test 1: Check if documents were loaded
    print(f"\nTest 1: Document Loading")
    print(f"Total documents loaded: {len(agent.documents)}")
    
    if agent.documents:
        print("\nSample document previews:")
        for i, doc in enumerate(agent.documents[:3]):  # Show first 3 docs
            print(f"\nDocument {i+1}:")
            print(f"Source: {doc.metadata.get('source', 'unknown')}")
            print(f"Preview: {doc.page_content[:200]}...")
    else:
        print("❌ No documents were loaded")
    
    # Test 2: Test document relevance
    print("\nTest 2: Testing Document Relevance")
    test_queries = [
        "What is a Certificate of Ensurance?",
        "How do situs accounts work?",
        "Tell me about the BASIN protocol"
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        relevant_docs = agent._get_relevant_docs(query, num_docs=2)
        print("\nRelevant document chunks:")
        print(relevant_docs[:500] + "...\n")
        
    # Test 3: Test full query processing
    print("\nTest 3: Testing Full Query Processing")
    test_query = "What is the purpose of a .basin account?"
    print(f"\nQuery: {test_query}")
    response = await agent.process_query(test_query)
    print("\nResponse:")
    print(response)

if __name__ == "__main__":
    asyncio.run(test_doc_loading()) 