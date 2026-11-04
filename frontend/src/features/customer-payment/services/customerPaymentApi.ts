import { getJson } from '../../../lib/http.ts'
import type { ListResponse } from '../../../types/api.ts'

export function getFrequency() {
  return getJson<ListResponse>('/api/customer-payment/frequency')
}
