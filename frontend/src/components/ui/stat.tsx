import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./card.tsx"

export function Stat({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <Card className="gap-1">
      <CardHeader className="gap-2">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-xl leading-none font-bold tracking-tight tabular-nums sm:text-2xl">{value}</CardTitle>
      </CardHeader>
      {detail && <CardContent className="text-xs text-muted-foreground">{detail}</CardContent>}
    </Card>
  )
}
