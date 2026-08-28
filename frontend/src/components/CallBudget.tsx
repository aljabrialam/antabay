export interface CallBudgetProps {
  callBudget: number | null
}

export function CallBudget({ callBudget }: CallBudgetProps) {
  return (
    <div className="console-sec">
      <div className="console-eyebrow">Call budget</div>
      <div className="constraint-value console-mono" data-testid="call-budget">
        {callBudget === null ? '—' : callBudget}
      </div>
    </div>
  )
}
