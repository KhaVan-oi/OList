import { CircleAlertIcon } from "lucide-react"
import type { ReactNode } from "react"

import { Spinner } from "./spinner.tsx"

export function QueryState({
  loading,
  error,
  children,
}: {
  loading: boolean
  error: Error | null
  children: ReactNode
}) {
  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner />
        Đang đọc kho...
      </p>
    )
  }
  if (error) {
    return (
      <p className="flex items-start gap-2 text-sm text-destructive">
        <CircleAlertIcon className="mt-0.5 size-4 shrink-0" />
        <span>Không đọc được kho. {error.message}</span>
      </p>
    )
  }
  return children
}
