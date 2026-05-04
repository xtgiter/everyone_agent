import { useState } from 'react'
import { Plus, MessageSquare, Trash2, PenLine, Check, X } from 'lucide-react'

function Sidebar({ sessions, activeSessionId, onSelect, onCreate, onDelete, onRename }) {
  const [editingId, setEditingId] = useState(null)
  const [editTitle, setEditTitle] = useState('')

  const startRename = (e, session) => {
    e.stopPropagation()
    setEditingId(session.id)
    setEditTitle(session.title)
  }

  const confirmRename = (e) => {
    e.stopPropagation()
    if (editTitle.trim()) {
      onRename(editingId, editTitle.trim())
    }
    setEditingId(null)
  }

  const cancelRename = (e) => {
    e.stopPropagation()
    setEditingId(null)
  }

  return (
    <div className="flex flex-col h-full w-64 bg-gray-900 text-gray-300">
      {/* New Chat Button */}
      <div className="p-3">
        <button
          onClick={onCreate}
          className="flex items-center gap-2 w-full px-3 py-2.5 text-sm font-medium rounded-lg border border-gray-700 hover:bg-gray-800 transition-colors"
        >
          <Plus size={16} />
          新建对话
        </button>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
        {sessions.map((session) => (
          <div
            key={session.id}
            onClick={() => onSelect(session.id)}
            className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer text-sm transition-colors ${
              session.id === activeSessionId
                ? 'bg-gray-700 text-white'
                : 'hover:bg-gray-800 text-gray-400'
            }`}
          >
            <MessageSquare size={14} className="flex-shrink-0 opacity-60" />

            {editingId === session.id ? (
              <div className="flex-1 flex items-center gap-1">
                <input
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') confirmRename(e)
                    if (e.key === 'Escape') cancelRename(e)
                  }}
                  onClick={(e) => e.stopPropagation()}
                  className="flex-1 bg-gray-600 text-white text-sm px-1.5 py-0.5 rounded outline-none"
                  autoFocus
                />
                <button onClick={confirmRename} className="text-green-400 hover:text-green-300">
                  <Check size={14} />
                </button>
                <button onClick={cancelRename} className="text-gray-500 hover:text-gray-300">
                  <X size={14} />
                </button>
              </div>
            ) : (
              <>
                <span className="flex-1 truncate">{session.title}</span>
                <div className="hidden group-hover:flex items-center gap-0.5">
                  <button
                    onClick={(e) => startRename(e, session)}
                    className="p-1 rounded hover:bg-gray-600 text-gray-500 hover:text-gray-300"
                  >
                    <PenLine size={13} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onDelete(session.id)
                    }}
                    className="p-1 rounded hover:bg-gray-600 text-gray-500 hover:text-red-400"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </>
            )}
          </div>
        ))}

        {sessions.length === 0 && (
          <p className="text-center text-gray-600 text-xs mt-8">暂无对话记录</p>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-gray-800 text-xs text-gray-600 text-center">
        Everyone Agent v0.3
      </div>
    </div>
  )
}

export default Sidebar
