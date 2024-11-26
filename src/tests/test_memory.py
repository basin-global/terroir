import asyncio
from src.agents.terroir_agent import TerroirAgent
from src.config.settings import Settings

async def test_memory_systems():
    print("\nTesting Terroir Memory Systems...")
    
    settings = Settings()
    agent = TerroirAgent(settings)
    
    # Test 1: Conversation Context
    print("\nTest 1: Conversation Context")
    
    # First query
    print("\nFirst Query: 'What is a .basin account?'")
    response1 = await agent.process_query("What is a .basin account?")
    print(f"Response 1: {response1[:200]}...")
    
    # Second query referencing first
    print("\nSecond Query: 'Can you give me an example of one?'")
    response2 = await agent.process_query("Can you give me an example of one?")
    print(f"Response 2: {response2[:200]}...")
    
    # Test 2: Learning System
    print("\nTest 2: Learning System")
    
    # Add new information using shorter command
    learning_query = "nl: elk.basin was the first .basin account created"
    print(f"\nAdding new information: {learning_query}")
    response3 = await agent.process_query(learning_query)
    print(f"Response 3: {response3[:200]}...")
    
    # Make a correction using shorter command
    correction_query = "cor: elk.basin spans from Aspen to Glenwood Springs"
    print(f"\nMaking correction: {correction_query}")
    response4 = await agent.process_query(correction_query)
    print(f"Response 4: {response4[:200]}...")
    
    # Test 3: Todo System
    print("\nTest 3: Todo System")
    
    # Add todos
    print("\nAdding todos...")
    await agent.process_query("todo: Update elk.basin description")
    await agent.process_query("todo: Add winter range information")
    
    # Show todos
    print("\nShowing todo list:")
    todos_response = await agent.process_query("show todos")
    print(todos_response)
    
    # Mark one as done
    print("\nMarking first todo as done...")
    done_response = await agent.process_query("done: 1")
    print(done_response)
    
    # Show updated list
    print("\nUpdated todo list:")
    todos_response = await agent.process_query("show todos")
    print(todos_response)
    
    # Test 4: Examine Learned Knowledge
    print("\nTest 4: Examining Learned Knowledge")
    print("\nVerified Facts:")
    for fact in agent.learned_knowledge["verified_facts"]:
        print(f"- {fact}")
    
    print("\nCorrections:")
    for correction in agent.learned_knowledge["corrections"]:
        print(f"- {correction}")
    
    # Test 5: Memory Persistence
    print("\nTest 5: Memory Persistence")
    print(f"Checking learned_knowledge file: {agent.knowledge_file}")
    try:
        with open(agent.knowledge_file, 'r') as f:
            print("✓ learned_knowledge.json exists and is readable")
    except FileNotFoundError:
        print("❌ learned_knowledge.json not found")
        
    print(f"\nChecking todo file: {agent.todo_file}")
    try:
        with open(agent.todo_file, 'r') as f:
            print("✓ todo_list.json exists and is readable")
    except FileNotFoundError:
        print("❌ todo_list.json not found")

if __name__ == "__main__":
    asyncio.run(test_memory_systems()) 