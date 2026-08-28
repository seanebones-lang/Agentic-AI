import { CheckCircle, XCircle, Clock, AlertTriangle } from 'lucide-react'

interface StatsCardsProps {
  stats: {
    pending: number
    approved: number
    rejected: number
    escalated: number
    total: number
  }
}

export function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    { label: 'Total', value: stats.total, icon: AlertTriangle, color: 'var(--fg-secondary)' },
    { label: 'Pending', value: stats.pending, icon: Clock, color: 'var(--accent-warning)' },
    { label: 'Approved', value: stats.approved, icon: CheckCircle, color: 'var(--accent-success)' },
    { label: 'Rejected', value: stats.rejected, icon: XCircle, color: 'var(--accent-error)' },
    { label: 'Escalated', value: stats.escalated, icon: AlertTriangle, color: 'var(--accent-info)' },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
      {cards.map((card, i) => {
        const Icon = card.icon
        return (
          <div key={i} className="card">
            <div className="card-content">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted">{card.label}</p>
                  <p className="text-2xl font-bold mt-1" style={{ color: card.color }}>{card.value}</p>
                </div>
                <div className="p-2 rounded-lg" style={{ backgroundColor: `${card.color}15` }}>
                  <Icon className="w-5 h-5" style={{ color: card.color }} />
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}