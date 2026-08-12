type ApiRecord = Record<string, unknown>


function isRecord(value: unknown): value is ApiRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}


function locationLabel(value: unknown): string {
  if (!Array.isArray(value)) return ''
  return value
    .filter((part) => part !== 'body' && part !== 'query')
    .map(String)
    .join('.')
}


export function apiDetailMessage(detail: unknown): string | null {
  if (typeof detail === 'string' && detail.trim()) return detail.trim()
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => apiDetailMessage(item))
      .filter((item): item is string => Boolean(item))
    return messages.length ? messages.join('; ') : null
  }
  if (!isRecord(detail)) return null

  const message = typeof detail.msg === 'string'
    ? detail.msg
    : typeof detail.message === 'string'
      ? detail.message
      : null
  if (message) {
    const location = locationLabel(detail.loc)
    return location ? `${location}: ${message}` : message
  }
  if ('detail' in detail) return apiDetailMessage(detail.detail)
  return null
}


export function apiErrorMessage(error: unknown, fallback: string): string {
  if (isRecord(error)) {
    const response = isRecord(error.response) ? error.response : null
    const data = response && isRecord(response.data) ? response.data : null
    const detail = data ? apiDetailMessage(data.detail) : null
    if (detail) return detail
    if (typeof error.message === 'string' && error.message.trim()) return error.message.trim()
  }
  if (error instanceof Error && error.message.trim()) return error.message.trim()
  return fallback
}
