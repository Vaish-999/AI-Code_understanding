import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Monitor, Folder, FileText, ChevronRight, ChevronDown, Code, X, Settings2, Send, Bot } from 'lucide-react';

// --- Recursive File Tree Component ---
const FileItem = ({ item, onFileClick }) => {
  const [isOpen, setIsOpen] = useState(false);
  const isDirectory = item.type === "directory";

  const handleClick = () => {
    if (isDirectory) {
      setIsOpen(!isOpen);
    } else {
      onFileClick(item.path);
    }
  };

  return (
    <div className="ml-4">
      <div
        className={`flex items-center gap-2 py-1 px-2 rounded cursor-pointer hover:bg-gray-800 transition-colors ${isDirectory ? 'text-gray-300' : 'text-gray-400'}`}
        onClick={handleClick}
      >
        {isDirectory ? (
          <>
            {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <Folder size={14} className="text-blue-400" />
          </>
        ) : (
          <FileText size={14} className="ml-4 text-gray-500" />
        )}
        <span className="text-[11px] font-mono truncate">{item.name}</span>
      </div>

      {isDirectory && isOpen && item.children && (
        <div className="border-l border-gray-800 ml-2">
          {item.children.map((child, idx) => (
            <FileItem key={idx} item={child} onFileClick={onFileClick} />
          ))}
        </div>
      )}
    </div>
  );
};

// --- Link Renderer for Chat ---
const renderTextWithLinks = (text, onFileClick) => {
  if (!text) return "";
  // Split on brackets and URLs
  const parts = text.split(/(\[.*?\]|https?:\/\/[^\s]+)/g);
  
  return parts.map((part, i) => {
    if (part.startsWith('[') && part.endsWith(']')) {
      const filePath = part.slice(1, -1).trim();
      return (
        <span 
          key={i}
          onClick={() => {
            console.log("🔗 Clicked File Link:", filePath);
            onFileClick(filePath);
          }}
          className="text-blue-400 underline cursor-pointer hover:text-blue-300 font-mono font-bold bg-blue-500/10 px-1 rounded mx-1"
        >
          {filePath}
        </span>
      );
    } else if (part.startsWith('http://') || part.startsWith('https://')) {
      return (
        <a 
          key={i}
          href={part}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-400 underline cursor-pointer hover:text-blue-300"
        >
          {part}
        </a>
      );
    }
    return part;
  });
};

function App() {
  const [input, setInput] = useState("");
  const [chat, setChat] = useState([]);
  const [loading, setLoading] = useState(false);
  
  // 1. Updated default to a standard local model
  const [selectedModel, setSelectedModel] = useState("llama-3.3-70b-versatile");
  
  const [files, setFiles] = useState([]);
  const [activeFile, setActiveFile] = useState(null);
  const chatEndRef = useRef(null);

  // Auto-scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat]);

  // 1. Fetch File Tree
  useEffect(() => {
    const getFiles = async () => {
      try {
        const res = await axios.get("http://localhost:8000/api/files");
        setFiles(res.data.files);
      } catch (err) {
        console.error("Failed to fetch files", err);
      }
    };
    getFiles();
  }, []);

  // 2. Handle File Click
 const handleFileClick = async (filePath) => {
  try {
    const response = await fetch(`http://localhost:8000/api/file-content?path=${encodeURIComponent(filePath)}`);
    const data = await response.json();

    // 🚨 Check if the backend returned an error message inside the 'content'
    if (data.filename === "Error" || data.content.startsWith("File not found")) {
       console.error("Backend couldn't find file:", data.content);
       return; 
    }

    // This is where you update your state to show the code
    setActiveFile({
      name: data.filename,
      path: filePath,
      content: data.content
    });
  } catch (err) {
    console.error("Failed to fetch file content:", err);
  }
};

  // 3. Text Selection
  const handleTextSelection = () => {
    const selectedText = window.getSelection().toString().trim();
    if (selectedText && selectedText.length > 2) {
      setInput(`Where else is "${selectedText}" used in this project?`);
      document.querySelector('input')?.focus();
    }
  };

  const sendMessage = async () => {
    if (!input.trim()) return;

    const history = chat.map(m => ({
      role: m.role === 'ai' ? 'assistant' : 'user',
      content: m.text
    }));

    const userMsg = { role: 'user', text: input };
    setChat(prev => [...prev, userMsg]);
    const currentInput = input;
    setInput("");
    setLoading(true);

    try {
      setChat(prev => [...prev, { role: 'ai', text: "", sources: [] }]);
      
      // DYNAMIC PROVIDER DETECTION
      // If the model name has a '/', it's a Hugging Face model
      const getProvider = (model) => {
      if (model.includes('/')) return "huggingface";
      if (["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "mixtral-8x7b-32768"].includes(model)) return "groq";
      return "ollama";
      };
      const provider = getProvider(selectedModel);

      const response = await fetch("http://localhost:8000/api/chat", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: currentInput,
          model_name: selectedModel,
          provider: provider, // 👈 Dynamically calculated
          active_file_content: activeFile ? activeFile.content : "",
          history: history
        }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let aiResponseText = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        lines.forEach(line => {
          if (!line) return;
          try {
            const data = JSON.parse(line);
            if (data.text) {
              aiResponseText += data.text;
              setChat(prev => {
                const newChat = [...prev];
                newChat[newChat.length - 1].text = aiResponseText;
                return newChat;
              });
            } else if (data.sources) {
              setChat(prev => {
                const newChat = [...prev];
                newChat[newChat.length - 1].sources = data.sources;
                return newChat;
              });
            }
          } catch (e) { }
        });
      }
    } catch (err) {
      console.error("Error:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
   <div className="flex h-screen bg-[#0d1117] text-gray-300 overflow-hidden font-sans text-sm">

      {/* 1. SIDEBAR: Fixed Width */}
      <div className="w-[20%] min-w-[240px] border-r border-gray-800 bg-[#161b22] flex flex-col shrink-0">
        <div className="p-4 border-b border-gray-800 flex items-center gap-2">
          <Monitor size={16} className="text-blue-500" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400 font-mono">Project Explorer</h2>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {files.map((file, idx) => <FileItem key={idx} item={file} onFileClick={handleFileClick} />)}
        </div>
      </div>

      {/* 2. CENTER: Code Preview (Stable Manual Vertical Layout) */}
      <div className="w-[40%] border-r border-gray-800 flex flex-col bg-[#0d1117] relative shrink-0 overflow-hidden">
        {activeFile ? (
          <>
            <div className="p-3 border-b border-gray-800 flex justify-between items-center bg-[#161b22] sticky top-0 z-10">
              <div className="flex items-center gap-2 text-xs font-mono text-blue-400 truncate">
                <Code size={14} className="shrink-0" /> 
                <span className="truncate">{activeFile.name}</span>
              </div>
              <button onClick={() => setActiveFile(null)} className="hover:text-red-400 text-gray-500 shrink-0">
                <X size={14} />
              </button>
            </div>
            
            {loading && (
              <div className="absolute inset-0 bg-blue-500/5 animate-pulse pointer-events-none z-20" />
            )}

            <div 
              className="flex-1 overflow-auto p-6 font-mono text-[12px] text-gray-400 leading-relaxed bg-[#0d1117]" 
              onMouseUp={handleTextSelection}
            >
              <pre className="whitespace-pre min-w-full">
                {activeFile.content}
              </pre>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-600 italic border-r border-gray-800">
            Select a file to preview
          </div>
        )}
      </div>

      {/* 3. RIGHT: Chat Window (Updated Select Options) */}
      <div className="flex-1 min-w-0 flex flex-col bg-[#0d1117]">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between bg-[#161b22]">
          <h1 className="font-semibold text-sm text-white flex items-center gap-2">
            <Bot size={16} className="text-blue-500" /> Agent <span className="text-blue-500">Chat</span>
          </h1>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded border border-gray-700 bg-[#0d1117]">
            <Settings2 size={12} className="text-gray-500" />
            <select 
              value={selectedModel} 
              onChange={(e) => setSelectedModel(e.target.value)} 
              className="bg-transparent text-[10px] text-blue-400 outline-none cursor-pointer"
            >
              {/* OLLAMA MODELS */}
             <optgroup label="☁️ Cloud (Groq)" className="bg-[#161b22]">
               <option value="llama-3.3-70b-versatile">Llama 3.3 70B</option>
             </optgroup>

              <optgroup label="💻 Local (Ollama)" className="bg-[#161b22]">
                <option value="qwen2.5-coder:1.5b">Qwen 1.5B</option>
                <option value="deepseek-coder-v2:16b">DeepSeek 16B (Local)</option>
              </optgroup>

            </select>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {chat.map((msg, i) => (
            <div key={i} className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] p-4 rounded-lg border ${msg.role === 'user' ? 'bg-blue-600/10 border-blue-500/20' : 'bg-[#161b22] border-gray-800'}`}>
                <div className="text-[9px] font-bold uppercase opacity-40 mb-2 font-mono">
                  {msg.role === 'ai' ? 'Assistant' : 'User'}
                </div>
                <div className="text-sm leading-relaxed whitespace-pre-wrap">
                  {renderTextWithLinks(msg.text, handleFileClick)}
                </div>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-800 flex flex-wrap gap-2">
                    {msg.sources.map((s, idx) => (
                      <span key={idx} className="text-[10px] text-blue-400 font-mono bg-blue-500/5 px-2 py-0.5 rounded border border-blue-500/10">📄 {s}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 bg-[#161b22] border-t border-gray-800">
          <div className="flex gap-2 max-w-4xl mx-auto">
            <input 
              className="flex-1 p-3 bg-[#0d1117] border border-gray-700 rounded text-sm outline-none focus:border-blue-500 transition-all text-white placeholder-gray-500" 
              placeholder={activeFile ? `Ask about ${activeFile.name}...` : "Ask a question..."}
              value={input} 
              onChange={(e) => setInput(e.target.value)} 
              onKeyPress={(e) => e.key === 'Enter' && sendMessage()} 
            />
            <button 
              onClick={sendMessage} 
              className="px-5 bg-blue-600 rounded text-white hover:bg-blue-500 transition-shadow shadow-lg shadow-blue-600/20 active:scale-95"
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;