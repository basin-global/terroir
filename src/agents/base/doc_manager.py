from langchain_community.document_loaders.github import GithubFileLoader
from langchain.schema import Document
from typing import List
import json
import os

class DocManager:
    def __init__(self, config):
        self.config = config
        self.documents = []
        self.cache_dir = "src/data/cache"
        self.cache_file = os.path.join(self.cache_dir, "docs_cache.json")
        self._load_protocol_docs()

    def get_relevant(self, query: str, num_docs: int = 3) -> str:
        """Get relevant documentation based on query"""
        if not self.documents:
            return ""
        
        # Convert query terms to keywords
        query_terms = query.lower().split()
        
        # Score and sort documents by relevance
        scored_docs = []
        for doc in self.documents:
            source = doc.metadata.get('source', '')
            content = doc.page_content.lower()
            
            # Calculate relevance score
            score = 0
            for term in query_terms:
                if term in content:
                    score += 1
                # Give extra weight to docs with matching terms in path
                if term in source.lower():
                    score += 2
                    
            if score > 0:
                scored_docs.append((score, doc))
        
        # Sort by score and get top docs
        scored_docs.sort(reverse=True, key=lambda x: x[0])
        relevant_docs = [doc for score, doc in scored_docs[:num_docs]]
        
        # Format context with source paths
        context = []
        for doc in relevant_docs:
            source = doc.metadata.get('source', 'unknown')
            context.append(f"Source: {source}\n{doc.page_content}")
        
        return "\n\n---\n\n".join(context)

    def _load_protocol_docs(self, force_refresh: bool = False):
        """Load all protocol documentation"""
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Try cache first unless forcing refresh
        if not force_refresh:
            try:
                if os.path.exists(self.cache_file) and os.path.getsize(self.cache_file) > 0:
                    with open(self.cache_file, 'r') as f:
                        cached_data = json.load(f)
                        print(f"\nLoaded {len(cached_data)} documents from cache")
                        self.documents = [
                            Document(
                                page_content=doc['content'],
                                metadata=doc['metadata']
                            ) for doc in cached_data
                        ]
                        return
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"Cache not usable: {e}")
        
        # Load from GitHub
        print("Loading fresh documents from GitHub...")
        repos = {
            "docs": ["basin-global/situs-docs", "basin-global/BASIN-Field-Manual"],
            "code": ["basin-global/Situs-Protocol"]
        }
        
        total_docs = 0
        for repo in repos["docs"]:
            docs = self.load_github_docs(repo)
            total_docs += len(docs)
        
        if total_docs > 0:
            # Cache the documents
            cache_data = [
                {
                    'content': doc.page_content,
                    'metadata': doc.metadata
                } for doc in self.documents
            ]
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f)
            
            print(f"\nLoaded and cached {total_docs} fresh documents from GitHub")
        else:
            print("Warning: No documents were loaded from GitHub")

    def load_github_docs(self, repo_url: str, branch: str = "main") -> List[Document]:
        """Load documentation from a GitHub repository"""
        try:
            loader = GithubFileLoader(
                access_token=self.config.GITHUB_PERSONAL_ACCESS_TOKEN,
                repo=repo_url,
                branch=branch,
                recursive=True,
                file_filter=lambda file_path: file_path.endswith(('.md', '.mdx'))
            )
            
            docs = loader.load()
            self.documents.extend(docs)
            return docs
            
        except Exception as e:
            print(f"\nError loading docs from {repo_url}: {e}")
            return []