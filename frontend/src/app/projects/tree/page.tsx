'use client'

import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertCircle, Building2, CheckSquare, GitBranch, Loader2, Users } from 'lucide-react'

import { projectsApi, tasksApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { Division, Project, Task } from '@/types'
import { PRIORITY_LABELS, STATUS_LABELS, priorityBadgeClass, statusBadgeClass } from '@/lib/utils'

interface TreeNode {
  id: string
  type: 'project' | 'division' | 'task'
  label: string
  sublabel?: string
  status?: string
  priority?: string
  children: TreeNode[]
  taskId?: number
}

function taskNode(task: Task): TreeNode {
  return {
    id: `task-${task.id}`,
    type: 'task',
    taskId: task.id,
    label: `${task.specification?.wbs_code ?? task.id} · ${task.title}`,
    sublabel: `${task.progress_percent}% selesai`,
    status: task.status,
    priority: task.priority,
    children: [],
  }
}

function buildTree(project: Project, divisions: Division[], tasks: Task[]): TreeNode {
  const divisionNodes = divisions.map((division): TreeNode => {
    const divisionTasks = tasks.filter((task) => task.division_id === division.id)
    return {
      id: `division-${division.id}`,
      type: 'division',
      label: division.division_name,
      sublabel: `${divisionTasks.length} tugas · ${divisionTasks.filter((task) => task.status === 'done').length} selesai`,
      children: divisionTasks.map(taskNode),
    }
  })

  const unassignedTasks = tasks.filter((task) => !task.division_id)
  if (unassignedTasks.length > 0) {
    divisionNodes.push({
      id: 'division-unassigned',
      type: 'division',
      label: 'Belum ditetapkan ke divisi',
      sublabel: `${unassignedTasks.length} tugas`,
      children: unassignedTasks.map(taskNode),
    })
  }

  return {
    id: `project-${project.id}`,
    type: 'project',
    label: project.project_name,
    sublabel: `${project.progress_percent}% progres keseluruhan`,
    status: project.status,
    children: divisionNodes,
  }
}

export default function ProjectTreePage() {
  const user = useAuthStore((state) => state.user)
  const isStaff = user?.role === 'staff' || user?.role === 'subcontractor'
  const [projectId, setProjectId] = useState<number | ''>('')
  const [selected, setSelected] = useState<TreeNode | null>(null)

  const { data: projects = [], isLoading: projectsLoading } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => (await projectsApi.list()).data,
  })
  const { data: divisions = [], isLoading: divisionsLoading } = useQuery<Division[]>({
    queryKey: ['divisions', projectId],
    queryFn: async () => projectId ? (await projectsApi.divisions(Number(projectId))).data : [],
    enabled: Boolean(projectId),
  })
  const { data: tasks = [], isLoading: tasksLoading } = useQuery<Task[]>({
    queryKey: ['tasks', projectId, isStaff ? 'division' : 'all'],
    queryFn: async () => projectId ? (await tasksApi.list({
      project_id: Number(projectId),
      ...(isStaff ? { scope: 'division' } : {}),
    })).data : [],
    enabled: Boolean(projectId),
  })

  useEffect(() => {
    if (!projectId && projects.length > 0) setProjectId(projects[0].id)
  }, [projectId, projects])

  const project = projects.find((item) => item.id === Number(projectId))
  const tree = project ? buildTree(project, divisions, tasks) : null
  const loading = projectsLoading || (Boolean(projectId) && (divisionsLoading || tasksLoading))

  return (
    <div className="animate-in space-y-5">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <GitBranch size={22} className="text-brand-500" /> {isStaff ? 'Struktur Divisi' : 'Struktur Proyek'}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Setiap tugas disusun vertikal di bawah divisi penanggung jawab agar alur pekerjaan mudah ditelusuri.
          </p>
        </div>
        <select
          value={projectId}
          onChange={(event) => {
            setProjectId(event.target.value ? Number(event.target.value) : '')
            setSelected(null)
          }}
          className="input w-full text-sm sm:w-72"
        >
          <option value="">Pilih proyek</option>
          {projects.map((item) => <option key={item.id} value={item.id}>{item.project_name}</option>)}
        </select>
      </div>

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="card min-h-[520px] p-5 sm:p-7">
          {loading ? (
            <div className="flex min-h-[440px] items-center justify-center"><Loader2 size={30} className="animate-spin text-brand-500" /></div>
          ) : !tree ? (
            <div className="flex min-h-[440px] flex-col items-center justify-center text-center text-slate-400">
              <GitBranch size={46} className="mb-3 text-slate-300" />
              <p className="text-sm">{projects.length === 0 ? 'Belum ada proyek yang terhubung ke akun ini.' : 'Pilih proyek untuk melihat strukturnya.'}</p>
            </div>
          ) : (
            <div className="mx-auto max-w-4xl">
              <button
                type="button"
                onClick={() => setSelected(tree)}
                className="mx-auto flex w-full max-w-xl items-center gap-4 rounded-2xl bg-gradient-to-r from-sky-600 to-cyan-500 px-5 py-4 text-left text-white shadow-lg shadow-sky-500/20 transition hover:-translate-y-0.5"
              >
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/15"><Building2 size={22} /></span>
                <span className="min-w-0 flex-1">
                  <span className="block text-xs font-semibold uppercase tracking-widest text-sky-100">Proyek</span>
                  <span className="mt-0.5 block truncate font-bold">{tree.label}</span>
                  <span className="mt-1 block text-xs text-sky-100">{tree.sublabel}</span>
                </span>
              </button>

              <div className="mx-auto h-8 w-px bg-slate-300" />

              {tree.children.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-6 py-12 text-center">
                  <Users size={34} className="mx-auto mb-3 text-slate-300" />
                  <p className="font-semibold text-slate-700">Belum ada divisi atau tugas</p>
                  <p className="mt-1 text-sm text-slate-500">Data proyek akan muncul di sini setelah divisi dan tugas ditambahkan.</p>
                </div>
              ) : (
                <div className="space-y-7">
                  {tree.children.map((division) => (
                    <section key={division.id} className="rounded-2xl border border-indigo-100 bg-indigo-50/35 p-4 sm:p-5">
                      <button
                        type="button"
                        onClick={() => setSelected(division)}
                        className="flex w-full items-center gap-3 rounded-xl bg-indigo-600 px-4 py-3 text-left text-white shadow-sm transition hover:bg-indigo-700"
                      >
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/15"><Users size={18} /></span>
                        <span className="min-w-0 flex-1">
                          <span className="block text-[10px] font-semibold uppercase tracking-widest text-indigo-200">Divisi</span>
                          <span className="block truncate text-sm font-bold">{division.label}</span>
                        </span>
                        <span className="shrink-0 text-xs text-indigo-100">{division.sublabel}</span>
                      </button>

                      {division.children.length === 0 ? (
                        <div className="ml-4 border-l-2 border-dashed border-indigo-200 py-6 pl-6 text-sm text-slate-500">Belum ada tugas pada divisi ini.</div>
                      ) : (
                        <div className="ml-4 space-y-3 border-l-2 border-indigo-200 py-4 pl-6">
                          {division.children.map((task) => (
                            <button
                              key={task.id}
                              type="button"
                              onClick={() => setSelected(task)}
                              className="relative flex w-full items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left shadow-sm transition before:absolute before:-left-6 before:top-1/2 before:h-px before:w-6 before:bg-indigo-200 hover:border-brand-300 hover:shadow-md"
                            >
                              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500"><CheckSquare size={17} /></span>
                              <span className="min-w-0 flex-1">
                                <span className="block text-sm font-semibold text-slate-800">{task.label}</span>
                                <span className="mt-1 block text-xs text-slate-500">{task.sublabel}</span>
                              </span>
                              {task.status && <span className={`${statusBadgeClass(task.status)} badge hidden sm:inline-flex`}>{STATUS_LABELS[task.status] ?? task.status}</span>}
                            </button>
                          ))}
                        </div>
                      )}
                    </section>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <aside className="card p-5 xl:sticky xl:top-6">
          <h2 className="text-sm font-bold text-slate-900">Detail struktur</h2>
          {!selected ? (
            <div className="py-10 text-center">
              <AlertCircle size={28} className="mx-auto mb-3 text-slate-300" />
              <p className="text-sm leading-6 text-slate-500">Pilih proyek, divisi, atau tugas untuk melihat informasi ringkasnya.</p>
            </div>
          ) : (
            <div className="mt-4 space-y-4">
              <div>
                <p className="label">Jenis data</p>
                <div className="flex items-center gap-2 text-sm font-semibold capitalize text-slate-700">
                  {selected.type === 'project' && <Building2 size={15} className="text-brand-500" />}
                  {selected.type === 'division' && <Users size={15} className="text-indigo-500" />}
                  {selected.type === 'task' && <CheckSquare size={15} className="text-slate-500" />}
                  {selected.type === 'task' ? 'Tugas' : selected.type === 'division' ? 'Divisi' : 'Proyek'}
                </div>
              </div>
              <div><p className="label">Nama</p><p className="text-sm leading-6 text-slate-700">{selected.label}</p></div>
              {selected.status && <div><p className="label">Status</p><span className={`${statusBadgeClass(selected.status)} badge`}>{STATUS_LABELS[selected.status] ?? selected.status}</span></div>}
              {selected.priority && <div><p className="label">Prioritas</p><span className={`${priorityBadgeClass(selected.priority)} badge`}>{PRIORITY_LABELS[selected.priority] ?? selected.priority}</span></div>}
              {selected.sublabel && <div><p className="label">Ringkasan</p><p className="text-sm font-semibold text-slate-700">{selected.sublabel}</p></div>}
              {selected.children.length > 0 && (
                <div>
                  <p className="label">Item di bawahnya</p>
                  <div className="max-h-72 space-y-1 overflow-y-auto">
                    {selected.children.map((child) => (
                      <button key={child.id} type="button" onClick={() => setSelected(child)} className="w-full rounded-lg px-2 py-2 text-left text-xs leading-5 text-slate-600 transition hover:bg-slate-50 hover:text-brand-700">
                        ↓ {child.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
