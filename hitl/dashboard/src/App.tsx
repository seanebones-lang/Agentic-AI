import { useState, useEffect, useCallback } from 'react'
import { Checkpoint, CheckpointStats } from './types'
import { CheckpointTable } from './components/CheckpointTable'
import { StatsCards } from './components/StatsCards'
import { Header } from './components/Header'
import { ToastProvider, useToasts } from './components/Toast'

const API_BASE = '/api'

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

function CheckpointList() {
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([])
  const [stats, setStats] = useState<CheckpointStats>({ pending: 0, approved: 0, rejected: 0, escalated: 0, total: 0 })
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('all')
  const [searchValue, setSearchValue] = useState('')
  const [selectedCheckpoint, setSelectedCheckpoint] = useState<Checkpoint | null>(null)
  const { addToast } = useToasts()

  const loadCheckpoints = useCallback(async () => {
    try {
      const [checkpointsData, statsData] = await Promise.all([
        fetchJson<Checkpoint[]>(`${API_BASE}/hitl/checkpoints`),
        fetchJson<CheckpointStats>(`${API_BASE}/hitl/checkpoints/stats`),
      ])
      setCheckpoints(checkpointsData)
      setStats(statsData)
    } catch (e) {
      addToast({ type: 'error', title: 'Failed to load checkpoints', message: String(e) })
    } finally {
      setLoading(false)
    }
  }, [addToast])

  const loadStats = useCallback(async () => {
    try {
      const statsData = await fetchJson<CheckpointStats>(`${API_BASE}/hitl/checkpoints/stats`)
      setStats(statsData)
    } catch {
      // Ignore stats errors
    }
  }, [])

  useEffect(() => {
    loadCheckpoints()
    const interval = setInterval(loadStats, 30000)
    return () => clearInterval(interval)
  }, [loadCheckpoints, loadStats])

  const handleApprove = async (checkpoint: Checkpoint) => {
    try {
      await fetchJson(`${API_BASE}/hitl/checkpoints/${checkpoint.checkpoint_id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ checkpoint_id: checkpoint.checkpoint_id, approved: true }),
      })
      addToast({ type: 'success', title: 'Checkpoint approved' })
      loadCheckpoints()
    } catch (e) {
      addToast({ type: 'error', title: 'Failed to approve', message: String(e) })
    }
  }

  const handleReject = async (checkpoint: Checkpoint) => {
    const notes = prompt('Rejection reason (optional):')
    try {
      await fetchJson(`${API_BASE}/hitl/checkpoints/${checkpoint.checkpoint_id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ checkpoint_id: checkpoint.checkpoint_id, approved: false, reviewer_notes: notes }),
      })
      addToast({ type: 'success', title: 'Checkpoint rejected' })
      loadCheckpoints()
    } catch (e) {
      addToast({ type: 'error', title: 'Failed to reject', message: String(e) })
    }
  }

  const handleEscalate = async (checkpoint: Checkpoint) => {
    try {
      await fetchJson(`${API_BASE}/hitl/checkpoints/${checkpoint.checkpoint_id}/escalate`, {
        method: 'POST',
      })
      addToast({ type: 'warning', title: 'Checkpoint escalated' })
      loadCheckpoints()
    } catch (e) {
      addToast({ type: 'error', title: 'Failed to escalate', message: String(e) })
    }
  }

  const handleView = (checkpoint: Checkpoint) => {
    setSelectedCheckpoint(checkpoint)
  }

  const handleCloseModal = () => {
    setSelectedCheckpoint(null)
  }

  return (
    <div className="flex-1 p-4 sm:p-6 lg:p-8 overflow-auto">
      <div className="max-w-7xl mx-auto space-y-6">
        <Header
          onRefresh={loadCheckpoints}
          onSearchChange={setSearchValue}
          searchValue={searchValue}
          onSettingsClick={() => addToast({ type: 'info', title: 'Settings', message: 'Not implemented yet' })}
          onProfileClick={() => {}}
          onLogoutClick={() => addToast({ type: 'info', title: 'Logout', message: 'Not implemented yet' })}
          pendingCount={stats.pending}
        />

        <StatsCards stats={stats} />

        <CheckpointTable
          checkpoints={checkpoints}
          loading={loading}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          onView={handleView}
          onApprove={handleApprove}
          onReject={handleReject}
          onEscalate={handleEscalate}
        />
      </div>

      {selectedCheckpoint && (
        <CheckpointDetailModal
          checkpoint={selectedCheckpoint}
          onClose={handleCloseModal}
          onApprove={handleApprove}
          onReject={handleReject}
          onEscalate={handleEscalate}
        />
      )}
    </div>
  )
}

