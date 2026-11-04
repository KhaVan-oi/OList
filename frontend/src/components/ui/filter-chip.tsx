import type { ComponentProps } from "react"

import { cn } from "@/lib/utils.ts"
import { Button } from "./button.tsx"

function FilterChip({ active = false, className, ...props }: ComponentProps<typeof Button> & { active?: boolean }) {
  return (
    <Button
      {...props}
      type="button"
      size="sm"
      variant={active ? "default" : "outline"}
      className={cn("rounded-full disabled:opacity-100", className)}
    />
  )
}

export { FilterChip }
