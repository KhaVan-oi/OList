import { cn } from "cn"
import { ChevronDownIcon } from "lucide-react"
import type { ComponentProps } from "react"

function NativeSelect({ className, ...props }: ComponentProps<"select">) {
  return (
    <div className="relative inline-flex">
      <select
        data-slot="native-select"
        className={cn(
          "h-8 appearance-none rounded-lg border border-input bg-background py-1 pr-8 pl-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50",
          className,
        )}
        {...props}
      />
      <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
    </div>
  )
}

export { NativeSelect }
