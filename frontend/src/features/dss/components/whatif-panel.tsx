import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { QueryState } from '../../../components/ui'
import { Button } from '../../../components/ui/button.tsx'
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card.tsx'
import { Stat } from '../../../components/ui/stat.tsx'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../../components/ui/table.tsx'
import { money } from '../../../lib/format.ts'
import { ratio, signedPct, units } from '../format.ts'
import { DEFAULT_WHATIF, getDssWhatIf, type DssSelection, type WhatIfInputs } from '../services/dssApi.ts'

const FIELDS: { key: keyof WhatIfInputs; label: string; hint: string }[] = [
  { key: 'uplift', label: 'Cầu tăng (%)', hint: 'Mức tăng nhu cầu do khuyến mãi' },
  { key: 'discount', label: 'Giảm giá (%)', hint: 'Giảm trên giá niêm yết' },
  { key: 'margin', label: 'Biên lợi nhuận gộp (%)', hint: 'Trên giá niêm yết, trước khuyến mãi' },
  { key: 'loss', label: 'Tổn thất hàng dư (%)', hint: 'Phần giá vốn mất ở hàng không bán hết' },
]

const inputClass =
  'h-8 w-28 rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50'

function tone(value: number | null | undefined) {
  if (value == null) return ''
  if (value > 0.05) return 'text-emerald-600'
  if (value < -0.05) return 'text-destructive'
  return ''
}

function isValid(inputs: WhatIfInputs) {
  const ranges: Record<keyof WhatIfInputs, [number, number]> = {
    uplift: [0, 300],
    discount: [0, 60],
    margin: [1, 90],
    loss: [0, 100],
  }
  return (Object.keys(ranges) as (keyof WhatIfInputs)[]).every((key) => {
    const raw = inputs[key]
    if (raw.trim() === '') return false
    const value = Number(raw)
    return Number.isFinite(value) && value >= ranges[key][0] && value <= ranges[key][1]
  })
}

export function WhatIfPanel({
  selection,
  scopeLabel,
  applied,
  onApply,
}: {
  selection: DssSelection
  scopeLabel: string
  applied: WhatIfInputs
  onApply: (inputs: WhatIfInputs) => void
}) {
  const [draft, setDraft] = useState<WhatIfInputs>(applied)
  const dirty = (Object.keys(draft) as (keyof WhatIfInputs)[]).some((key) => draft[key] !== applied[key])

  const query = useQuery({
    queryKey: ['dss', 'whatif', selection, applied],
    queryFn: () => getDssWhatIf(selection, applied),
    enabled: selection.scope === 'total' || Boolean(selection.value),
  })
  const data = query.data

  return (
    <Card>
      <CardHeader>
        <CardTitle>Khuyến mãi (what-if) · {scopeLabel}</CardTitle>
        <p className="text-xs text-muted-foreground">
          Các ô dưới là giả định của người dùng, không suy ra từ dữ liệu vì kho không có thí nghiệm khuyến mãi. Phần
          dự báo và lượng đệm lấy từ mô hình ở trên (tính theo số món).
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          {FIELDS.map((field) => (
            <label key={field.key} className="space-y-1.5 text-xs text-muted-foreground" title={field.hint}>
              <span className="block">{field.label}</span>
              <input
                type="number"
                inputMode="decimal"
                className={inputClass}
                value={draft[field.key]}
                onChange={(event) => setDraft({ ...draft, [field.key]: event.target.value })}
              />
            </label>
          ))}
          <Button type="button" size="sm" disabled={!dirty || !isValid(draft)} onClick={() => onApply(draft)}>
            Tính lại
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              setDraft(DEFAULT_WHATIF)
              onApply(DEFAULT_WHATIF)
            }}
          >
            Mặc định
          </Button>
        </div>

        <QueryState loading={query.isLoading} error={query.error}>
          {data ? (
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Stat
                  label={`Cầu cơ sở ${data.month} (món)`}
                  value={units(data.baseline_forecast_units)}
                  detail={`Giá bán TB 3 tháng gần nhất: ${money(data.avg_price)} R$`}
                />
                <Stat
                  label="Cầu tăng tối thiểu để hòa vốn"
                  value={data.breakeven_uplift == null ? 'Không có' : ratio(data.breakeven_uplift)}
                  detail={
                    data.breakeven_uplift == null
                      ? 'Giảm giá không thấp hơn biên lợi nhuận'
                      : 'Công thức: giảm giá / (biên - giảm giá), chưa tính hàng dư'
                  }
                />
                <Stat
                  label="Tham chiếu quan sát: Black Friday 2017"
                  value={data.observed_event_uplift == null ? 'Trống' : signedPct(data.observed_event_uplift * 100)}
                  detail="Tháng 11/2017 so với trung bình 9 và 10/2017, đã lẫn xu hướng tăng"
                />
                <Stat
                  label="Lượng nhập khi khuyến mãi"
                  value={units(data.promo.promo_order_units)}
                  detail={`Không khuyến mãi: ${units(data.promo.baseline.order_units)} món`}
                />
              </div>

              <div>
                <p className="mb-2 text-sm font-semibold">Nếu khuyến mãi chỉ đạt một phần mức tăng cầu giả định</p>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Mức tăng cầu thực tế so với giả định</TableHead>
                      <TableHead className="text-right">Cầu (món)</TableHead>
                      <TableHead className="text-right">Bán được</TableHead>
                      <TableHead className="text-right">Hàng dư</TableHead>
                      <TableHead className="text-right">Thiếu hàng</TableHead>
                      <TableHead className="text-right">Lợi nhuận so với không khuyến mãi</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.promo.scenarios.map((row) => (
                      <TableRow key={row.realization}>
                        <TableCell className="font-medium">{`${Math.round(row.realization * 100)}%`}</TableCell>
                        <TableCell className="text-right tabular-nums">{units(row.demand_units)}</TableCell>
                        <TableCell className="text-right tabular-nums">{units(row.sold_units)}</TableCell>
                        <TableCell className="text-right tabular-nums">{units(row.leftover_units)}</TableCell>
                        <TableCell className="text-right tabular-nums">{units(row.shortfall_units)}</TableCell>
                        <TableCell className={`text-right tabular-nums ${tone(row.profit_change_pct)}`}>
                          {signedPct(row.profit_change_pct)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              <div>
                <p className="mb-2 text-sm font-semibold">
                  Độ nhạy: đổi lợi nhuận (%) theo mức tăng cầu và mức giảm giá, biên {Math.round(data.inputs.margin * 100)}%
                </p>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Giảm giá \ Cầu tăng</TableHead>
                      {data.sensitivity[0]?.cells.map((cell) => (
                        <TableHead key={cell.uplift} className="text-right">{`${Math.round(cell.uplift * 100)}%`}</TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.sensitivity.map((row) => (
                      <TableRow key={row.discount}>
                        <TableCell className="font-medium">{`${Math.round(row.discount * 100)}%`}</TableCell>
                        {row.cells.map((cell) => (
                          <TableCell key={cell.uplift} className={`text-right tabular-nums ${tone(cell.profit_change_pct)}`}>
                            {signedPct(cell.profit_change_pct)}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                <p className="mt-3 text-xs text-muted-foreground">{data.note}</p>
              </div>
            </div>
          ) : null}
        </QueryState>
      </CardContent>
    </Card>
  )
}
