# tools.py
import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# Initialize these once so they can be reused
db_path = os.path.join(os.getcwd(), "chroma_db_idx")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory=db_path, embedding_function=embeddings)

def get_code_context(query: str, k: int = 6):
    """
    Searches the vector database and returns both the 
    formatted text context and the list of source files.
    """
    docs = vectorstore.similarity_search(query, k=k)
    
    # Extract unique sources
    sources = list(set([d.metadata.get("source", "Unknown File") for d in docs]))
    
    # Format the text for the LLM
    context_text = "\n\n".join([
        f"--- FILE: {d.metadata.get('source')} ---\n{d.page_content}" 
        for d in docs
    ])
    
    return context_text, sources
def get_file_tree(startpath):
    """
    Generates a visual string representation of the project structure.
    """
    tree = []
    # Files/folders to ignore to keep the tree clean
    ignore_list = {'.git', '__pycache__', 'venv', 'node_modules', '.idx', 'chroma_db_idx'}
    
    for root, dirs, files in os.walk(startpath):
        dirs[:] = [d for d in dirs if d not in ignore_list]
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * level
        tree.append(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            if f not in ignore_list:
                tree.append(f"{subindent}{f}")
                
    return "\n".join(tree)
def get_project_structure(root_path):
    """
    Returns a nested list of dictionaries representing the file tree.
    """
    structure = []
    ignore_list = {'.git', '__pycache__', 'venv', 'node_modules', 'chroma_db_idx', '.DS_Store'}

    try:
        for item in os.listdir(root_path):
            if item in ignore_list:
                continue
                
            full_path = os.path.join(root_path, item)
            is_dir = os.path.isdir(full_path)
            
            # Inside tools.py -> get_project_structure function
            node = {
                "name": item,
                "type": "directory" if is_dir else "file",
                "path": os.path.relpath(full_path, start=os.getcwd()) # This keeps paths relative to Root
            }
            if is_dir:
                # Recursive call to get sub-folders
                node["children"] = get_project_structure(full_path)
            
            structure.append(node)
            
        # Sort so directories appear above files
        return sorted(structure, key=lambda x: (x['type'] != 'directory', x['name'].lower()))
    except Exception as e:
        return [{"name": f"Error: {str(e)}", "type": "file"}]
    
import os

def keyword_search(query, root_path="./test_repo"):
    """
    Scans every file in the project for an exact string match.
    Returns a list of strings formatted as 'filename:line_number'
    """
    results = []
    # Files/folders to skip to keep it fast
    ignore_list = {'.git', '__pycache__', 'venv', 'node_modules', '.DS_Store', 'chroma_db_idx'}
    
    # Standardize the query
    query = query.strip().strip('"').strip("'")
    
    if len(query) < 2:
        return []

    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in ignore_list]
        for file in files:
            if file in ignore_list:
                continue
            
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        if query.lower() in line.lower():
                            # Create a clean relative path
                            rel_path = os.path.relpath(file_path, start=os.getcwd())
                            results.append(f"{rel_path} (Line {line_num})")
                            # Cap results at 15 to avoid overwhelming the AI
                            if len(results) >= 15:
                                return results
            except Exception:
                continue
    return results