import os
import sys
from langchain_community.document_loaders.generic import GenericLoader
from langchain_community.document_loaders.parsers import LanguageParser
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# 1. Define supported languages for the Parser
SUPPORTED_LANGUAGES = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".jsx": Language.JS,
    ".ts": Language.TS,
    ".tsx": Language.TS,
}

def run_ingestion(target_path):
    db_path = os.path.join(os.getcwd(), "chroma_db_idx")
    print(f"🚀 Starting Advanced Ingestion from: {target_path}")

    # 2. Multi-Format Loading
    # We include .json and .md, but we'll parse them as text, not code structure
    loader = GenericLoader.from_filesystem(
        target_path,
        glob="**/*",
        suffixes=[".py", ".js", ".jsx", ".ts", ".tsx", ".md", ".json"],
        parser=LanguageParser() # Automatically detects language based on suffix!
    )
    
    print("📂 Loading and Parsing files...")
    raw_documents = loader.load()
    
    if not raw_documents:
        print("❌ No compatible files found.")
        return

    # 3. Optimized Chunking for Code
    # Smaller chunks (800) with higher overlap (200) helps keep 
    # function headers attached to their bodies in the next chunk.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=200,
        add_start_index=True # Preserves "Line Number" metadata
    )
    
    docs = splitter.split_documents(raw_documents)
    
    # 4. Deduplication & Metadata Cleanup
    # We ensure every chunk has a clean 'source' path
    unique_contents = set()
    final_docs = []
    for doc in docs:
        content_hash = hash(doc.page_content)
        if content_hash not in unique_contents:
            unique_contents.add(content_hash)
            # Make the source path relative for cleaner UI display
            doc.metadata["source"] = os.path.relpath(doc.metadata["source"], target_path)
            final_docs.append(doc)

    print(f"✅ Created {len(final_docs)} unique chunks (Filtered from {len(docs)}).")

    # 5. Embedding & Storage
    print("🧠 Updating Vector Database...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # We overwrite the old DB to ensure we have the new metadata format
    vectorstore = Chroma.from_documents(
        documents=final_docs,
        embedding=embeddings,
        persist_directory=db_path
    )
    
    print(f"✨ Success! Context-aware index created at {db_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ingest.py ./your_codebase")
    else:
        run_ingestion(sys.argv[1])