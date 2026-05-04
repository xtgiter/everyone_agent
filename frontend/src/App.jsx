import { useState, useEffect, useRef } from 'react'
import ChatWindow from './components/ChatWindow'
import Sidebar from './components/Sidebar'
import { Bot, Trash2, Wrench, MessageSquare, PanelLeftClose, PanelLeft } from 'lucide-react'

// ── API helpers ──

async function apiCreateSession(mode = 'agent') {
  const res = await fetch('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  })
  return res.json()
}

async function apiListSessions() {
  const res = await fetch('/api/sessions')
  const data = await res.json()
  return data.sessions || []
}

async function apiGetSession(id) {
  const res = await fetch(`/api/sessions/${id}`)
  return res.json()
}

async function apiSaveSession(id, messages, mode) {
  await fetch(`/api/sessions/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, mode }),
  })
}

async function apiRenameSession(id, title) {
  await fetch(`/api/sessions/${id}/rename`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}

async function apiDeleteSession(id) {
  await fetch(`/api/sessions/${id}`, { method: 'DELETE' })
}

async function apiSwitchBranch(sessionId, nodeId) {
  const res = await fetch(`/api/sessions/${sessionId}/switch-branch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ node_id: nodeId }),
  })
  return res.json()
}

// ── SSE stream reader ──

function parseSSEStream(text, state, setContextTokens, setMaxContextTokens) {
  // Prepend any leftover partial line from the previous chunk
  const raw = (state._sseBuffer || '') + text
  const lines = raw.split('\n')
  // Last element may be an incomplete line — save it for next chunk
  state._sseBuffer = lines.pop()

  for (const line of lines) {
    if (!line.startsWith('data: ')) continue
    const dataStr = line.slice(6).trim()
    if (!dataStr) continue
    try {
      const data = JSON.parse(dataStr)
      if (data.error || data.type === 'error') {
        state.accumulated += `\n\n**错误:** ${data.error || data.content}`
      } else if (data.type === 'context_info') {
        setContextTokens(data.tokens || 0)
        if (data.max_tokens) setMaxContextTokens(data.max_tokens)
      } else if (data.type === 'tool_call') {
        state.toolCalls = [...state.toolCalls, { tool: data.tool, arguments: data.arguments, status: 'running' }]
      } else if (data.type === 'tool_result') {
        state.toolCalls = state.toolCalls.map((tc, i) =>
          i === state.toolCalls.length - 1 ? { ...tc, status: 'done', success: data.success, output: data.output } : tc
        )
      } else if (data.type === 'text' || data.content !== undefined) {
        const c = data.content || ''
        if (c) state.accumulated += c
      }
    } catch { /* incomplete JSON — will retry when more data arrives */ }
  }
}

// ── App ──

