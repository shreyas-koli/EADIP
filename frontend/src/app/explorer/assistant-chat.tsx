"use client"

import * as React from "react"
import { DatabaseTable, ChatMessage, AIProviderId, ProviderStatus, explorerApi } from "@/lib/api/explorer"
import { Button } from "@/components/ui/button"
import { Send, Bot, User, Loader2, AlertCircle, Wifi, WifiOff, RefreshCw } from "lucide-react"
import ReactMarkdown from "react-markdown"

interface AssistantChatProps {
  warehouseId: number
  selectedTable: DatabaseTable | null
  onSendToSqlConsole?: (sql: string) => void
  messages?: ChatMessage[]
  onMessagesChange?: (messages: ChatMessage[]) => void
}

const PROVIDER_META: Record<AIProviderId, { label: string; modeLabel: string }> = {
  openai: { label: "OpenAI", modeLabel: "Online" },
  gemini: { label: "Gemini", modeLabel: "Online" },
  ollama: { label: "Local", modeLabel: "Ollama" },
}

export function AssistantChat({
  warehouseId,
  selectedTable,
  onSendToSqlConsole,
  messages: messagesProp,
  onMessagesChange,
}: AssistantChatProps) {
  const [internalMessages, setInternalMessages] = React.useState<ChatMessage[]>([])
  const messages = messagesProp !== undefined ? messagesProp : internalMessages

  const updateMessages = React.useCallback(
    (newMsgs: ChatMessage[]) => {
      if (messagesProp === undefined) {
        setInternalMessages(newMsgs)
      }
      onMessagesChange?.(newMsgs)
    },
    [messagesProp, onMessagesChange]
  )

  const [input, setInput] = React.useState("")
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  // Context Key for isolation check
  const contextKey = selectedTable
    ? `${warehouseId}:${selectedTable.schema_name}.${selectedTable.name}`
    : `${warehouseId}:_global_`

  const prevContextKeyRef = React.useRef(contextKey)

  // Clear input/error when switching context (table change)
  React.useEffect(() => {
    if (prevContextKeyRef.current !== contextKey) {
      prevContextKeyRef.current = contextKey
      setInput("")
      setError(null)
    }
  }, [contextKey])

  // Provider state
  const [providers, setProviders] = React.useState<ProviderStatus[]>([])
  const [selectedProvider, setSelectedProvider] = React.useState<AIProviderId | null>(null)
  const [isLoadingProviders, setIsLoadingProviders] = React.useState(true)
  const [providerError, setProviderError] = React.useState<string | null>(null)

  const messagesEndRef = React.useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  React.useEffect(() => {
    scrollToBottom()
  }, [messages, isLoading])

  const fetchProviders = React.useCallback(async () => {
    setIsLoadingProviders(true)
    setProviderError(null)
    try {
      const data = await explorerApi.getAssistantProviders(warehouseId)
      setProviders(data.providers)
      // Auto-select the default provider if we haven't picked one yet
      setSelectedProvider((prev) => {
        if (prev) return prev // preserve explicit user selection
        const defaultProv = data.providers.find((p) => p.id === data.default_provider)
        if (defaultProv?.available) return defaultProv.id as AIProviderId
        // Default unavailable — leave null, user must pick
        return null
      })
    } catch {
      setProviderError("Could not load provider status.")
    } finally {
      setIsLoadingProviders(false)
    }
  }, [warehouseId])

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchProviders()
  }, [fetchProviders])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || isLoading) return
    if (!selectedProvider) {
      setError("Please select an AI provider before sending.")
      return
    }

    const newMessages: ChatMessage[] = [...messages, { role: "user", content: text }]
    updateMessages(newMessages)
    setInput("")
    setIsLoading(true)
    setError(null)

    try {
      const payload = {
        messages: newMessages,
        schema_name: selectedTable?.schema_name,
        table_name: selectedTable?.name,
        provider: selectedProvider,
      }
      
      const res = await explorerApi.chatAssistant(warehouseId, payload)
      const updatedMessages: ChatMessage[] = [...newMessages, { role: "assistant", content: res.response }]
      updateMessages(updatedMessages)
    } catch (err) {
      const e = err as Error
      setError(e.message || "Failed to communicate with assistant.")
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const activeMeta = selectedProvider ? PROVIDER_META[selectedProvider] : null
  const activeProviderStatus = providers.find((p) => p.id === selectedProvider)

  return (
    <div className="flex flex-col h-full bg-slate-900/50 rounded-lg border border-slate-800 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-800 bg-slate-900">
        <Bot className="h-5 w-5 text-blue-400 shrink-0" />
        <div className="flex flex-col min-w-0">
          <h3 className="font-semibold text-sm text-slate-200 leading-tight">Warehouse AI Assistant</h3>
          {activeMeta && activeProviderStatus && (
            <span className="text-[10px] text-slate-400 flex items-center gap-1">
              {activeProviderStatus.available
                ? <Wifi className="h-2.5 w-2.5 text-emerald-400" />
                : <WifiOff className="h-2.5 w-2.5 text-red-400" />}
              {activeMeta.label} · {activeMeta.modeLabel}
            </span>
          )}
        </div>
        {selectedTable && (
          <span className="ml-auto text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded-full shrink-0">
            Context: {selectedTable.schema_name}.{selectedTable.name}
          </span>
        )}
      </div>

      {/* Provider Selector */}
      <div className="px-3 py-2 border-b border-slate-800 bg-slate-900/70">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] text-slate-500 uppercase tracking-wider font-medium mr-1">AI Provider</span>

          {isLoadingProviders ? (
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Loader2 className="h-3 w-3 animate-spin" />
              <span>Loading…</span>
            </div>
          ) : providerError ? (
            <div className="flex items-center gap-1.5 text-xs text-red-400">
              <AlertCircle className="h-3 w-3" />
              <span>{providerError}</span>
              <button onClick={fetchProviders} className="text-slate-400 hover:text-slate-200">
                <RefreshCw className="h-3 w-3" />
              </button>
            </div>
          ) : (
            <>
              {providers.map((p) => {
                const meta = PROVIDER_META[p.id as AIProviderId]
                const isSelected = selectedProvider === p.id
                return (
                  <button
                    key={p.id}
                    onClick={() => setSelectedProvider(p.id as AIProviderId)}
                    title={p.available ? `${meta.label} (${meta.modeLabel})` : (p.reason ?? "Unavailable")}
                    className={[
                      "flex flex-col items-start px-2.5 py-1 rounded-md border text-left transition-all cursor-pointer",
                      "focus:outline-none focus:ring-1 focus:ring-blue-500/50",
                      isSelected
                        ? p.available
                          ? "border-blue-500 bg-blue-600/20 text-white"
                          : "border-amber-500 bg-amber-500/10 text-amber-200"
                        : p.available
                        ? "border-slate-700 bg-slate-800 text-slate-300 hover:border-slate-500 hover:bg-slate-700"
                        : "border-slate-800 bg-slate-900/80 text-slate-500 hover:border-slate-700 hover:bg-slate-800",
                    ].join(" ")}
                  >
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`h-1.5 w-1.5 rounded-full shrink-0 ${
                          p.available ? "bg-emerald-400" : "bg-red-400"
                        }`}
                      />
                      <span className="text-xs font-medium leading-tight">{meta.label}</span>
                    </div>
                    <span className="text-[10px] leading-tight pl-3">
                      {p.available
                        ? meta.modeLabel
                        : "Unavailable"}
                    </span>
                  </button>
                )
              })}
              <button
                onClick={fetchProviders}
                title="Refresh provider status"
                className="ml-auto text-slate-600 hover:text-slate-400 transition-colors"
              >
                <RefreshCw className="h-3 w-3" />
              </button>
            </>
          )}
        </div>

        {selectedProvider && !activeProviderStatus?.available && (
          <p className="text-[10px] text-red-400 mt-1.5 flex items-center gap-1">
            <AlertCircle className="h-3 w-3 shrink-0" />
            {activeProviderStatus?.reason || "Selected provider is unavailable. Please check backend configuration."}
          </p>
        )}
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-[200px]">
        {messages.length === 0 && !isLoading && (
          <div className="flex flex-col items-center justify-center h-full text-slate-500 space-y-2">
            <Bot className="h-10 w-10 opacity-20" />
            {selectedProvider ? (
              <p className="text-sm">Ask me about your warehouse schema or to generate SQL queries.</p>
            ) : (
              <p className="text-sm text-amber-500/80">Select an AI provider above to begin.</p>
            )}
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="shrink-0 mt-0.5">
                <div className="w-6 h-6 rounded-full bg-blue-900/50 border border-blue-500/30 flex items-center justify-center">
                  <Bot className="h-3.5 w-3.5 text-blue-400" />
                </div>
              </div>
            )}
            
            <div
              className={`max-w-[85%] rounded-lg px-4 py-2.5 text-sm ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-slate-800 text-slate-200 border border-slate-700"
              }`}
            >
              {msg.role === "user" ? (
                <div className="whitespace-pre-wrap">{msg.content}</div>
              ) : (
                <div className="prose prose-invert prose-sm max-w-none prose-pre:bg-slate-950 prose-pre:border prose-pre:border-slate-700">
                  <ReactMarkdown
                    components={{
                      code({ inline, className, children, ...props }: React.ComponentPropsWithoutRef<"code"> & { inline?: boolean }) {
                        const match = /language-(\w+)/.exec(className || "")
                        const isSql = match && match[1] === "sql"
                        
                        if (!inline && isSql) {
                          const sqlText = String(children).replace(/\n$/, "")
                          return (
                            <div className="relative group">
                              <code className={className} {...props}>
                                {children}
                              </code>
                              <button 
                                onClick={() => onSendToSqlConsole?.(sqlText)}
                                className="absolute top-2 right-2 bg-slate-800 hover:bg-blue-600 text-[10px] text-white px-2 py-1 rounded transition-colors flex items-center gap-1 opacity-80 hover:opacity-100"
                              >
                                <Send className="h-3 w-3" />
                                Send to SQL Console
                              </button>
                            </div>
                          )
                        }
                        return <code className={className} {...props}>{children}</code>
                      }
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                </div>
              )}
            </div>

            {msg.role === "user" && (
              <div className="shrink-0 mt-0.5">
                <div className="w-6 h-6 rounded-full bg-slate-700 flex items-center justify-center">
                  <User className="h-3.5 w-3.5 text-slate-300" />
                </div>
              </div>
            )}
          </div>
        ))}
        
        {isLoading && (
          <div className="flex gap-3 justify-start">
            <div className="shrink-0 mt-0.5">
              <div className="w-6 h-6 rounded-full bg-blue-900/50 border border-blue-500/30 flex items-center justify-center">
                <Bot className="h-3.5 w-3.5 text-blue-400" />
              </div>
            </div>
            <div className="bg-slate-800 text-slate-200 border border-slate-700 rounded-lg px-4 py-2.5 text-sm flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
              <span className="text-slate-400 italic">
                {selectedProvider ? `${PROVIDER_META[selectedProvider].label} is thinking…` : "Thinking…"}
              </span>
            </div>
          </div>
        )}
        
        {error && (
          <div className="flex items-center gap-2 text-sm text-red-400 bg-red-950/30 border border-red-900/50 p-3 rounded-md">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <p>{error}</p>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-3 border-t border-slate-800 bg-slate-900/50">
        <div className="flex items-end gap-2 bg-slate-950 border border-slate-700 rounded-lg focus-within:border-blue-500/50 focus-within:ring-1 focus-within:ring-blue-500/20 transition-all p-1">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={selectedProvider ? "Ask about tables, columns, or request a query…" : "Select a provider above first…"}
            disabled={!selectedProvider}
            className="flex-1 bg-transparent border-0 text-sm text-slate-200 placeholder:text-slate-500 resize-none p-2 min-h-[40px] max-h-[120px] focus:ring-0 focus:outline-none leading-relaxed disabled:opacity-40"
            rows={1}
          />
          <Button
            onClick={handleSend}
            disabled={!input.trim() || isLoading || !selectedProvider}
            size="sm"
            className="h-8 w-8 p-0 shrink-0 mb-1 mr-1 bg-blue-600 hover:bg-blue-700 text-white rounded-md disabled:opacity-50 disabled:bg-slate-800 disabled:text-slate-500"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
        <div className="text-[10px] text-slate-500 text-center mt-2">
          AI can make mistakes. Verify queries before running them. Press Enter to send, Shift+Enter for new line.
        </div>
      </div>
    </div>
  )
}
