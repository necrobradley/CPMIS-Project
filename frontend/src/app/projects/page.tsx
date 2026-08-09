'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projectsApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { Project } from '@/types'
import { formatCurrency, formatDate, statusBadgeClass, STATUS_LABELS } from '@/lib/utils'
import { Plus, Building2, MapPin, Calendar, DollarSign, Loader2, Search, X } from 'lucide-react'
import toast from 'react-hot-toast'

export default function ProjectsPage() {
  const qc = useQueryClient()
  const user = useAuthStore((state) => state.user)
  const isManagement = Boolean(user && ['admin', 'director', 'manager'].includes(user.role))
  const [showForm, setShowForm] = useState(false)
  const [search, setSearch] = useState('')
  const [form, setForm] = useState({
    project_name: '', description: '', location: '',
    contract_value: '', start_date: '', end_date: '',
  })

  const { data: projects = [], isLoading } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => (await projectsApi.list()).data,
  })

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => projectsApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      setShowForm(false)
      setForm({ project_name: '', description: '', location: '', contract_value: '', start_date: '', end_date: '' })
      toast.success('Proyek berhasil dibuat!')
    },
    onError: () => toast.error('Gagal membuat proyek'),
  })

  const filtered = projects.filter((p) =>
    p.project_name.toLowerCase().includes(search.toLowerCase()) ||
    (p.location ?? '').toLowerCase().includes(search.toLowerCase())
  )

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    createMutation.mutate({
      ...form,
      contract_value: form.contract_value ? Number(form.contract_value) : null,
      start_date: form.start_date || null,
      end_date: form.end_date || null,
    })
  }

  return (
    <div className="space-y-6 animate-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">{isManagement ? 'Proyek' : 'Proyek Saya'}</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {isManagement ? `${projects.length} proyek terdaftar` : `${projects.length} proyek terkait akun/divisi`}
          </p>
        </div>
        {isManagement && <button onClick={() => setShowForm(true)} className="btn-primary">
          <Plus size={16} /> Proyek Baru
        </button>}
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Cari proyek..." className="input pl-9 pr-8" />
        {search && <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"><X size={14} /></button>}
      </div>

      {/* Modal form */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg animate-in">
            <div className="p-6 border-b border-slate-100 flex items-center justify-between">
              <h2 className="font-semibold text-slate-900">Buat Proyek Baru</h2>
              <button onClick={() => setShowForm(false)} className="btn-ghost p-1.5"><X size={16} /></button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="label">Nama Proyek *</label>
                <input required value={form.project_name} onChange={(e) => setForm({ ...form, project_name: e.target.value })}
                  className="input" placeholder="Gedung Kantor XYZ" />
              </div>
              <div>
                <label className="label">Deskripsi</label>
                <textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="input resize-none" placeholder="Deskripsi singkat proyek..." />
              </div>
              <div>
                <label className="label">Lokasi</label>
                <input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })}
                  className="input" placeholder="Jl. Sudirman, Jakarta" />
              </div>
              <div>
                <label className="label">Nilai Kontrak (Rp)</label>
                <input type="number" value={form.contract_value} onChange={(e) => setForm({ ...form, contract_value: e.target.value })}
                  className="input" placeholder="85000000000" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Tanggal Mulai</label>
                  <input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} className="input" />
                </div>
                <div>
                  <label className="label">Tanggal Selesai</label>
                  <input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} className="input" />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowForm(false)} className="btn-secondary flex-1 justify-center">Batal</button>
                <button type="submit" disabled={createMutation.isPending} className="btn-primary flex-1 justify-center">
                  {createMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
                  Buat Proyek
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Projects grid */}
      {isLoading ? (
        <div className="flex justify-center py-20"><Loader2 size={28} className="animate-spin text-brand-500" /></div>
      ) : filtered.length === 0 ? (
        <div className="card p-16 text-center">
          <Building2 size={40} className="text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500">
            {search ? 'Proyek tidak ditemukan' : isManagement ? 'Belum ada proyek. Buat proyek pertama!' : 'Belum ada proyek yang terkait dengan akun/divisi ini'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5 stagger">
          {filtered.map((p) => (
            <a key={p.id} href={`/projects/${p.id}`}
              className="card card-hover p-5 flex flex-col gap-4 group animate-in">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-brand-100 rounded-xl flex items-center justify-center">
                    <Building2 size={18} className="text-brand-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-slate-800 group-hover:text-brand-600 transition leading-tight line-clamp-1">
                      {p.project_name}
                    </h3>
                    <span className={statusBadgeClass(p.status)}>{STATUS_LABELS[p.status]}</span>
                  </div>
                </div>
              </div>

              {p.description && (
                <p className="text-sm text-slate-500 line-clamp-2">{p.description}</p>
              )}

              <div className="space-y-2 text-xs text-slate-500">
                {p.location && (
                  <div className="flex items-center gap-2">
                    <MapPin size={12} className="text-slate-400" /> {p.location}
                  </div>
                )}
                {p.contract_value && (
                  <div className="flex items-center gap-2">
                    <DollarSign size={12} className="text-slate-400" /> {formatCurrency(p.contract_value)}
                  </div>
                )}
                {(p.start_date || p.end_date) && (
                  <div className="flex items-center gap-2">
                    <Calendar size={12} className="text-slate-400" />
                    {formatDate(p.start_date)} — {formatDate(p.end_date)}
                  </div>
                )}
              </div>

              {/* Progress bar */}
              <div>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-slate-500">Progress</span>
                  <span className="font-semibold text-slate-700">{p.progress_percent}%</span>
                </div>
                <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-brand-500 rounded-full transition-all duration-500"
                    style={{ width: `${p.progress_percent}%` }} />
                </div>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
