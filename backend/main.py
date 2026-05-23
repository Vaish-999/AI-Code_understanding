import os
import json
import ollama
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv 
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from typing import Optional, List, cast
from tools import get_code_context, get_project_structure, get_file_tree,keyword_search

load_dotenv()
app = FastAPI()

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY")
)
GROQ_MODEL = "llama-3.3-70b-versatile"

# --- 1. Security: Enable CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. Data Models ---
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    model_name: str
    history: List[Message] = []
    provider: str = "groq"
    active_file_content: Optional[str] = None 

@app.on_event("startup")
async def startup_event():
    print("🚀 API IS STARTING UP...")
    load_dotenv()
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        print(f"✅ GROQ_API_KEY Loaded: {groq_key[:5]}***")
    else:
        print("❌ ERROR: GROQ_API_KEY NOT FOUND!")

# --- 3. Sidebar: Fetch Project Structure ---
@app.get("/api/files")
async def fetch_files():
    target_repo = os.path.join(os.getcwd(), "test_repo")
    if not os.path.exists(target_repo):
        return {"files": [], "error": f"test_repo not found at {target_repo}"}
    return {"files": get_project_structure(target_repo)}

# --- 4. File Reader (Updated with URL-Sanitization) ---
@app.get("/api/file-content")
async def get_file_content(path: str = Query(...)):
    # 1. Clean the path and strip any hallucinated web prefixes
    clean_path = path.strip("[]").lstrip("./").lstrip("/")
    
    # If AI includes 'example.com/path/to/test_repo...', extract only the repo part
    if "test_repo" in clean_path:
        clean_path = "test_repo" + clean_path.split("test_repo")[-1]

    base_dir = os.getcwd()
    
    # 2. Prevent double-nesting
    if clean_path.startswith("test_repo"):
        full_path = os.path.abspath(os.path.join(base_dir, clean_path))
    else:
        full_path = os.path.abspath(os.path.join(base_dir, "test_repo", clean_path))

    print(f"📂 UI requested file: {full_path}")

    if os.path.exists(full_path) and os.path.isfile(full_path):
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {"content": content, "filename": os.path.basename(full_path)}
        except Exception as e:
            return {"content": f"Read Error: {str(e)}", "filename": "Error"}
    else:
        return {"content": f"File not found. Path checked: {full_path}", "filename": "Error"}

# --- 5. The Chat Agent with Memory ---
@app.post("/api/chat")
async def chat_with_agent(request: ChatRequest):
    print(f"DEBUG: Request Provider: {request.provider} | Model: {request.model_name}")
    
    try:
        context_text, sources = get_code_context(request.message)
        project_map = get_file_tree("./test_repo")
        
        # Aggressive prompt to prevent URL generation in Cloud Models
        system_instruction = f"""
        You are a Senior Architect working in a LOCAL IDE environment.
        📂 PROJECT structure: {project_map}
        📂 ACTIVE FILE: {request.active_file_content if request.active_file_content else 'None'}
        
        🚨 CRITICAL UI RULE: 
        1. NEVER use 'http', 'https', or 'www'.
        2. NEVER generate external web links.
        3. ALWAYS provide local file paths wrapped in square brackets, e.g., [test_repo/conduit/app.py].
        """

        messages: List[ChatCompletionMessageParam] = [cast(ChatCompletionMessageParam, {'role': 'system', 'content': system_instruction})]
        for msg in request.history:
            messages.append(cast(ChatCompletionMessageParam, {'role': msg.role, 'content': msg.content}))
        messages.append(cast(ChatCompletionMessageParam, {'role': 'user', 'content': request.message}))

        async def event_generator():
            yield json.dumps({"sources": ["Cloud (Groq)" if request.provider == "groq" else "Local (Ollama)"]}) + "\n"
    
            if request.provider == "groq":
                response = client.chat.completions.create(
                    model=GROQ_MODEL,           # ← uses fixed model, ignores frontend model_name
                    messages=cast(List[ChatCompletionMessageParam], messages),
                    stream=True
                )
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        yield json.dumps({"text": content}) + "\n"
            
            else:
                stream = ollama.chat(
                    model=request.model_name, 
                    messages=messages, 
                    stream=True
                )
                for chunk in stream:
                    content = chunk['message']['content']
                    yield json.dumps({"text": content}) + "\n"
                            
        return StreamingResponse(event_generator(), media_type="application/x-ndjson")

    except Exception as e:
        print(f"❌ CHAT ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI Engine Error: {str(e)}")
    
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)