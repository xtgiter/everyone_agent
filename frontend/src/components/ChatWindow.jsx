import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { Send, Bot, User, Loader2, Wrench, CheckCircle2, XCircle, ChevronDown, ChevronRight, RefreshCw, ChevronLeft, GitBranch } from 'lucide-react'

function ToolCallCard({ tc }) {
  const [expanded, setExpanded] = useState(false)
  const isRunning = tc.status === 'running'

  return (
    <div className="my-2 rounded-lg border border-gray-200 bg-gray-50 text-xs overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full px-3 py-2 hover:bg-gray-100 transition-colors text-left"
      >
        {isRunning ? (
          <Loader2 size={13} className="animate-spin text-indigo-500 flex-shrink-0" />
        ) : tc.success ? (
          <CheckCircle2 size={13} className="text-green-500 flex-shrink-0" />
        ) : (
          <XCircle size={13} className="text-red-500 flex-shrink-0" />
        )}
        <Wrench size={13} className="text-gray-400 flex-shrink-0" />
        <span className="font-mono font-semibold text-gray-700">{tc.tool}</span>
        <span className="text-gray-400 truncate flex-1">
          {JSON.stringify(tc.arguments).slice(0, 60)}
        </span>
        {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
      </button>
      {expanded && (
        <div className="px-3 pb-2 space-y-1">
          <div>
            <span className="text-gray-500 font-medium">Args: </span>
            <pre className="inline whitespace-pre-wrap text-gray-600 font-mono">
              {JSON.stringify(tc.arguments, null, 2)}
            </pre>
          </div>
          {tc.output && (
            <div>
              <span className="text-gray-500 font-medium">Result: </span>
              <pre className="whitespace-pre-wrap text-gray-600 font-mono max-h-40 overflow-y-auto mt-1 p-2 bg-white rounded border border-gray-200">
                {tc.output}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function BranchIndicator({ branchList, onSwitch }) {
  const activeIdx = branchList.findIndex((b) => b.active)
  const total = branchList.length

  const handlePrev = () => {
    const prevIdx = activeIdx > 0 ? activeIdx - 1 : total - 1
    onSwitch(branchList[prevIdx].id)
  }
  const handleNext = () => {
    const nextIdx = activeIdx < total - 1 ? activeIdx + 1 : 0
    onSwitch(branchList[nextIdx].id)
  }

  return (
    <div className="inline-flex items-center gap-0.5 px-1 py-0.5 rounded-md bg-gray-100 text-xs text-gray-500 select-none">
      <button onClick={handlePrev} className="p-0.5 hover:text-indigo-600 transition-colors" title="上一个分支">
        <ChevronLeft size={12} />
      </button>
      <span className="flex items-center gap-0.5 px-0.5 font-medium">
        <GitBranch size={11} />
        {activeIdx + 1}/{total}
      </span>
      <button onClick={handleNext} className="p-0.5 hover:text-indigo-600 transition-colors" title="下一个分支">
        <ChevronRight size={12} />
      </button>
    </div>
  )
}

function ChatWindow({ messages, branches, isLoading, onSend, onRegenerate, onSwitchBranch, mode, contextTokens, maxContextTokens }) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + 'px'
    }
  }, [input])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    onSend(input)
    setInput('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-gray-400 select-none">
            <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-indigo-100 text-indigo-500 mb-4">
              <Bot size={32} />
            </div>
            <p className="text-lg font-medium text-gray-500">开始新对话</p>
            <p className="text-sm mt-1">
              {mode === 'agent' ? 'Agent 模式：可调用工具完成复杂任务' : '输入消息，按 Enter 发送'}
            </p>
          </div>
        )}

        <div className="max-w-3xl mx-auto space-y-4">
          {messages.map((msg, idx) => {
            const isLastAssistant = msg.role === 'assistant' && idx === messages.length - 1
            return (
              <div key={idx}>
                <div className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {msg.role === 'assistant' && (
                    <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center mt-1">
                      <Bot size={16} />
                    </div>
                  )}

                  <div
                    className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-indigo-600 text-white rounded-br-md'
                        : 'bg-white text-gray-800 border border-gray-200 rounded-bl-md shadow-sm'
                    }`}
                  >
                    {msg.role === 'assistant' ? (
                      <div>
                        {/* Tool Calls */}
                        {msg.toolCalls && msg.toolCalls.length > 0 && (
                          <div className="mb-2">
                            {msg.toolCalls.map((tc, i) => (
                              <ToolCallCard key={i} tc={tc} />
                            ))}
                          </div>
                        )}
                        {/* Text Content */}
                        <div className="markdown-body">
                          {msg.content ? (
                            <ReactMarkdown>{msg.content}</ReactMarkdown>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-gray-400">
                              <Loader2 size={14} className="animate-spin" />
                              {msg.toolCalls && msg.toolCalls.length > 0 ? '工具调用中...' : '思考中...'}
                            </span>
                          )}
                        </div>
                      </div>
                    ) : (
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    )}
                  </div>

                  {msg.role === 'user' && (
                    <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gray-200 text-gray-600 flex items-center justify-center mt-1">
                      <User size={16} />
                    </div>
                  )}
                </div>

                {/* Branch indicator + Regenerate button */}
                {msg.role === 'assistant' && (
                  <div className="flex items-center gap-2 ml-11 mt-1.5">
                    {msg._node_id && branches && branches[msg._node_id] && (
                      <BranchIndicator branchList={branches[msg._node_id]} onSwitch={onSwitchBranch} />
                    )}
                    {isLastAssistant && msg.content && !isLoading && (
                      <button
                        onClick={onRegenerate}
                        className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-md transition-colors"
                        title="重新生成（创建新分支）"
                      >
                        <RefreshCw size={13} />
                        重新生成
                      </button>
                    )}
                  </div>
                )}
              </div>
            )
          })}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 bg-white px-4 py-3">
        {maxContextTokens > 0 && (
          <div className="max-w-3xl mx-auto mb-2 flex items-center justify-end gap-2">
            <div className="flex items-center gap-1.5">
              <div className="w-32 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    maxContextTokens > 0 && contextTokens / maxContextTokens > 0.85
                      ? 'bg-red-500'
                      : maxContextTokens > 0 && contextTokens / maxContextTokens > 0.6
                      ? 'bg-amber-500'
                      : 'bg-indigo-500'
                  }`}
                  style={{ width: `${maxContextTokens > 0 ? Math.min(100, (contextTokens / maxContextTokens) * 100) : 0}%` }}
                />
              </div>
              <span className={`text-xs font-medium ${
                maxContextTokens > 0 && contextTokens / maxContextTokens > 0.85
                  ? 'text-red-500'
                  : maxContextTokens > 0 && contextTokens / maxContextTokens > 0.6
                  ? 'text-amber-500'
                  : 'text-gray-400'
              }`}>
                {contextTokens.toLocaleString()} / {maxContextTokens.toLocaleString()} tokens
                {maxContextTokens > 0 ? ` (${Math.round((contextTokens / maxContextTokens) * 100)}%)` : ''}
              </span>
            </div>
          </div>
        )}
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto flex items-end gap-3">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={mode === 'agent' ? 'Agent 模式：可以让我搜索、读写文件、执行命令...' : '输入消息... (Shift+Enter 换行)'}
            rows={1}
            className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent placeholder-gray-400 transition-shadow"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="flex-shrink-0 w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
          </button>
        </form>
      </div>
    </div>
  )
}

export default ChatWindow
