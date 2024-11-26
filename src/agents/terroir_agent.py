from langchain_anthropic import ChatAnthropic
from langchain_community.document_loaders.github import GithubFileLoader
from anthropic import Anthropic
from .instructions import TERROIR_PURPOSE, ACCOUNT_TYPES
from langchain.memory import ConversationBufferMemory
from src.data.sql_reader import SQLReader
import json
from datetime import datetime
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
import asyncpg
from typing import Dict

class TerroirAgent:
    """Terroir Agent - AI system for managing situs accounts and natural capital"""
    def __init__(self, config):
        self.knowledge_file = "/Users/tmo/cursor/terroir/data/learned_knowledge.json"
        self.todo_file = "/Users/tmo/cursor/terroir/data/todo_list.json"
        self.faq_file = "/Users/tmo/cursor/terroir/data/faq_responses.json"
        self._initialize_clients(config)
        self._initialize_memory()
        self._initialize_knowledge_base()
        self._initialize_todos()
        self._initialize_faq()
        self.sql_reader = SQLReader()
        
        # Terroir-specific initialization
        self.purpose = TERROIR_PURPOSE
        self.account_types = ACCOUNT_TYPES
        self._load_protocol_docs()
        
        # Add authorized users with both FID and addresses
        self.authorized_learners = {
            "farcaster": {
                "fid": "215322",
                "custody": "0x7cba2d1f540fb606e20fe9ae6ad44aad09e8c420",
                "verified": []  # Add verified addresses here
            }
        }

    def _initialize_clients(self, config):
        """Initialize Claude client"""
        self.config = config
        self.anthropic_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.chat_model = ChatAnthropic(
            anthropic_api_key=config.ANTHROPIC_API_KEY,
            model_name="claude-3-sonnet-20240229"
        )

    def _initialize_memory(self):
        """Set up conversation memory"""
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )

    def _initialize_knowledge_base(self):
        """Set up knowledge storage"""
        self.documents = []
        self.learned_knowledge = self._load_learned_knowledge()

    def _initialize_todos(self):
        """Initialize todo list"""
        try:
            with open(self.todo_file, 'r') as f:
                self.todos = json.load(f)
        except FileNotFoundError:
            self.todos = {
                "active": [],
                "completed": [],
                "cleared": []
            }
            self._save_todos()

    def _save_todos(self):
        """Save todos to disk"""
        os.makedirs(os.path.dirname(self.todo_file), exist_ok=True)
        with open(self.todo_file, 'w') as f:
            json.dump(self.todos, f, indent=2)

    def _process_todo(self, query: str, response: str, source: dict = None):
        """Process todo commands"""
        if "todo:" in query.lower():
            todo_item = query.split("todo:")[1].strip()
            self.todos["active"].append({
                "item": todo_item,
                "created_at": datetime.now().isoformat(),
                "source": source or "local"
            })
            self._save_todos()
            return f"Added to todo list: {todo_item}"
            
        elif "done:" in query.lower():
            item_id = query.split("done:")[1].strip()
            try:
                item_index = int(item_id) - 1
                if 0 <= item_index < len(self.todos["active"]):
                    completed_item = self.todos["active"].pop(item_index)
                    completed_item["completed_at"] = datetime.now().isoformat()
                    self.todos["completed"].append(completed_item)
                    self._save_todos()
                    return f"Marked as done: {completed_item['item']}"
            except ValueError:
                pass

        elif "clear:" in query.lower():
            item_id = query.split("clear:")[1].strip()
            try:
                item_index = int(item_id) - 1
                if 0 <= item_index < len(self.todos["active"]):
                    cleared_item = self.todos["active"].pop(item_index)
                    cleared_item["cleared_at"] = datetime.now().isoformat()
                    self.todos["cleared"].append(cleared_item)
                    self._save_todos()
                    return f"Cleared: {cleared_item['item']}"
            except ValueError:
                pass
                
        elif query.lower() == "show todos":
            if not self.todos["active"]:
                return "No active todos."
            
            todo_list = "Active Todos:\n"
            for i, todo in enumerate(self.todos["active"], 1):
                todo_list += f"{i}. {todo['item']} (added: {todo['created_at']})\n"
            return todo_list

    def _get_relevant_docs(self, query: str, num_docs: int = 3) -> str:
        """Get relevant documentation based on query"""
        if not self.documents:
            return ""
        
        # Make search terms more flexible
        search_terms = ["swiss re", "bes", "index", "biodiversity"]
        query_terms = query.lower().split()
        relevant_chunks = []
        
        for doc in self.documents:
            content = doc.page_content.lower()
            # Check for any relevant terms
            if any(term in content for term in search_terms) or any(term in content for term in query_terms):
                chunk = f"Source: {doc.metadata.get('source', 'unknown')}\n{doc.page_content}"
                relevant_chunks.append(chunk)
            
        return "\n\n---\n\n".join(relevant_chunks[:num_docs])

    async def process_query(self, query: str) -> str:
        """Process query using Claude's intelligence with access to our resources"""
        
        # Get any relevant docs but don't force their use
        doc_context = self._get_relevant_docs(query)
        
        # Get account data if it seems relevant
        account_context = ""
        if any(term in query.lower() for term in ['.basin', '.earth', 'account', 'token']):
            account_name = self._extract_account_name(query)
            if account_name:
                account_data = await self.sql_reader.get_account_details(account_name)
                if account_data:
                    account_context = f"\nAccount Data:\n{json.dumps(account_data, indent=2)}"

        system_prompt = f"""You are Terroir, an AI assistant focused on the BASIN and Situs protocols.

        You have access to:
        - Your general knowledge and reasoning abilities
        - Protocol documentation (if relevant to the query)
        - Account data from our database (if relevant)
        - Previous conversations and learned facts
        
        Feel free to:
        - Use your judgment on which information sources are most relevant
        - Combine information from multiple sources
        - Express uncertainty when appropriate
        - Ask for clarification if needed
        - Draw on your general knowledge when appropriate
        
        Available Context (use if relevant):
        {doc_context}
        {account_context}
        
        Previous Conversations:
        {self.memory.load_memory_variables({}).get('chat_history', '')}
        
        Learned Facts:
        {json.dumps(self.learned_knowledge.get('verified_facts', []), indent=2)}"""

        message = await self.chat_model.ainvoke(
            system_prompt + "\n\nHuman: " + query
        )
        
        if message and message.content:
            return message.content
        return "I apologize, I need more context to answer that question. Could you provide more details?"

    def _load_protocol_docs(self):
        """
        Load all protocol documentation at startup
        """
        repos = {
            "docs": ["basin-global/situs-docs", "basin-global/BASIN-Field-Manual"],
            "code": ["basin-global/Situs-Protocol"]
        }
        
        total_docs = 0
        for repo in repos["docs"]:
            docs = self.load_github_docs(repo)
            total_docs += len(docs)
        
        for repo in repos["code"]:
            docs = self.load_github_docs(repo, include_code=True)
            total_docs += len(docs)
            
        print(f"\nTotal documents loaded: {total_docs}")
        if total_docs == 0:
            print("Warning: No documents were loaded. Responses will be based on core instructions only.")

    def load_github_docs(self, repo_url: str, branch: str = "main", include_code: bool = False):
        """
        Load documentation and optionally code from a GitHub repository
        """
        try:
            file_types = [".md", ".mdx"]
            if include_code:
                file_types.extend([".sol"])
                
            loader = GithubFileLoader(
                access_token=self.config.GITHUB_PERSONAL_ACCESS_TOKEN,
                repo=repo_url,
                branch=branch,
                file_filter=lambda file_path: any(file_path.endswith(ext) for ext in file_types)
            )
            
            docs = loader.load()
            self.documents.extend(docs)
            print(f"\nLoaded {len(docs)} documents from {repo_url}")
            # Print first few lines of each doc for verification
            for doc in docs:
                preview = doc.page_content[:100] + "..."
                print(f"Document: {doc.metadata.get('source')}")
                print(f"Preview: {preview}\n")
            return docs
            
        except Exception as e:
            print(f"Error loading docs from {repo_url}: {e}")
            return []

    def _load_learned_knowledge(self):
        """Load previously learned information"""
        try:
            with open(self.knowledge_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "interactions": [],
                "verified_facts": [],
                "corrections": []
            }
    
    def _save_learned_knowledge(self):
        """Save learned information to disk"""
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.knowledge_file), exist_ok=True)
        with open(self.knowledge_file, 'w') as f:
            json.dump(self.learned_knowledge, f, indent=2)

    def _extract_account_name(self, query: str) -> str:
        """Extract account name from query if present"""
        try:
            words = query.split()
            for word in words:
                if '.basin' in word or '.earth' in word:
                    # Only return if it looks like an account name
                    if len(word.split('.')) == 2:
                        return word
        except Exception as e:
            print(f"Error extracting account name: {e}")
        return None

    async def get_recent_activity(self, limit: int = 5) -> str:
        """Get and format recent account activity"""
        activity = await self.sql_reader.get_recent_activity(limit)
        return f"Recent Activity:\n{json.dumps(activity, indent=2)}"

    def _process_new_learning(self, query: str, response: str, source: dict = None):
        """Process and store new learnings with source validation"""
        if not source:
            is_authorized = True
        else:
            is_authorized = self._validate_learning_source(source)
            
        if not is_authorized:
            return "Sorry, only authorized users can add new learnings or corrections."
            
        # Process the learning
        self.learned_knowledge["interactions"].append({
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "response": response,
            "source": source or "local",
            "verified": is_authorized
        })
        
        # Check for new learning command "nl" in the QUERY
        if "nl:" in query.lower() and is_authorized:
            new_learning = query.split("nl:")[1].strip()
            self.learned_knowledge["verified_facts"].append({
                "fact": new_learning,
                "added_by": source or "local",
                "timestamp": datetime.now().isoformat()
            })
        
        # Check for correction command "cor" in the QUERY
        if "cor:" in query.lower() and is_authorized:
            correction = query.split("cor:")[1].strip()
            self.learned_knowledge["corrections"].append({
                "correction": correction,
                "added_by": source or "local",
                "timestamp": datetime.now().isoformat()
            })
        
        self._save_learned_knowledge()

    def _validate_learning_source(self, source: dict) -> bool:
        """Validate if the source is authorized to add learnings"""
        if source.get("platform") == "farcaster":
            fid = source.get("fid")
            address = source.get("address", "").lower()
            
            # Check if FID matches
            if fid != self.authorized_learners["farcaster"]["fid"]:
                return False
            
            # Check if address is either custody or verified
            valid_addresses = [
                self.authorized_learners["farcaster"]["custody"].lower(),
                *[addr.lower() for addr in self.authorized_learners["farcaster"]["verified"]]
            ]
            
            return address in valid_addresses
            
        return False

    def _update_rag(self):
        """Update RAG with new learnings"""
        self._initialize_rag()  # Reinitialize with updated knowledge

    def _serialize_for_json(self, obj):
        """Handle datetime serialization for JSON"""
        if isinstance(obj, (datetime, datetime.date)):
            return obj.isoformat()
        return str(obj)

    def _initialize_faq(self):
        """Initialize FAQ system"""
        try:
            with open(self.faq_file, 'r') as f:
                self.faq_responses = json.load(f)
        except FileNotFoundError:
            self.faq_responses = {
                "common_questions": {},
                "protocol_basics": {}
            }
            self._save_faq()

    def _save_faq(self):
        """Save FAQ to disk"""
        os.makedirs(os.path.dirname(self.faq_file), exist_ok=True)
        with open(self.faq_file, 'w') as f:
            json.dump(self.faq_responses, f, indent=2)

    def _process_faq_command(self, query: str):
        """Process FAQ commands"""
        if "faq:" in query.lower():
            # Add new FAQ
            # Format: faq: category | question | pattern1, pattern2 | response
            parts = query.split("faq:")[1].split("|")
            if len(parts) == 4:
                category = parts[0].strip()
                question = parts[1].strip()
                patterns = [p.strip() for p in parts[2].split(",")]
                response = parts[3].strip()
                
                if category not in self.faq_responses:
                    self.faq_responses[category] = {}
                    
                self.faq_responses[category][question] = {
                    "patterns": patterns,
                    "response": response
                }
                self._save_faq()
                return f"Added FAQ: {question} to category: {category}"
                
        elif query.lower() == "show faq":
            output = "FAQ Categories:\n"
            for category, questions in self.faq_responses.items():
                output += f"\n{category}:\n"
                for question, data in questions.items():
                    output += f"- {question}\n"
                    output += f"  Patterns: {', '.join(data['patterns'])}\n"
                    output += f"  Response: {data['response']}\n"
            return output

    async def get_account_by_token(self, og_type: str, token_id: int) -> Dict:
        """Get account details by token ID and OG type"""
        conn = await asyncpg.connect(self.connection_string)
        try:
            table_name = f"situs_accounts_{og_type}"
            result = await conn.fetchrow(f"""
                SELECT 
                    token_id,
                    account_name,
                    created_at,
                    tba_address,
                    description
                FROM {table_name}
                WHERE token_id = $1
            """, token_id)
            
            if result:
                return dict(result)
            return None
        finally:
            await conn.close()
    async def process_query(self, query: str) -> str:
        # Check for token ID queries
        if any(word in query.lower() for word in ["token", "id"]) and any(og in query.lower() for og in [".earth", ".basin"]):
            try:
                # Extract OG type and token ID
                og_type = "earth" if ".earth" in query.lower() else "basin"
                token_id = int(''.join(filter(str.isdigit, query)))
                
                # Use existing sql_reader to get account details
                table_name = f"situs_accounts_{og_type}"
                if table_name in self.sql_reader.account_tables:
                    results = await self.sql_reader.get_all_accounts(og_type)
                    for account in results:
                        if account['token_id'] == token_id:
                            return f"Token {token_id} in .{og_type} is account: {account['account_name']}"
            except Exception as e:
                print(f"Error looking up token: {e}")
        
        # Rest of process_query remains the same...
