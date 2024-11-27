from langchain.memory import ConversationBufferMemory
from datetime import datetime
import json
import os

class MemoryManager:
    def __init__(self):
        self.knowledge_file = "src/data/knowledge/learned_knowledge.json"
        self._initialize_memory()
        
    def _initialize_memory(self):
        """Initialize memory systems"""
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        self.learned_knowledge = self._load_learned_knowledge()
        
    def _load_learned_knowledge(self):
        """Load previously learned information"""
        try:
            with open(self.knowledge_file, 'r') as f:
                knowledge = json.load(f)
                # Ensure all required keys exist
                required_keys = {
                    "verified_facts": [],  # Keep nl: commands as verified facts
                    "corrections": [],     # Keep cor: commands as corrections
                    "interactions": []     # All other interactions
                }
                for key, default in required_keys.items():
                    if key not in knowledge:
                        knowledge[key] = default
                return knowledge
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Issue loading knowledge file: {e}")
            return {
                "verified_facts": [],
                "corrections": [],
                "interactions": []
            }
            
    def _save_knowledge(self):
        """Save knowledge to disk"""
        os.makedirs(os.path.dirname(self.knowledge_file), exist_ok=True)
        with open(self.knowledge_file, 'w') as f:
            json.dump(self.learned_knowledge, f, indent=2)
        
    def store(self, query: str, response: str, source: dict = None):
        """Store interaction in memory"""
        # Always store in conversation memory
        self.memory.save_context({"input": query}, {"output": response})
        
        # Process nl: and cor: commands
        if query.lower().startswith("nl:"):
            self.learned_knowledge["verified_facts"].append({
                "fact": query.split("nl:")[1].strip(),
                "added_by": source or "local",
                "timestamp": datetime.now().isoformat()
            })
            self._save_knowledge()
            return
            
        if query.lower().startswith("cor:"):
            self.learned_knowledge["corrections"].append({
                "correction": query.split("cor:")[1].strip(),
                "added_by": source or "local",
                "timestamp": datetime.now().isoformat()
            })
            self._save_knowledge()
            return
            
        # Store all other interactions
        self.learned_knowledge["interactions"].append({
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "response": response,
            "source": source or "local"
        })
        self._save_knowledge()
        
    def get_context(self):
        """Get conversation context including verified facts and corrections"""
        context = []
        
        # Add verified facts
        if self.learned_knowledge["verified_facts"]:
            context.append("Verified Facts:")
            for fact in self.learned_knowledge["verified_facts"]:
                context.append(f"- {fact['fact']}")
            context.append("")
            
        # Add corrections
        if self.learned_knowledge["corrections"]:
            context.append("Important Corrections:")
            for correction in self.learned_knowledge["corrections"]:
                context.append(f"- {correction['correction']}")
            context.append("")
            
        # Add conversation history
        chat_history = self.memory.load_memory_variables({}).get('chat_history', '')
        if chat_history:
            context.append("Recent Conversation:")
            # Make sure chat_history is a string before adding
            if isinstance(chat_history, list):
                context.append("\n".join(str(msg) for msg in chat_history))
            else:
                context.append(str(chat_history))
            
        return "\n".join(str(item) for item in context)
        