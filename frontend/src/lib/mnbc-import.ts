const REQUIRED_MNBC_FILES = [
  '30_AI_Training_Dataset_Master.json',
  '30_AI_Knowledge_Graph.json',
  '30_AI_Instruction_Dataset.jsonl',
] as const

export async function prepareMnbcImportArchive(source: File): Promise<File> {
  if (!source.name.toLowerCase().endsWith('.zip')) {
    throw new Error('Dataset MNBC harus berupa file ZIP.')
  }

  const { default: JSZip } = await import('jszip')
  let inputZip: InstanceType<typeof JSZip>
  try {
    inputZip = await JSZip.loadAsync(source)
  } catch {
    throw new Error('File yang dipilih bukan ZIP yang valid.')
  }

  const outputZip = new JSZip()
  for (const filename of REQUIRED_MNBC_FILES) {
    const entry = inputZip.file(filename)
    if (!entry) {
      throw new Error(`Dataset MNBC tidak lengkap: ${filename} tidak ditemukan.`)
    }
    outputZip.file(filename, await entry.async('uint8array'))
  }

  const blob = await outputZip.generateAsync({
    type: 'blob',
    compression: 'DEFLATE',
    compressionOptions: { level: 6 },
  })
  return new File([blob], 'mnbc-import.zip', {
    type: 'application/zip',
    lastModified: Date.now(),
  })
}
