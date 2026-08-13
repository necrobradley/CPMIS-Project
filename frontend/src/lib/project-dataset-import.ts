const REQUIRED_PROJECT_FILES = [
  '30_AI_Training_Dataset_Master.json',
  '30_AI_Knowledge_Graph.json',
  '30_AI_Instruction_Dataset.jsonl',
] as const

const OPTIONAL_PROJECT_FILES = [
  'CPMIS_Demo_Features.json',
] as const

const SOURCE_DOCUMENT_MIME: Record<string, string> = {
  pdf: 'application/pdf',
  doc: 'application/msword',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  xls: 'application/vnd.ms-excel',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}

export async function prepareProjectDatasetArchive(source: File): Promise<File> {
  if (!source.name.toLowerCase().endsWith('.zip')) {
    throw new Error('Paket data proyek harus berupa file ZIP.')
  }

  const { default: JSZip } = await import('jszip')
  let inputZip: InstanceType<typeof JSZip>
  try {
    inputZip = await JSZip.loadAsync(source)
  } catch {
    throw new Error('File yang dipilih bukan ZIP yang valid.')
  }

  const outputZip = new JSZip()
  for (const filename of REQUIRED_PROJECT_FILES) {
    const entry = inputZip.file(filename)
    if (!entry) {
      throw new Error(`Paket data proyek tidak lengkap: ${filename} tidak ditemukan.`)
    }
    outputZip.file(filename, await entry.async('uint8array'))
  }
  for (const filename of OPTIONAL_PROJECT_FILES) {
    const entry = inputZip.file(filename)
    if (entry) outputZip.file(filename, await entry.async('uint8array'))
  }

  const blob = await outputZip.generateAsync({
    type: 'blob',
    compression: 'DEFLATE',
    compressionOptions: { level: 6 },
  })
  return new File([blob], 'project-dataset-import.zip', {
    type: 'application/zip',
    lastModified: Date.now(),
  })
}

export async function extractProjectSourceDocuments(source: File): Promise<File[]> {
  const { default: JSZip } = await import('jszip')
  const inputZip = await JSZip.loadAsync(source)
  const reserved = new Set<string>([...REQUIRED_PROJECT_FILES, ...OPTIONAL_PROJECT_FILES])
  const entries = Object.values(inputZip.files)
    .filter((entry) => !entry.dir && !reserved.has(entry.name))
    .filter((entry) => {
      const extension = entry.name.toLowerCase().split('.').pop() || ''
      return Boolean(SOURCE_DOCUMENT_MIME[extension])
    })
    .sort((a, b) => a.name.localeCompare(b.name))

  return Promise.all(entries.map(async (entry) => {
    const extension = entry.name.toLowerCase().split('.').pop() || ''
    const blob = await entry.async('blob')
    const filename = entry.name.split('/').pop() || entry.name
    return new File([blob], filename, {
      type: SOURCE_DOCUMENT_MIME[extension],
      lastModified: source.lastModified,
    })
  }))
}
