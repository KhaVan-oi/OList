import type { ReactNode } from 'react'

export function PageHeading({
  title,
  description,
  actions,
}: {
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0 flex-1">
        <h1 className="text-[26px] leading-tight font-bold tracking-[0.2px]">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions ? <div className="shrink-0">{actions}</div> : null}
    </div>
  )
}