function App() {
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [branches, setBranches] = useState({})
  const [isLoading, setIsLoading] = useState(false)
  const [mode, setMode] = useState('agent')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [contextTokens, setContextTokens] = useState(0)
  const [maxContextTokens, setMaxContextTokens] = useState(0)
  const messagesRef = useRef(messages)
  const modeRef = useRef(mode)
  const activeIdRef = useRef(activeSessionId)
  messagesRef.current = messages
  modeRef.current = mode
  activeIdRef.current = activeSessionId

  useEffect(() => {
    apiListSessions().then((list) => {
      setSessions(list)
      if (list.length > 0) loadSession(list[0].id)
    })
    fetch('/api/context-config')
      .then((r) => r.json())
      .then((data) => { if (data.max_context_tokens) setMaxContextTokens(data.max_context_tokens) })
      .catch(() => {})
  }, [])

  // ── Session helpers ──

  const loadSession = async (id) => {
    const session = await apiGetSession(id)
    if (session && !session.error) {
      setActiveSessionId(id)
      const msgs = session.messages || []
      setMessages(msgs)
      setBranches(session.branches || {})
      setMode(session.mode || 'agent')
      if (msgs.length > 0) {
        try {
          const res = await fetch('/api/count-tokens', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: msgs.map(({ role, content }) => ({ role, content })) }),
          })
          const data = await res.json()
          setContextTokens(data.tokens || 0)
          if (data.max_tokens) setMaxContextTokens(data.max_tokens)
        } catch { setContextTokens(0) }
      } else {
        setContextTokens(0)
      }
    }
  }

  const saveSession = async (sessionId, msgs, sessionMode) => {
    if (!sessionId) return
    await apiSaveSession(sessionId, msgs, sessionMode)
    const list = await apiListSessions()
    setSessions(list)
  }

  const refreshSessions = async () => {
    const list = await apiListSessions()
    setSessions(list)
  }

  // ── Session actions ──

  const handleCreateSession = async () => {
    if (activeIdRef.current && messagesRef.current.length > 0) {
      await saveSession(activeIdRef.current, messagesRef.current, modeRef.current)
    }
    const session = await apiCreateSession(mode)
    await refreshSessions()
    setActiveSessionId(session.id)
    setMessages([])
    setBranches({})
    setContextTokens(0)
  }

  const handleSelectSession = async (id) => {
    if (id === activeIdRef.current) return
    if (activeIdRef.current && messagesRef.current.length > 0) {
      await saveSession(activeIdRef.current, messagesRef.current, modeRef.current)
    }
    await loadSession(id)
  }

  const handleDeleteSession = async (id) => {
    await apiDeleteSession(id)
    const list = await apiListSessions()
    setSessions(list)
    if (id === activeIdRef.current) {
      if (list.length > 0) {
        await loadSession(list[0].id)
      } else {
        setActiveSessionId(null)
        setMessages([])
        setBranches({})
        setContextTokens(0)
      }
    }
  }

  const handleRenameSession = async (id, title) => {
    await apiRenameSession(id, title)
    await refreshSessions()
  }

  const handleModeChange = async (newMode) => {
    setMode(newMode)
    if (activeIdRef.current) {
      await saveSession(activeIdRef.current, messagesRef.current, newMode)
    }
  }

  // ── Branch switching ──

  const handleSwitchBranch = async (nodeId) => {
    if (!activeIdRef.current || isLoading) return
    // Save current state first
    await saveSession(activeIdRef.current, messagesRef.current, modeRef.current)
    const session = await apiSwitchBranch(activeIdRef.current, nodeId)
    if (session && !session.error) {
      setMessages(session.messages || [])
      setBranches(session.branches || {})
    }
  }

  // ── Core streaming request ──

  const streamResponse = async (priorMessages, sessionId) => {
    const endpoint = modeRef.current === 'agent' ? '/api/agent' : '/api/chat'
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: priorMessages.filter((m) => m.role === 'user' || (m.role === 'assistant' && m.content)),
        session_id: sessionId || undefined,
      }),
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`)

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    const state = { accumulated: '', toolCalls: [], _sseBuffer: '' }
    let finalMessages = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      parseSSEStream(decoder.decode(value, { stream: true }), state, setContextTokens, setMaxContextTokens)
      finalMessages = [...priorMessages, { role: 'assistant', content: state.accumulated, toolCalls: [...state.toolCalls] }]
      setMessages(finalMessages)
    }

    if (finalMessages && sessionId) {
      await saveSession(sessionId, finalMessages, modeRef.current)
      // Reload to get updated branch info
      const session = await apiGetSession(sessionId)
      if (session && !session.error) setBranches(session.branches || {})
    }
    return finalMessages
  }

  // ── Send message ──

  const handleSend = async (content) => {
    if (!content.trim() || isLoading) return

    let sessionId = activeIdRef.current
    if (!sessionId) {
      const session = await apiCreateSession(mode)
      sessionId = session.id
      setActiveSessionId(sessionId)
      await refreshSessions()
    }

    const userMessage = { role: 'user', content }
    const newMessages = [...messages, userMessage]
    setMessages([...newMessages, { role: 'assistant', content: '', toolCalls: [] }])
    setIsLoading(true)

    try {
      await streamResponse(newMessages, sessionId)
    } catch (err) {
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          content: `**连接错误:** ${err.message}\n\n请检查后端是否已启动，以及 API Key 是否配置正确。`,
          toolCalls: [],
        }
        return updated
      })
    } finally {
      setIsLoading(false)
    }
  }

  // ── Regenerate (creates a new branch) ──

  const handleRegenerate = async () => {
    if (isLoading || messages.length < 2) return
    const lastUserIdx = messages.map((m) => m.role).lastIndexOf('user')
    if (lastUserIdx === -1) return

    const keepMessages = messages.slice(0, lastUserIdx + 1)
    setMessages([...keepMessages, { role: 'assistant', content: '', toolCalls: [] }])
    setIsLoading(true)

    try {
      await streamResponse(keepMessages, activeIdRef.current)
    } catch (err) {
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'assistant',
          content: `**连接错误:** ${err.message}`,
          toolCalls: [],
        }
        return updated
      })
    } finally {
      setIsLoading(false)
    }
  }

  // ── Clear chat ──

  const handleClear = async () => {
    setMessages([])
    setBranches({})
    setContextTokens(0)
    if (activeIdRef.current) {
      await saveSession(activeIdRef.current, [], modeRef.current)
    }
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {sidebarOpen && (
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelect={handleSelectSession}
          onCreate={handleCreateSession}
          onDelete={handleDeleteSession}
          onRename={handleRenameSession}
        />
      )}

      <div className="flex flex-col flex-1 min-w-0">
        <header className="flex items-center justify-between px-4 py-3 bg-white border-b border-gray-200 shadow-sm">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
            >
              {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
            </button>
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-600 text-white">
              <Bot size={18} />
            </div>
            <div>
              <h1 className="text-base font-semibold text-gray-800">Everyone Agent</h1>
              <p className="text-xs text-gray-400">本地 AI 助手</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center bg-gray-100 rounded-lg p-0.5">
              <button
                onClick={() => handleModeChange('chat')}
                className={`flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  mode === 'chat' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <MessageSquare size={14} />
                对话
              </button>
              <button
                onClick={() => handleModeChange('agent')}
                className={`flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  mode === 'agent' ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <Wrench size={14} />
                Agent
              </button>
            </div>
            <button
              onClick={handleClear}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-500 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
              title="清空对话"
            >
              <Trash2 size={16} />
              <span className="hidden sm:inline">清空</span>
            </button>
          </div>
        </header>

        <ChatWindow
          messages={messages}
          branches={branches}
          isLoading={isLoading}
          onSend={handleSend}
          onRegenerate={handleRegenerate}
          onSwitchBranch={handleSwitchBranch}
          mode={mode}
          contextTokens={contextTokens}
          maxContextTokens={maxContextTokens}
        />
      </div>
    </div>
  )
}

export default App
