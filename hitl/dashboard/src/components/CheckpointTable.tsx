import React, { ChangeEvent } from 'react'
import { Checkpoint, CheckpointStatus } from '../types'
import { CheckCircle, XCircle, Clock, AlertTriangle as AlertTriangleIcon, Eye, Check, X } from 'lucide-react'

interface CheckpointTableProps {
  checkpoints: Checkpoint[]
  loading: boolean
  statusFilter: string
  onStatusFilterChange: (status: string) => void
  onView: (checkpoint: Checkpoint) => void
  onApprove: (checkpoint: Checkpoint) => void
  onReject: (checkpoint: Checkpoint) => void
  onEscalate: (checkpoint: Checkpoint) => void
}

const statusConfig: Record<CheckpointStatus, { label: string; color: string; Icon: React.ComponentType<{ className?: string }> }> = {
  pending: { label: 'Pending', color: 'var(--accent-warning)', Icon: Clock },
  approved: { label: 'Approved', color: 'var(--accent-success)', Icon: CheckCircle },
  rejected: { label: 'Rejected', color: 'var(--accent-error)', Icon: XCircle },
  escalated: { label: 'Escalated', color: 'var(--accent-info)', Icon: AlertTriangleIcon },
  timeout: { label: 'Timeout', color: 'var(--fg-muted)', Icon: Clock },
  cancelled: { label: 'Cancelled', color: 'var(--fg-secondary)', Icon: XCircle },
}

function StatusBadge({ status }: { status: CheckpointStatus }) {
  const config = statusConfig[status]
  const Icon = config.Icon

  return (
    <span className="badge" style={{ backgroundColor: `${config.color}15`, color: config.color }}>
      <Icon className="w-3 h-3" />
      {config.label}
    </span>
  )
}

function LoadingState() {
  return (
    <div className="card">
      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Agent</th>
              <th>Reason</th>
              <th>Question</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 5 }).map((_, i) => (
              <tr key={i}>
                <td><div className="skeleton h-4 w-24"></div></td>
                <td><div className="skeleton h-4 w-20"></div></td>
                <td><div className="skeleton h-4 w-28"></div></td>
                <td><div className="skeleton h-4 w-32"></div></td>
                <td><div className="skeleton h-4 w-20"></div></td>
                <td><div className="skeleton h-4 w-16"></div></td>
                <td><div className="skeleton h-4 w-24"></div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="card">
      <div className="empty-state">
        <svg className="empty-state-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p className="empty-state-title">No Checkpoints Found</p>
        <p className="empty-state-description">
          There are no checkpoints matching your current filters.
        </p>
      </div>
    </div>
  )
}

function formatTimestamp(timestamp: string | null): string {
  if (!timestamp) return '—'
  try {
    const date = new Date(timestamp)
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return '—'
  }
}

export function CheckpointTable({
  checkpoints,
  loading,
  statusFilter,
  onStatusFilterChange,
  onView,
  onApprove,
  onReject,
  onEscalate,
}: CheckpointTableProps) {
  const statusOptions = [
    { value: 'all', label: 'All Statuses' },
    { value: 'pending', label: 'Pending' },
    { value: 'approved', label: 'Approved' },
    { value: 'rejected', label: 'Rejected' },
    { value: 'escalated', label: 'Escalated' },
    { value: 'timeout', label: 'Timeout' },
    { value: 'cancelled', label: 'Cancelled' },
  ]

  const filteredCheckpoints = statusFilter === 'all'
    ? checkpoints
    : checkpoints.filter(c => c.status === statusFilter)

  if (loading) {
    return <LoadingState />
  }

  if (filteredCheckpoints.length === 0) {
    return <EmptyState />
  }

  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title">Checkpoints ({filteredCheckpoints.length})</h2>
        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => onStatusFilterChange(e.target.value)}
            className="input select w-auto"
            aria-label="Filter by status"
          >
            {statusOptions.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="table-container scrollbar-thin">
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Agent</th>
              <th>Reason</th>
              <th>Question</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredCheckpoints.map(checkpoint => (
              <tr key={checkpoint.checkpoint_id}>
                <td className="font-mono text-xs truncate max-w-[120px]">{checkpoint.checkpoint_id.slice(0, 12)}...</td>
                <td className="font-mono text-xs truncate max-w-[100px]">{checkpoint.agent_id}</td>
                <td>
                  <span className="badge" style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--fg-secondary)' }}>
                    {checkpoint.reason}
                  </span>
                </td>
                <td className="truncate max-w-[300px] text-sm">
                  {checkpoint.question || '—'}
                </td>
                <td><StatusBadge status={checkpoint.status} /></td>
                <td className="text-xs text-muted">{formatTimestamp(checkpoint.created_at)}</td>
                <td>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => onView(checkpoint)}
                      className="btn btn-ghost btn-sm btn-icon"
                      aria-label={`View checkpoint ${checkpoint.checkpoint_id.slice(0, 8)}`}
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    {checkpoint.status === 'pending' && (
                      <>
                        <button
                          onClick={() => onApprove(checkpoint)}
                          className="btn btn-success btn-sm"
                          aria-label="Approve"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => onReject(checkpoint)}
                          className="btn btn-danger btn-sm"
                          aria-label="Reject"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </>
                    )}
                    {checkpoint.status === 'pending' && (
                      <button
                        onClick={() => onEscalate(checkpoint)}
                        className="btn btn-ghost btn-sm btn-icon"
                        aria-label="Escalate"
                        title="Escalate"
                      >
                        <AlertTriangleIcon className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}