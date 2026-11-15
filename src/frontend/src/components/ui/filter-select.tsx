import type { ReactNode } from 'react'
import { NativeSelect } from './native-select.tsx'

const SELECT_CLASS = 'border-0 bg-transparent shadow-none focus-visible:ring-0'

/** Ô chọn trong thanh bộ lọc (kèm vạch ngăn bên trái, ẩn khi đứng đầu thanh). */
export function FilterSelect({
  id,
  label,
  value,
  onChange,
  minWidth = '6.5rem',
  children,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  minWidth?: string
  children: ReactNode
}) {
  return (
    <>
      <span className="h-5 w-px bg-border first:hidden" aria-hidden />
      <NativeSelect
        id={id}
        aria-label={label}
        className={SELECT_CLASS}
        style={{ minWidth }}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {children}
      </NativeSelect>
    </>
  )
}

/** Khung thanh bộ lọc: tự xuống dòng khi hẹp để không phải cuộn ngang. */
export const filterBarClass =
  'flex flex-wrap items-center gap-1 rounded-xl border border-border bg-card p-1 shadow-sm'
