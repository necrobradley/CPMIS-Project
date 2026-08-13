import Image from 'next/image'

export default function BrandLoadingScreen() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_#e0f2fe_0,_#f8fafc_42%,_#f8fafc_100%)] px-6">
      <div className="w-full max-w-sm text-center" role="status" aria-live="polite">
        <div className="mx-auto mb-7 flex h-24 items-center justify-center rounded-3xl border border-slate-200/80 bg-white px-7 shadow-xl shadow-sky-950/10">
          <Image
            src="/brand/rencanix-logo.png"
            alt="Rencanix"
            width={420}
            height={130}
            className="h-auto w-full max-w-[260px] object-contain"
            priority
          />
        </div>
        <h1 className="text-xl font-bold tracking-tight text-slate-950">Menyiapkan ruang kerja proyek</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          Menyinkronkan data, alur kerja, dan kolaborasi tim Anda.
        </p>
        <div className="mx-auto mt-7 h-1.5 max-w-[240px] overflow-hidden rounded-full bg-slate-200">
          <div className="h-full w-2/5 animate-[loading_1.2s_ease-in-out_infinite] rounded-full bg-gradient-to-r from-sky-500 to-cyan-400" />
        </div>
        <span className="sr-only">Memuat aplikasi Rencanix</span>
      </div>
    </div>
  )
}
