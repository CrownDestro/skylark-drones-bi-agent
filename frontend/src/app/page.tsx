"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { Send, CheckCircle2, CircleDashed, AlertTriangle, ArrowRight, ChevronDown } from "lucide-react";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  timeline?: { stage: string; status: "running" | "complete" | "error"; message?: string }[];
}

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [showMoreQuestions, setShowMoreQuestions] = useState(false);
  const endOfMessagesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e?: React.FormEvent, customQuery?: string) => {
    if (e) e.preventDefault();
    const query = customQuery || input;
    if (!query.trim() || isLoading) return;

    const userMessage: ChatMessage = { id: Date.now().toString(), role: "user", content: query };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    const assistantId = (Date.now() + 1).toString();
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", content: "", isStreaming: true, timeline: [] },
    ]);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${apiUrl}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: query,
          history: messages.map((m) => ({ role: m.role, content: m.content })),
        }),
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = JSON.parse(line.substring(6));

            setMessages((prev) =>
              prev.map((m) => {
                if (m.id !== assistantId) return m;

                if (data.stage === "complete") {
                  const completedTimeline = (m.timeline || []).map(t => 
                    t.status === "running" ? { ...t, status: "complete" as const } : t
                  );
                  return { ...m, isStreaming: false, content: data.data.response, timeline: completedTimeline };
                } else if (data.stage === "error") {
                  return { ...m, isStreaming: false, content: data.message };
                } else {
                  const newTimeline = [...(m.timeline || [])];
                  const existingStageIdx = newTimeline.findIndex((t) => t.stage === data.stage);

                  if (existingStageIdx >= 0) {
                    newTimeline[existingStageIdx] = { ...newTimeline[existingStageIdx], ...data };
                  } else {
                    newTimeline.push({ stage: data.stage, status: data.status, message: data.message });
                  }
                  return { ...m, timeline: newTimeline };
                }
              })
            );
          }
        }
      }
    } catch (err) {
      console.error(err);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, isStreaming: false, content: "An error occurred connecting to the server." } : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const examples = [
    "How is our pipeline looking this quarter?",
    "Which sector has the strongest pipeline?",
    "How much have we collected?",
    "Prepare a leadership update."
  ];

  const moreQuestions = [
    "What is our total pipeline?",
    "What are our biggest open deals?",
    "How much have we billed?",
    "How much is outstanding?",
    "How are our work orders performing?",
    "Which sectors have strong pipeline but weak execution?",
    "How is the business doing?",
    "How reliable is our current forecast?",
    "What data did you use to answer this?",
    "What is our Renewables pipeline?",
    "What is our Powerline pipeline?"
  ];

  return (
    <div className="min-h-screen flex flex-col bg-white text-gray-900">
      <header className="p-4 border-b border-gray-100 flex items-center">
        <div className="font-semibold text-lg tracking-tight">Skylark Drones BI Agent</div>
      </header>

      <main className="flex-1 overflow-y-auto p-4 md:p-8">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center max-w-2xl mx-auto text-center space-y-8 mt-12">
            <div>
              <h1 className="text-3xl font-semibold mb-3">Skylark Drones</h1>
              <h2 className="text-xl text-gray-500 font-medium">Business Intelligence Agent</h2>
              <p className="mt-4 text-gray-400">Ask founder-level questions about sales, pipeline, operations and collections.</p>
            </div>

            <div className="w-full relative shadow-sm rounded-xl border border-gray-200 focus-within:border-blue-400 focus-within:ring-1 focus-within:ring-blue-400 transition-all">
              <form onSubmit={handleSubmit} className="flex relative">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask a question..."
                  className="w-full p-4 rounded-xl outline-none bg-transparent"
                  disabled={isLoading}
                />
                <button
                  type="submit"
                  disabled={!input.trim() || isLoading}
                  className="absolute right-2 top-2 p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  <Send size={18} />
                </button>
              </form>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full text-left">
              {examples.map((ex, i) => (
                <button
                  key={i}
                  onClick={() => handleSubmit(undefined, ex)}
                  className="p-3 text-sm text-gray-600 border border-gray-100 rounded-lg hover:bg-gray-50 flex items-center justify-between group transition-colors"
                >
                  {ex}
                  <ArrowRight size={14} className="opacity-0 group-hover:opacity-100 transition-opacity text-blue-500" />
                </button>
              ))}
            </div>

            <div className="w-full mt-4">
              <button
                onClick={() => setShowMoreQuestions(!showMoreQuestions)}
                className="mx-auto flex items-center gap-1 text-sm text-gray-400 hover:text-gray-600 transition-colors"
              >
                More questions...
                <ChevronDown size={14} className={`transform transition-transform ${showMoreQuestions ? 'rotate-180' : ''}`} />
              </button>

              {showMoreQuestions && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full text-left mt-4 animate-in slide-in-from-top-2 fade-in duration-200">
                  {moreQuestions.map((ex, i) => (
                    <button
                      key={`more-${i}`}
                      onClick={() => handleSubmit(undefined, ex)}
                      className="p-3 text-sm text-gray-600 border border-gray-100 rounded-lg hover:bg-gray-50 flex items-center justify-between group transition-colors"
                    >
                      {ex}
                      <ArrowRight size={14} className="opacity-0 group-hover:opacity-100 transition-opacity text-blue-500" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto space-y-8 pb-32">
            {messages.map((m) => (
              <div key={m.id} className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}>
                <div className={`max-w-[85%] rounded-2xl px-5 py-4 ${m.role === "user" ? "bg-gray-100 text-gray-900" : "bg-white"}`}>

                  {m.role === "assistant" && m.isStreaming && (
                    <div className="mb-4">
                      <details className="cursor-pointer group" open>
                        <summary className="text-sm font-medium text-gray-500 flex items-center space-x-2 select-none mb-2">
                          <CircleDashed className="animate-spin text-blue-500" size={16} />
                          <span>Working...</span>
                        </summary>
                        <div className="pl-6 space-y-2 mt-2 text-sm text-gray-500 border-l border-gray-100 ml-2">
                          {m.timeline?.map((t, i) => (
                            <div key={i} className="flex items-center space-x-2">
                              {t.status === "complete" ? (
                                <CheckCircle2 size={14} className="text-green-500" />
                              ) : t.status === "error" ? (
                                <AlertTriangle size={14} className="text-red-500" />
                              ) : (
                                <CircleDashed size={14} className="text-blue-500 animate-spin" />
                              )}
                              <span>{t.message || t.stage.replace(/_/g, " ")}</span>
                            </div>
                          ))}
                        </div>
                      </details>
                    </div>
                  )}

                  {m.role === "assistant" && !m.isStreaming && m.timeline && m.timeline.length > 0 && (
                    <div className="mb-4 border-b border-gray-100 pb-4">
                      <details className="cursor-pointer group">
                        <summary className="text-sm font-medium text-gray-400 hover:text-gray-600 flex items-center space-x-2 select-none">
                          <CheckCircle2 className="text-gray-400" size={16} />
                          <span>Working</span>
                        </summary>
                        <div className="pl-6 space-y-2 mt-2 text-sm text-gray-500 border-l border-gray-100 ml-2">
                          {m.timeline?.map((t, i) => (
                            <div key={i} className="flex items-center space-x-2">
                              {t.status === "complete" ? (
                                <CheckCircle2 size={14} className="text-green-500" />
                              ) : t.status === "error" ? (
                                <AlertTriangle size={14} className="text-red-500" />
                              ) : (
                                <CircleDashed size={14} className="text-blue-500 animate-spin" />
                              )}
                              <span className="capitalize">{t.message || t.stage.replace(/_/g, " ")}</span>
                            </div>
                          ))}
                        </div>
                      </details>
                    </div>
                  )}

                  <div className="prose prose-sm md:prose-base prose-slate max-w-none">
                    {m.role === "user" ? m.content : <ReactMarkdown>{m.content}</ReactMarkdown>}
                  </div>
                </div>
              </div>
            ))}
            <div ref={endOfMessagesRef} />
          </div>
        )}
      </main>

      {messages.length > 0 && (
        <div className="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-white via-white to-transparent p-4 md:p-6 pb-6 md:pb-8 flex justify-center">
          <div className="w-full max-w-3xl relative shadow-lg rounded-2xl border border-gray-200 bg-white">
            <form onSubmit={handleSubmit} className="flex relative">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question..."
                className="w-full p-4 rounded-2xl outline-none"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={!input.trim() || isLoading}
                className="absolute right-2 top-2 p-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                <Send size={18} />
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
