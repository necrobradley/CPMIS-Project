'use client'
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { projectsApi, tasksApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { Project, Division, Task } from '@/types'
import { statusBadgeClass, STATUS_LABELS, PRIORITY_LABELS, priorityBadgeClass } from '@/lib/utils'
import { GitBranch, Loader2, Building2, Users, CheckSquare, AlertTriangle } from 'lucide-react'

// ── Mini node renderer (no ReactFlow dep needed for MVP) ─────────
// Full React Flow integration requires npm install — this version
// renders an interactive SVG tree that works without extra packages.

interface TreeNode {
  id:       string
  type:     'project' | 'division' | 'task'
  label:    string
  sublabel?: string
  status?:  string
  priority?: string
  children: TreeNode[]
  count?:   number
}

function buildTree(project: Project, divisions: Division[], tasks: Task[]): TreeNode {
  const divNodes: TreeNode[] = divisions.map(div => {
    const divTasks = tasks.filter(t => t.division_id === div.id)
    const taskNodes: TreeNode[] = divTasks.map(t => ({
      id: `task-${t.id}`, type: 'task', label: `${t.specification?.wbs_code ?? t.id} · ${t.title}`,
      sublabel: `${t.progress_percent}%`, status: t.status, priority: t.priority,
      children: [],
    }))
    return {
      id: `div-${div.id}`, type: 'division', label: div.division_name,
      sublabel: `${divTasks.length} task`, children: taskNodes,
      count: divTasks.filter(t => t.status === 'done').length,
    }
  })

  // Tasks without division
  const noDivTasks = tasks.filter(t => !t.division_id)
  if (noDivTasks.length > 0) {
    divNodes.push({
      id: 'div-none', type: 'division', label: 'Tanpa Divisi',
      sublabel: `${noDivTasks.length} task`,
      children: noDivTasks.map(t => ({
        id: `task-${t.id}`, type: 'task', label: `${t.specification?.wbs_code ?? t.id} · ${t.title}`,
        sublabel: `${t.progress_percent}%`, status: t.status, priority: t.priority,
        children: [],
      })),
    })
  }

  return {
    id: `proj-${project.id}`, type: 'project',
    label: project.project_name, sublabel: `${project.progress_percent}% selesai`,
    status: project.status, children: divNodes,
  }
}

const NODE_W = 200
const NODE_H = 64
const H_GAP  = 40
const V_GAP  = 80

interface LayoutNode {
  node:   TreeNode
  x:      number
  y:      number
  depth:  number
}

function layoutTree(root: TreeNode): LayoutNode[] {
  const result: LayoutNode[] = []
  let leafCount = 0

  function countLeaves(n: TreeNode): number {
    if (n.children.length === 0) return 1
    return n.children.reduce((s, c) => s + countLeaves(c), 0)
  }

  function place(n: TreeNode, depth: number, offset: number): number {
    if (n.children.length === 0) {
      result.push({ node: n, x: offset * (NODE_W + H_GAP), y: depth * (NODE_H + V_GAP), depth })
      return offset + 1
    }
    let cur = offset
    const childXs: number[] = []
    for (const c of n.children) {
      const leafsBefore = cur
      cur = place(c, depth + 1, cur)
      childXs.push(leafsBefore * (NODE_W + H_GAP) + ((cur - leafsBefore - 1) * (NODE_W + H_GAP)) / 2)
    }
    const cx = (childXs[0] + childXs[childXs.length - 1]) / 2
    result.push({ node: n, x: cx, y: depth * (NODE_H + V_GAP), depth })
    return cur
  }

  place(root, 0, 0)
  return result
}

function NodeBox({ node, x, y, selected, onSelect }: {
  node: TreeNode; x: number; y: number
  selected: boolean; onSelect: (n: TreeNode) => void
}) {
  const colors: Record<string, { bg: string; border: string; text: string }> = {
    project:  { bg: '#0ea5e9', border: '#0284c7', text: '#fff' },
    division: { bg: '#6366f1', border: '#4f46e5', text: '#fff' },
    task:     { bg: '#fff', border: selected ? '#0ea5e9' : '#e2e8f0', text: '#1e293b' },
  }
  const c = colors[node.type]
  const isDone = node.status === 'done'
  return (
    <g onClick={() => onSelect(node)} style={{ cursor: 'pointer' }}>
      <rect x={x} y={y} width={NODE_W} height={NODE_H} rx={12}
        fill={isDone && node.type === 'task' ? '#f0fdf4' : c.bg}
        stroke={selected ? '#f59e0b' : c.border}
        strokeWidth={selected ? 2.5 : 1.5}
        filter={selected ? 'drop-shadow(0 4px 12px rgba(14,165,233,.35))' : 'drop-shadow(0 1px 3px rgba(0,0,0,.08))'}
      />
      {/* Icon */}
      <text x={x + 14} y={y + 22} fontSize={14} fill={node.type === 'task' ? '#94a3b8' : '#fff'}>
        {node.type === 'project' ? '🏗️' : node.type === 'division' ? '👥' : '✅'}
      </text>
      {/* Label */}
      <text x={x + 34} y={y + 24} fontSize={11} fontWeight={600}
        fill={node.type === 'task' ? '#1e293b' : '#fff'} fontFamily="Sora,sans-serif">
        {node.label.length > 20 ? node.label.slice(0, 20) + '…' : node.label}
      </text>
      {/* Sublabel */}
      {node.sublabel && (
        <text x={x + 34} y={y + 40} fontSize={10} fill={node.type === 'task' ? '#94a3b8' : 'rgba(255,255,255,.75)'} fontFamily="Sora,sans-serif">
          {node.sublabel}
        </text>
      )}
      {/* Done badge */}
      {isDone && node.type === 'task' && (
        <circle cx={x + NODE_W - 12} cy={y + 12} r={7} fill="#10b981" />
      )}
    </g>
  )
}

function Edge({ x1, y1, x2, y2 }: { x1:number; y1:number; x2:number; y2:number }) {
  const mx = (x1 + x2) / 2
  return (
    <path d={`M${x1},${y1} C${x1},${(y1+y2)/2} ${x2},${(y1+y2)/2} ${x2},${y2}`}
      fill="none" stroke="#cbd5e1" strokeWidth={1.5} />
  )
}

export default function ProjectTreePage() {
  const user = useAuthStore((state) => state.user)
  const isStaff = user?.role === 'staff' || user?.role === 'subcontractor'
  const [projectId, setProjectId] = useState<number | ''>('')
  const [selected, setSelected]   = useState<TreeNode | null>(null)
  const [pan, setPan] = useState({ x: 40, y: 40 })
  const [dragging, setDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => (await projectsApi.list()).data,
  })
  const { data: divisions = [] } = useQuery<Division[]>({
    queryKey: ['divisions', projectId],
    queryFn: async () => projectId ? (await projectsApi.divisions(Number(projectId))).data : [],
    enabled: !!projectId,
  })
  const { data: tasks = [] } = useQuery<Task[]>({
    queryKey: ['tasks', projectId, isStaff ? 'division' : 'all'],
    queryFn: async () => projectId ? (await tasksApi.list({
      project_id: Number(projectId),
      ...(isStaff ? { scope: 'division' } : {}),
    })).data : [],
    enabled: !!projectId,
  })

  useEffect(() => {
    if (!projectId && projects.length > 0) {
      setProjectId(projects[0].id)
    }
  }, [projectId, projects])

  const project = projects.find(p => p.id === Number(projectId))
  const tree = project ? buildTree(project, divisions, tasks) : null
  const layout = tree ? layoutTree(tree) : []

  // Compute SVG size
  const maxX = layout.reduce((m, n) => Math.max(m, n.x + NODE_W), 0)
  const maxY = layout.reduce((m, n) => Math.max(m, n.y + NODE_H), 0)
  const svgW  = maxX + 60
  const svgH  = maxY + 60

  // Edges
  const edges: { x1:number; y1:number; x2:number; y2:number }[] = []
  for (const ln of layout) {
    for (const child of ln.node.children) {
      const childLayout = layout.find(l => l.node.id === child.id)
      if (childLayout) {
        edges.push({
          x1: ln.x + NODE_W / 2,      y1: ln.y + NODE_H,
          x2: childLayout.x + NODE_W / 2, y2: childLayout.y,
        })
      }
    }
  }

  function onMouseDown(e: React.MouseEvent) {
    setDragging(true)
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
  }
  function onMouseMove(e: React.MouseEvent) {
    if (!dragging) return
    setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y })
  }
  function onMouseUp() { setDragging(false) }

  return (
    <div className="space-y-4 animate-in" style={{ height: 'calc(100vh - 80px)' }}>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <GitBranch size={22} className="text-brand-500" /> {isStaff ? 'Struktur Divisi' : 'Project Tree View'}
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {isStaff ? 'Visualisasi proyek, divisi, dan task yang terkait dengan pekerjaan Anda' : 'Visualisasi hierarki proyek, divisi, dan task'}
          </p>
        </div>
        <select value={projectId} onChange={e => { setProjectId(e.target.value ? Number(e.target.value) : ''); setSelected(null) }}
          className="input w-56 text-sm">
          <option value="">Pilih Proyek...</option>
          {projects.map(p => <option key={p.id} value={p.id}>{p.project_name}</option>)}
        </select>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-slate-500">
        {[{color:'#0ea5e9',label:'Proyek'},{color:'#6366f1',label:'Divisi'},{color:'#e2e8f0',label:'Task'}].map(l=>(
          <div key={l.label} className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded" style={{background:l.color,border:'1px solid #cbd5e1'}} />
            {l.label}
          </div>
        ))}
        <span className="text-slate-300">|</span>
        <span>Drag untuk geser · Klik node untuk detail</span>
      </div>

      <div className="flex gap-4 h-full">
        {/* Canvas */}
        <div className="flex-1 card overflow-hidden relative"
          style={{ cursor: dragging ? 'grabbing' : 'grab' }}
          onMouseDown={onMouseDown} onMouseMove={onMouseMove} onMouseUp={onMouseUp} onMouseLeave={onMouseUp}>
          {!projectId ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-300">
              <GitBranch size={48} className="mb-3" />
              <p className="text-sm">{projects.length === 0 ? 'Belum ada proyek yang terhubung ke akun ini' : 'Pilih proyek untuk melihat tree view'}</p>
            </div>
          ) : layout.length === 0 ? (
            <div className="flex items-center justify-center h-full"><Loader2 size={28} className="animate-spin text-brand-500" /></div>
          ) : (
            <svg width={svgW} height={svgH}
              style={{
                transform: `translate(${pan.x}px,${pan.y}px)`,
                transformOrigin: '0 0',
                transition: dragging ? 'none' : 'transform .1s',
                userSelect: 'none',
              }}>
              {edges.map((e, i) => <Edge key={i} {...e} />)}
              {layout.map(ln => (
                <NodeBox key={ln.node.id} node={ln.node} x={ln.x} y={ln.y}
                  selected={selected?.id === ln.node.id}
                  onSelect={setSelected} />
              ))}
            </svg>
          )}
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="w-64 card p-4 space-y-3 overflow-y-auto flex-shrink-0 animate-in">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-800 text-sm">Detail</h3>
              <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-slate-600 text-lg leading-none">×</button>
            </div>
            <div className="space-y-2">
              <div>
                <p className="label">Tipe</p>
                <div className="flex items-center gap-1.5">
                  {selected.type === 'project'  && <Building2 size={13} className="text-brand-500" />}
                  {selected.type === 'division' && <Users size={13} className="text-indigo-500" />}
                  {selected.type === 'task'     && <CheckSquare size={13} className="text-slate-500" />}
                  <span className="text-sm capitalize text-slate-700">{selected.type}</span>
                </div>
              </div>
              <div>
                <p className="label">Nama</p>
                <p className="text-sm text-slate-700">{selected.label}</p>
              </div>
              {selected.status && (
                <div>
                  <p className="label">Status</p>
                  <span className={statusBadgeClass(selected.status)+' badge'}>{STATUS_LABELS[selected.status] ?? selected.status}</span>
                </div>
              )}
              {selected.priority && (
                <div>
                  <p className="label">Prioritas</p>
                  <span className={priorityBadgeClass(selected.priority)+' badge'}>{PRIORITY_LABELS[selected.priority]}</span>
                </div>
              )}
              {selected.sublabel && (
                <div>
                  <p className="label">Progress / Jumlah</p>
                  <p className="text-sm font-semibold text-slate-700">{selected.sublabel}</p>
                </div>
              )}
              {selected.children.length > 0 && (
                <div>
                  <p className="label">Sub-items</p>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {selected.children.map(c => (
                      <button key={c.id} onClick={() => setSelected(c)}
                        className="w-full text-left text-xs px-2 py-1.5 rounded-lg hover:bg-slate-50 transition text-slate-600 flex items-center gap-1.5">
                        <span className="text-slate-400">→</span> {c.label.slice(0, 26)}{c.label.length > 26 ? '…' : ''}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
