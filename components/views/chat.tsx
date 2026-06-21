"use client";

import { FormEvent, useState, useRef, useEffect } from "react";
import { ArrowUp, Bot, FileCode2, Lightbulb, MessageCircle, Paperclip, Sparkles, UserRound } from "lucide-react";
import { sendChatMessage, type ChatSource } from "../api-client";
import { MarkdownRenderer } from "../markdown-renderer";

type Message = { role: "user" | "assistant"; text: string; sources?: ChatSource[] };

const prompts = [
  "How does authentication work?",
  "What should I read first?",
  "Where is the orchestrator pipeline built?",
  "Explain the project execution flow"
];

interface ChatProps {
  repoId: string;
}

export function Chat({ repoId }: ChatProps) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    { 
      role: "assistant", 
      text: "I’ve mapped this repository's syntax structure and generated semantic code embeddings. Ask me how something works, where it is defined, or what files to read first." 
    },
  ]);
  const [thinking, setThinking] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  
  // Reference for auto-scrolling chat history
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, thinking]);

  // Clean conversation on repo switch
  useEffect(() => {
    setConversationId(null);
    setMessages([
      { 
        role: "assistant", 
        text: "I’ve mapped this repository's syntax structure and generated semantic code embeddings. Ask me how something works, where it is defined, or what files to read first." 
      }
    ]);
  }, [repoId]);

  const send = async (question: string) => {
    if (!question.trim() || thinking) return;
    
    // Add user message
    setMessages((items) => [...items, { role: "user", text: question }]);
    setInput("");
    setThinking(true);

    try {
      const response = await sendChatMessage(repoId, question, conversationId);
      
      // Update session conversation ID
      if (response.conversation_id) {
        setConversationId(response.conversation_id);
      }

      setMessages((items) => [
        ...items, 
        { 
          role: "assistant", 
          text: response.answer, 
          sources: response.sources 
        }
      ]);
    } catch (err: any) {
      setMessages((items) => [
        ...items, 
        { 
          role: "assistant", 
          text: "I encountered an error trying to search the codebase. Please make sure the backend is active." 
        }
      ]);
    } finally {
      setThinking(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    send(input);
  };

  return (
    <section className="flex min-h-[calc(100vh-156px)] flex-col">
      <div className="mb-6">
        <p className="eyebrow text-ember">Semantic repository search</p>
        <h1 className="display mt-2 text-4xl font-bold sm:text-5xl">Ask the code.</h1>
        <p className="mt-2 text-sm text-ink/50 leading-6">
          Conversational responses grounded directly in retrieved source code chunks. Source links map to local workspace file lines.
        </p>
      </div>

      <div className="card grid min-h-[620px] flex-1 overflow-hidden lg:grid-cols-[1fr_290px]">
        <div className="flex min-h-[600px] flex-col border-b border-ink/10 lg:border-b-0 lg:border-r">
          <div className="flex-1 space-y-6 overflow-y-auto p-4 sm:p-6 max-h-[500px]">
            {messages.map((message, index) => (
              <div key={index} className={`flex gap-3 ${message.role === "user" ? "justify-end" : ""}`}>
                {message.role === "assistant" && (
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-acid shadow-[2px_2px_0_#20241f]"><Bot size={17} /></span>
                )}
                <div className={`max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-6 whitespace-pre-line ${message.role === "user" ? "rounded-br-sm bg-ink text-paper" : "rounded-tl-sm border border-ink/10 bg-white/55 text-ink/70"}`}>
                  {message.role === "assistant" ? (
                    <MarkdownRenderer content={message.text} />
                  ) : (
                    message.text
                  )}
                  {message.role === "assistant" && message.sources && message.sources.length > 0 && (
                    <div className="mt-4 flex flex-wrap gap-2 border-t border-ink/10 pt-3">
                      {message.sources.map((source, sIdx) => (
                        <a 
                          key={sIdx}
                          href={`file:///${source.file_path}`} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="flex items-center gap-1.5 rounded-lg bg-paper px-2 py-1 font-mono text-[9px] font-bold text-ink hover:bg-white transition"
                          title={`Relevance: ${Math.round(source.relevance_score * 100)}%`}
                        >
                          <FileCode2 size={11} />
                          {source.file_path.split("/").pop()}:{source.line_interval[0]}–{source.line_interval[1]}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
                {message.role === "user" && (
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-mint"><UserRound size={17} /></span>
                )}
              </div>
            ))}
            {thinking && (
              <div className="flex gap-3">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-acid"><Bot size={17} /></span>
                <div className="flex items-center gap-1 rounded-2xl rounded-tl-sm border border-ink/10 bg-white/55 px-4 py-3">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink/45" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink/45 [animation-delay:120ms]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink/45 [animation-delay:240ms]" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="border-t border-ink/10 bg-[#eee9dc]/70 p-3 sm:p-4 mt-auto">
            <form onSubmit={submit} className="flex items-end gap-2 rounded-2xl border border-ink/20 bg-white p-2 shadow-sm focus-within:border-ink">
              <button type="button" className="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-ink/35 hover:bg-paper hover:text-ink"><Paperclip size={17} /></button>
              <textarea 
                value={input} 
                onChange={(e) => setInput(e.target.value)} 
                onKeyDown={(e) => { 
                  if (e.key === "Enter" && !e.shiftKey) { 
                    e.preventDefault(); 
                    send(input); 
                  } 
                }} 
                rows={1} 
                className="max-h-28 min-h-10 flex-1 resize-none bg-transparent py-2.5 text-sm outline-none placeholder:text-ink/30" 
                placeholder="Ask about architecture, files, or behavior…" 
              />
              <button 
                type="submit"
                disabled={!input.trim() || thinking} 
                className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-ember text-white transition hover:-translate-y-0.5 disabled:opacity-30"
              >
                <ArrowUp size={17} />
              </button>
            </form>
            <p className="mt-2 text-center text-[9px] text-ink/35">Grounded in repository source · Answers may be approximate</p>
          </div>
        </div>

        <aside className="bg-[#eee9dc] p-5">
          <div className="flex items-center gap-2">
            <Sparkles size={17} className="text-ember" />
            <p className="eyebrow">Good starting points</p>
          </div>
          <div className="mt-4 space-y-2">
            {prompts.map((prompt) => (
              <button 
                key={prompt} 
                onClick={() => send(prompt)} 
                className="group flex w-full items-start gap-2 rounded-xl border border-ink/10 bg-white/45 p-3 text-left text-xs font-semibold leading-5 transition hover:border-ink/25 hover:bg-white"
              >
                <MessageCircle size={14} className="mt-0.5 shrink-0 text-ink/30 group-hover:text-ember" />
                {prompt}
              </button>
            ))}
          </div>
          <div className="mt-7 rounded-2xl bg-ink p-4 text-paper">
            <Lightbulb size={18} className="text-acid" />
            <div className="mt-3 text-xs font-bold">Ask for comparisons</div>
            <p className="mt-1 text-[11px] leading-5 text-paper/45">Try “compare the AST and graph agents” or “which module has the highest maintainability risk?”</p>
          </div>
          <div className="mt-6 border-t border-ink/10 pt-4">
            <p className="eyebrow text-ink/35">Retrieval health</p>
            <div className="mt-3 space-y-2 text-[11px]">
              <div className="flex justify-between">
                <span className="text-ink/45">Vector Store</span>
                <strong>FAISS (Local)</strong>
              </div>
              <div className="flex justify-between">
                <span className="text-ink/45">Embedding Model</span>
                <strong>MiniLM-L6</strong>
              </div>
              <div className="flex justify-between">
                <span className="text-ink/45">Index status</span>
                <strong className="text-[#39745e]">Active</strong>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
