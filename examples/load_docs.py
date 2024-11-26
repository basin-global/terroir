from src.agents.terroir_agent import TerroirAgent
from src.config.settings import Settings

def load_docs():
    config = Settings()
    agent = TerroirAgent(config)
    
    try:
        # Load documentation repos
        print("Loading documentation...")
        for repo in ["basin-global/situs-docs", "basin-global/BASIN-Field-Manual"]:
            agent.load_github_docs(repo)
            
        # Load protocol repo with Solidity files
        print("\nLoading protocol code...")
        agent.load_github_docs("basin-global/Situs-Protocol", include_code=True)
            
        print("\nAll documentation loaded successfully!")
        
        # Prepare context from loaded documents
        context = "\n\n".join([doc.page_content for doc in agent.documents])
        
        # Test the knowledge with Claude
        print("\nAsking Claude to analyze the documentation...")
        response = agent.anthropic_client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            system="You are Terroir, an AI that will help manage ensurance accounts. Only use information explicitly stated in the provided documentation.",
            messages=[{
                "role": "user",
                "content": f"""Here is the BASIN and Situs documentation:

{context}

Based only on this documentation, what are the key concepts and components that would be relevant for managing ensurance accounts? Please cite specific sections or concepts from the documentation."""
            }]
        )
        
        print("\nTerroir's Understanding:", response.content[0].text)
        
    except Exception as e:
        print(f"Error loading documentation: {str(e)}")

if __name__ == "__main__":
    load_docs() 