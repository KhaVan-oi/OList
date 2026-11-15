import { getJson } from '../../../lib/http.ts'
import type { ListResponse } from '../../../types/api.ts'

export function getSalesTime(path: string) {
  return getJson<ListResponse>(path)
}