function CheckpointDetailModal({
  checkpoint,
  onClose,
  onApprove,
  onReject,
  onEscalate,
}: {
  checkpoint: Checkpoint
  onClose: () => void
  onApprove: (c: Checkpoint) => void
  onReject: (c: Checkpoint) => void
  onEscalate: (c: Checkpoint) => void
}) {
  const statusConfig: Record<string, { label: string; color: string }> = {
    pending: { label: 'Pending', color: 'var(--accent-warning)' },
    approved: { label: 'Approved', color: 'var(--accent-success)' },
    rejected: { label: 'Rejected', color: 'var(--accent-error)' },
    escalated: { label: 'Escalated', color: 'var(--accent-info)' },
    timeout: { label: 'Timeout', color: 'var(--fg-muted)' },
    cancelled: { label: 'Cancelled', color: 'var(--fg-secondary)' },
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={onClose}>
      <div className="card w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="card-header">
          <h2 className="card-title">Checkpoint Details</h2>
          <button onClick={onClose} className="btn btn-ghost btn-icon" aria-label="Close">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        <div className="card-content overflow-y-auto">
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Checkpoint ID</label>
                <p className="font-mono text-sm break-all">{checkpoint.checkpoint_id}</p>
              </div>
              <div>
                <label className="label">Agent ID</label>
                <p className="font-mono text-sm">{checkpoint.agent_id}</p>
              </div>
              <div>
                <label className="label">Execution ID</label>
                <p className="font-mono text-sm break-all">{checkpoint.execution_id}</p>
              </div>
              <div>
                <label className="label">Status</label>
                <span className="badge" style={{ backgroundColor: `${statusConfig[checkpoint.status]?.color}15`, color: statusConfig[checkpoint.status]?.color }}>
                  {statusConfig[checkpoint.status]?.label}
                </span>
              </div>
              <div>
                <label className="label">Reason</label>
                <span className="badge" style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--fg-secondary)' }}>
                  {checkpoint.reason}
                </span>
              </div>
              <div>
                <label className="label">Priority</label>
                <p className="text-sm">{checkpoint.priority}</p>
              </div>
              <div>
                <label className="label">Created</label>
                <p className="text-sm">{new Date(checkpoint.created_at).toLocaleString()}</p>
              </div>
              <div>
                <label className="label">Expires</label>
                <p className="text-sm">{checkpoint.expires_at ? new Date(checkpoint.expires_at).toLocaleString() : 'Never'}</p>
              </div>
              {checkpoint.resolved_at && (
                <div>
                  <label className="label">Resolved</label>
                  <p className="text-sm">{new Date(checkpoint.resolved_at).toLocaleString()}</p>
                </div>
              )}
              {checkpoint.resolved_by && (
                <div>
                  <label className="label">Resolved By</label>
                  <p className="text-sm">{checkpoint.resolved_by}</p>
                </div>
              )}
            </div>

            <div>
              <label className="label">Question</label>
              <p className="text-sm whitespace-pre-wrap bg-primary p-3 rounded border border-primary">{checkpoint.question || '—'}</p>
            </div>

            <div>
              <label className="label">Context</label>
              <pre className="text-xs bg-primary p-3 rounded border border-primary overflow-auto max-h-64">{JSON.stringify(checkpoint.context, null, 2)}</pre>
            </div>

            <div>
              <label className="label">State Snapshot</label>
              <pre className="text-xs bg-primary p-3 rounded border border-primary overflow-auto max-h-64">{JSON.stringify(checkpoint.state_snapshot, null, 2)}</pre>
            </div>

            <div>
              <label className="label">Options</label>
              <pre className="text-xs bg-primary p-3 rounded border border-primary overflow-auto max-h-48">{JSON.stringify(checkpoint.options, null, 2)}</pre>
            </div>

            <div>
              <label className="label">Audit Trail</label>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {checkpoint.audit_trail.map((entry, i) => (
                  <div key={i} className="text-xs bg-primary p-3 rounded border border-primary">
                    <div className="flex items-center gap-2 text-muted">
                      <span className="font-mono">{entry.timestamp}</span>
                      <span className="font-medium">{entry.action}</span>
                      {entry.actor && <span className="text-blue-400">by {entry.actor}</span>}
                    </div>
                    {Object.keys(entry.details).length > 0 && (
                      <pre className="mt-1 text-xs opacity-70">{JSON.stringify(entry.details, null, 2)}</pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
        {checkpoint.status === 'pending' && (
          <div className="card-header border-t">
            <div className="flex gap-2 justify-end">
              <button onClick={() => { onEscalate(checkpoint); onClose(); }} className="btn btn-ghost">Escalate</button>
              <button onClick={() => { onReject(checkpoint); onClose(); }} className="btn btn-danger">Reject</button>
              <button onClick={() => { onApprove(checkpoint); onClose(); }} className="btn btn-primary">Approve</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function App() {
  return (
    <ToastProvider>
      <div className="layout min-h-screen">
        <main className="main-content">
          <CheckpointList />
        </main>
      </div>
    </ToastProvider>
  )
}

export default App