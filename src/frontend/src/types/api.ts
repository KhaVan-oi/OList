export type Row = Record<string, string | number | boolean | null>

export type ListResponse = {
  status: string
  data: Row[]
  note?: string
  error?: string
  categories?: Row[]
}
