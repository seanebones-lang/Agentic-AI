import { useState, useEffect, useCallback } from 'react'
import { ChevronDown } from 'lucide-react'
import { Checkpoint, api } from './types'
import { CheckpointTable } from './components/CheckpointTable'
import { ToastContainer, ToastProvider, useToasts } from './components/Toast'
import { Header } from './components/Header'
import { StatsCards } from './components/StatsCards'

function AppContent() {
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [stats, setStats] = useState({ pending: 0, approved: 0, rejected: 0, escalated: 0 })
  const { toasts, addToast, removeToast } = useToasts()

  const ITEMS_PER_PAGE = 20

  const fetchCheckpoints = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      
      const params = new URLSearchParams({
        limit: ITEMS_PER_PAGE.toString(),
        offset: ((currentPage - 1) * ITEMS_PER_PAGE).toString(),
      })
      
      if (statusFilter !== 'all') {
        params.append('status', statusFilter)
      }
      if (searchQuery) {
        params.append('search', searchQuery)
      }

      const response = await api.get<{ checkpoints: Checkpoint[]; total: number }>(`/hitl/checkpoints?${params}`)
      setCheckpoints(response.checkpoints)
      setTotalPages(Math.ceil(response.total / ITEMS_PER_PAGE))
    } catch (err) {
      setError('Failed to fetch checkpoints')
      addToast({ type: 'error', title: 'Error', message: 'Failed to fetch checkpoints' })
    } finally {
      setLoading(false)
    }
  }, [currentPage, statusFilter, searchQuery, addToast])

  const fetchStats = useCallback(async () => {
    try {
      const response = await api.get<{ pending: number; approved: number; rejected: number; escalated: number }>('/hitl/checkpoints/stats')
      setStats(response)
    } catch (err) {
      console.error('Failed to fetch stats:', err)
    }
  }, [])

  useEffect(() => {
    fetchCheckpoints()
    fetchStats()
  }, [fetchCheckpoints, fetchStats])

  const handleApprove = async (checkpoint: Checkpoint, notes?: string) => {
    try {
      await api.post(`/hitl/checkpoints/${checkpoint.checkpoint_id}/resolve`, {
        approved: true,
        reviewer_id: 'current-user',
        reviewer_notes: notes,
      })
      addToast({ type: 'success', title: 'Approved', message: `Checkpoint ${checkpoint.checkpoint_id.slice(0, 8)} approved` })
      fetchCheckpoints()
      fetchStats()
    } catch (err) {
      addToast({ type: 'error', title: 'Error', message: 'Failed to approve checkpoint' })
    }
  }

  const handleReject = async (checkpoint: Checkpoint, notes?: string) => {
    try {
      await api.post(`/hitl/checkpoints/${checkpoint.checkpoint_id}/resolve`, {
        approved: false,
        reviewer_id: 'current-user',
        reviewer_notes: notes,
      })
      addToast({ type: 'success', title: 'Rejected', message: `Checkpoint ${checkpoint.checkpoint_id.slice(0, 8)} rejected` })
      fetchCheckpoints()
      fetchStats()
    } catch (err) {
      addToast({ type: 'error', title: 'Error', message: 'Failed to reject checkpoint' })
    }
  }

  const handleEscalate = async (checkpoint: Checkpoint) => {
    try {
      await api.post(`/hitl/checkpoints/${checkpoint.checkpoint_id}/escalate`)
      addToast({ type: 'warning', title: 'Escalated', message: 'Checkpoint escalated to next approver' })
      fetchCheckpoints()
      fetchStats()
    } catch (err) {
      addToast({ type: 'error', title: 'Error', message: 'Failed to escalate checkpoint' })
    }
  }

  const filteredCheckpoints = checkpoints

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <Header
        onRefresh={fetchCheckpoints}
        onSearchChange={setSearchQuery}
        searchQuery={searchQuery}
        loading={loading}
      />
      
      <main className="container py-6">
        <StatsCards stats={stats} />
        
        <div className="mt-6">
          <CheckpointTable
            checkpoints={filteredCheckpoints}
            loading={loading}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            onView={() => {}}
            onApprove={handleApprove}
            onReject={handleReject}
            onEscalate={handleEscalate}
          />
          
          {totalPages > 1 && (
            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setCurrentPage}
            />
          )}
        </div>
      </main>

      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </div>
  )
}

// Helper components
function Pagination({ currentPage, totalPages, onPageChange }: { currentPage: number; totalPages: number; onPageChange: (page: number) => void }) {
  const pages = Array.from({ length: totalPages }, (_, i) => i + 1)
  const visiblePages = pages.filter(page => 
    page === 1 || page === totalPages || 
    (page >= currentPage - 1 && page <= currentPage + 1)
  )

  return (
    <nav className="pagination" aria-label="Pagination">
      <button
        className="pagination-btn"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        aria-label="Previous page"
      >
        <ChevronDown className="w-4 h-4" style={{ transform: 'rotate(180deg)' }} />
      </button>
      
      {visiblePages.map((page, index) => (
        <React.Fragment key={page}>
          {index > 0 && visiblePages[index - 1] !== page - 1 && (
            <span className="px-2 text-[var(--fg-muted)]">...</span>
          )}
          <button
            className={`pagination-btn ${page === currentPage ? 'active' : ''}`}
            onClick={() => onPageChange(page)}
          >
            {page}
          </button>
        </React.Fragment>
      ))}
      
      <button
        className="pagination-btn"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        aria-label="Next page"
      >
        <ChevronDown className="w-4 h-4" />
      </button>
    </nav>
  )
}

function App() {
  return (
    <ToastProvider>
      <AppContent />
    </ToastProvider>
  )
}

export default App