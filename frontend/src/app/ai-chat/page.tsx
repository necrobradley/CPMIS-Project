'use client'
import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { aiApi, projectsApi } from '@/lib/api'
import { Project } from '@/types'
import { Bot, Send, Loader2, User, Sparkles, X, RotateCcw } from 'lucide-react'

interface Message {
  id:      number
  role:    'user' | 'assistant'
  content: string
  time:    Date
}

const SUGGESTIONS = [
  'Bagaimana cara mengelola risiko keterlambatan proyek konstruksi?',
  'Jelaskan tahapan pekerjaan pondasi bored pile',
  'Apa saja komponen penting dalam laporan kemajuan proyek?',
  'Bagaimana cara menghitung produktivitas tenaga kerja di lapangan?',
  'Tips komunikasi efektif dengan subkontraktor',
]

export default function AIChatPage() {
  const [messages, setMessages]     = useState<Message[]>([])
  const [input, setInput]           = useState('')
  const [loading, setLoading]       = useState(false)
  const [projectId, setProjectId]   = useState<number | undefined>()
  const bottomRef = useRef<HTMLDivElement>(null)
  let msgId = useRef(0)

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => (await projectsApi.list()).data,
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function sendMessage(text?: string) {
    const content = (text ?? input).trim()
    if (!content || loading) return
    setInput('')

    const userMsg: Message = { id: ++msgId.current, role: 'user', content, time: new Date() }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)

    try {
      const { data } = await aiApi.chat(content, projectId)
      const aiMsg: Message = {
        id: ++msgId.current, role: 'assistant',
        content: data.response, time: new Date(),
      }
      setMessages((prev) => [...prev, aiMsg])
    } catch {
      const errMsg: Message = {
        id: ++msgId.current, role: 'assistant',
        content: '❌ Maaf, terjadi kesalahan. Pastikan API key OpenAI sudah dikonfigurasi.',
        time: new Date(),
      }
      setMessages((prev) => [...prev, errMsg])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  function clearChat() { setMessages([]) }

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] animate-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <Sparkles size={24} className="text-violet-500" />
            AI Assistant
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Tanya apapun tentang proyek konstruksi Anda
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select value={projectId ?? ''}
            onChange={(e) => setProjectId(e.target.value ? Number(e.target.value) : undefined)}
            className="input w-52 text-sm">
            <option value="">Tanpa konteks proyek</option>
            {projects.map((p) => <option key={p.id} value={p.id}>{p.project_name}</option>)}
          </select>
          {messages.length > 0 && (
            <button onClick={clearChat} className="btn-secondary text-sm">
              <RotateCcw size={14} /> Reset
            </button>
          )}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 card overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Welcome state */}
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center py-12">
              <div className="w-16 h-16 bg-violet-100 rounded-2xl flex items-center justify-center mb-4">
                <Bot size={32} className="text-violet-500" />
              </div>
              <h3 className="text-lg font-semibold text-slate-800 mb-2">AI Construction Assistant</h3>
              <p className="text-sm text-slate-400 mb-8 max-w-md">
                Tanya saya tentang manajemen proyek konstruksi, K3, estimasi biaya, jadwal, laporan, dan lainnya.
              </p>
              <div className="w-full max-w-lg space-y-2">
                <p className="text-xs text-slate-400 font-semibold uppercase tracking-wide mb-3">Pertanyaan Saran</p>
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => sendMessage(s)}
                    className="w-full text-left text-sm px-4 py-3 rounded-xl border border-slate-200
                               hover:border-violet-300 hover:bg-violet-50 transition text-slate-600
                               hover:text-violet-700 group">
                    <span className="text-violet-400 mr-2 group-hover:text-violet-500">→</span>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          {messages.map((msg) => (
            <div key={msg.id}
              className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
              {/* Avatar */}
              <div className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-1
                ${msg.role === 'user' ? 'bg-brand-500' : 'bg-violet-100'}`}>
                {msg.role === 'user'
                  ? <User size={15} className="text-white" />
                  : <Bot size={15} className="text-violet-600" />
                }
              </div>

              {/* Bubble */}
              <div className={`max-w-[72%] ${msg.role === 'user' ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
                <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap
                  ${msg.role === 'user'
                    ? 'bg-brand-500 text-white rounded-tr-sm'
                    : 'bg-slate-100 text-slate-800 rounded-tl-sm'
                  }`}>
                  {msg.content}
                </div>
                <span className="text-[10px] text-slate-400 px-1">
                  {msg.time.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
          ))}

          {/* Loading bubble */}
          {loading && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-xl bg-violet-100 flex items-center justify-center flex-shrink-0">
                <Bot size={15} className="text-violet-600" />
              </div>
              <div className="bg-slate-100 px-4 py-3 rounded-2xl rounded-tl-sm">
                <div className="flex gap-1.5 items-center">
                  <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input area */}
        <div className="border-t border-slate-100 p-4">
          <div className="flex gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              placeholder="Tulis pertanyaan Anda... (Enter untuk kirim)"
              className="input flex-1 resize-none min-h-[44px] max-h-32 py-2.5"
              style={{ height: 'auto' }}
            />
            <button
              onClick={() => sendMessage()}
              disabled={!input.trim() || loading}
              className="btn-primary px-4 py-2.5 flex-shrink-0 self-end"
            >
              {loading
                ? <Loader2 size={16} className="animate-spin" />
                : <Send size={16} />
              }
            </button>
          </div>
          <p className="text-[11px] text-slate-400 mt-2 text-center">
            AI CPMIS menggunakan GPT-4o-mini. Respons mungkin tidak selalu akurat — verifikasi informasi penting.
          </p>
        </div>
      </div>
    </div>
  )
}
