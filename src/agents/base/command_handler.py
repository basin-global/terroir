import json
import os
from datetime import datetime

class CommandHandler:
    def __init__(self):
        self.todo_file = "src/data/commands/todo_list.json"
        self.faq_file = "src/data/commands/faq_responses.json"
        self._initialize_todos()
        self._initialize_faq()
        
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
            
    def _initialize_faq(self):
        """Initialize FAQ system"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.faq_file), exist_ok=True)
            
            # Try to read existing file
            if os.path.exists(self.faq_file) and os.path.getsize(self.faq_file) > 0:
                with open(self.faq_file, 'r') as f:
                    self.faq_responses = json.load(f)
            else:
                # Create default structure if file doesn't exist or is empty
                self.faq_responses = {
                    "common_questions": {},
                    "protocol_basics": {}
                }
                self._save_faq()
                
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Issue loading FAQ file: {e}")
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
            
    def process(self, query: str) -> str:
        """Process commands like todo, faq, etc"""
        # Let FarcasterHandler handle cast commands
        if "cast:" in query.lower() or ("cast+" in query.lower() and ":" in query.lower()):
            return None  # Let TerriorAgent handle it via FarcasterHandler
            
        # Check FAQ commands
        faq_response = self._process_faq_command(query)
        if faq_response:
            return faq_response
            
        # Check todo commands
        todo_response = self._process_todo(query)
        if todo_response:
            return todo_response
            
        return None

    def _process_todo(self, query: str) -> str:
        """Process todo commands"""
        if "todo:" in query.lower():
            todo_item = query.split("todo:")[1].strip()
            self.todos["active"].append({
                "item": todo_item,
                "created_at": datetime.now().isoformat()
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

        elif query.lower() == "show todos":
            if not self.todos["active"]:
                return "No active todos."
            
            todo_list = "Active Todos:\n"
            for i, todo in enumerate(self.todos["active"], 1):
                todo_list += f"{i}. {todo['item']} (added: {todo['created_at']})\n"
            return todo_list

        return None

    def _process_faq_command(self, query: str) -> str:
        """Process FAQ commands"""
        if "faq:" in query.lower():
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

        return None