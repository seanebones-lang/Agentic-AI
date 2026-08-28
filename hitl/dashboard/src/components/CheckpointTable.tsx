import React, { ChangeEvent } from 'react'
import { Checkpoint, CheckpointStatus } from '../types'
import { CheckCircle, XCircle, Clock, AlertTriangle as AlertTriangleIcon, Eye, Check, X } from 'lucide-react'
import { formatDistanceToNow, parseISO } from 'date-fns'

interface CheckpointTableProps {
  checkpoints: Checkpoint[]
  loading: boolean
  statusFilter: string
  onStatusFilterChange: (status: string) => void
  onView: (checkpoint: Checkpoint) => void
  onApprove: (checkpoint: Checkpoint, notes?: string) => void
  onReject: (checkpoint: Checkpoint, notes?: string) => void
  onEscalate: (checkpoint: Checkpoint) => void
}

const statusConfig: Record<CheckpointStatus, { label: string; badgeClass: string }> = {
  pending: { label: 'Pending', badgeClass: 'badge-pending' },
  approved: { label: 'Approved', badgeClass: 'badge-approved' },
  rejected: { label: 'Rejected', badgeClass: 'badge-rejected' },
  timeout: { label: 'Timeout', badgeClass: 'badge-timeout' },
  escalated: { label: 'Escalated', badgeClass: 'badge-escalated' },
  cancelled: { label: 'Cancelled', badgeClass: 'badge-cancelled' },
}

function StatusBadge({ status }: { status: CheckpointStatus }) {
  const config = statusConfig[status]
  
  const getIcon = () => {
    switch (status) {
      case 'pending':
      case 'timeout':
        return <Clock className="w-3 h-3" />
      case 'approved':
        return <CheckCircle className="w-3 h-3" />
      case 'rejected':
      case 'cancelled':
        return <XCircle className="w-3 h-3" />
      case 'escalated':
        return <AlertTriangleIcon className="w-3 h-3" />
      default:
        return <Clock className="w-3 h-3" />
    }
  }

  return (
    <span className={`badge ${config.badgeClass} flex items-center gap-1`}>
      {getIcon()}
      {config.label}
    </span>
  )
}

function LoadingRow() {
  return React.createElement(
    'tr', {},
    React.createElement('td', {}, React.createElement('div', { className: "skeleton h-4 w-24" })),
    React.createElement('td', {}, React.createElement('div', { className: "skeleton h-4 w-20" })),
    React.createElement('td', {}, React.createElement('div', { className: "skeleton h-4 w-28" })),
    React.createElement('td', {}, React.createElement('div', { className: "skeleton h-5 w-20" })),
    React.createElement('td', {}, React.createElement('div', { className: "skeleton h-4 w-32" })),
    React.createElement('td', {}, React.createElement('div', { className: "skeleton h-4 w-24" })),
    React.createElement('td', {}, React.createElement('div', { className: "skeleton h-4 w-16" })),
    React.createElement('td', {}, React.createElement('div', { className: "skeleton h-8 w-32" }))
  )
}

function EmptyState({ statusFilter }: { statusFilter: string }) {
  return (
    <div className="card">
      <div className="empty-state">
        <div className="empty-state-icon">
          <CheckCircle className="w-12 h-12" />
        </div>
        <h3 className="empty-state-title">No checkpoints found</h3>
        <p className="empty-state-message">
          {statusFilter !== 'all' 
            ? `No checkpoints with status "${statusFilter}"`
            : 'All checkpoints are resolved'}
        </p>
      </div>
    </div>
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
              <th>Status</th>
              <th>Created</th>
              <th>Expires</th>
              <th>Priority</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {[1, 2, 3, 4, 5].map(i => (
              <LoadingRow key={i} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
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

  if (loading && checkpoints.length === 0) {
    return <LoadingState />
  }

  if (checkpoints.length === 0) {
    return <EmptyState statusFilter={statusFilter} />
  }

  return (
    <div className="card">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <select
          className="input"
          style={{ width: 'auto', minWidth: '180px' }}
          value={statusFilter}
          onChange={(e: ChangeEvent<HTMLSelectElement>) => onStatusFilterChange(e.target.value)}
        >
          {statusOptions.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>Checkpoint ID</th>
              <th>Agent</th>
              <th>Reason</th>
              <th>Status</th>
              <th>Created</th>
              <th>Expires</th>
              <th>Priority</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {checkpoints.map(checkpoint => (
              <tr key={checkpoint.checkpoint_id}>
                <td className="font-mono text-sm">
                  {checkpoint.checkpoint_id.slice(0, 8)}...
                </td>
                <td>{checkpoint.agent_id}</td>
                <td>
                  <span className="badge badge-pending">{checkpoint.reason}</span>
                </td>
                <td>
                  <StatusBadge status={checkpoint.status} />
                </td>
                <td className="text-sm">
                  {formatDistanceToNow(parseISO(checkpoint.created_at), { addSuffix: true })}
                </td>
                <td className="text-sm">
                  {checkpoint.expires_at
                    ? formatDistanceToNow(parseISO(checkpoint.expires_at), { addSuffix: true })
                    : 'No expiry'}
                </td>
                <td>
                  <span className="badge" style={{ background: checkpoint.priority > 0 ? 'rgba(59, 130, 246, 0.15)' : 'transparent', color: checkpoint.priority > 0 ? 'var(--accent-primary)' : 'var(--fg-muted)' }}>
                    {checkpoint.priority > 0 ? `P${checkpoint.priority}` : 'Normal'}
                  </span>
                </td>
                <td>
                  <div className="flex items-center gap-2">
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => onView(checkpoint)}
                      title="View details"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    
                    {checkpoint.status === 'pending' || checkpoint.status === 'escalated' ? (
                      <>
                        <button
                          className="btn btn-success btn-sm"
                          onClick={() => onApprove(checkpoint)}
                          title="Approve"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => onReject(checkpoint)}
                          title="Reject"
                        >
                          <X className="w-4 h-4" />
                        </button>
                        <button
                          className="btn btn-warning btn-sm"
                          onClick={() => onEscalate(checkpoint)}
                          title="Escalate"
                        >
                          <AlertTriangleIcon className="w-4 h-4" />
                        </button>
                      </>
                    ) : (
                      <span className="text-[var(--fg-muted)] text-xs">Resolved</span>
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