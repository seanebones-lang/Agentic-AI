import { CheckCircle, XCircle, Clock, AlertTriangle } from 'lucide-react'

interface StatsCardsProps {
  stats: {
    pending: number
    approved: number
    rejected: number
    escalated: number
  }
}

const statCards = [
  {
    key: 'pending',
    label: 'Pending',
    icon: Clock,
    color: 'rgba(245, 158, 11, 0.15)',
    iconColor: 'var(--accent-warning)',
    borderColor: 'rgba(245, 158, 11, 0.3)',
  },
  {
    key: 'approved',
    label: 'Approved',
    icon: CheckCircle,
    color: 'rgba(16, 185, 129, 0.15)',
    iconColor: 'var(--accent-success)',
    borderColor: 'rgba(16, 185, 129, 0.3)',
  },
  {
    key: 'rejected',
    label: 'Rejected',
    icon: XCircle,
    color: 'rgba(239, 68, 68, 0.15)',
    iconColor: 'var(--accent-danger)',
    borderColor: 'rgba(239, 68, 68, 0.3)',
  },
  {
    key: 'escalated',
    label: 'Escalated',
    icon: AlertTriangle,
    color: 'rgba(239, 68, 68, 0.15)',
    iconColor: 'var(--accent-danger)',
    borderColor: 'rgba(239, 68, 68, 0.3)',
  },
]

export function StatsCards({ stats }: StatsCardsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {statCards.map(card => (
        <div
          key={card.key}
          className="card p-6"
          style={{
            background: card.color,
            borderColor: card.borderColor,
          }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-[var(--fg-secondary)]">
                {card.label}
              </p>
              <p className="text-3xl font-bold text-[var(--fg-primary)] mt-1">
                {stats[card.key as keyof typeof stats]}
              </p>
            </div>
            <div
              className="w-12 h-12 rounded-lg flex items-center justify-center"
              style={{ background: card.iconColor + '20' }}
            >
              <card.icon className="w-6 h-6" style={{ color: card.iconColor }} />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}