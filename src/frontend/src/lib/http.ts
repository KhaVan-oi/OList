export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  const body = (await response.json()) as T & { error?: string }
  if (!response.ok) {
    throw new Error(body.error || 'Không đọc được kho')
  }
  return body
}
