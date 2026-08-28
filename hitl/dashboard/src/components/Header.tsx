import { RefreshCw, Search, Bell, Settings, ChevronDown, CheckCircle, LogOut } from 'lucide-react'

interface HeaderProps {
  onRefresh: () => void
  onSearchChange: (query: string) => void
  searchQuery: string
  loading: boolean
}

export function Header({ onRefresh, onSearchChange, searchQuery, loading }: HeaderProps) {
  return (
    <header className="bg-[var(--bg-secondary)] border-b border-[var(--border-color)] sticky top-0 z-50">
      <div className="container">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--accent-primary)' }}>
                <CheckCircle className="w-5 h-5 text-white" />
              </div>
              <span className="font-bold text-xl">HITL Dashboard</span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="relative hidden md:block">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--fg-muted)]" />
              <input
                type="text"
                placeholder="Search checkpoints..."
                className="input pl-10 pr-4 w-64"
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
              />
            </div>

            <button
              className="btn btn-ghost btn-sm"
              onClick={onRefresh}
              disabled={loading}
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>

            <div className="dropdown">
              <button className="btn btn-ghost btn-sm" aria-label="Notifications">
                <Bell className="w-4 h-4" />
              </button>
              <div className="dropdown-menu">
                <div className="px-3 py-2 border-b border-[var(--border-color)] text-sm font-medium">
                  Notifications
                </div>
                <div className="py-2 text-center text-[var(--fg-muted)] text-sm">
                  No notifications
                </div>
              </div>
            </div>

            <div className="dropdown">
              <button className="btn btn-ghost btn-sm flex items-center gap-2" aria-label="User menu">
                <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'var(--accent-primary)' }}>
                  <span className="text-white text-sm font-medium">U</span>
                </div>
                <span className="hidden sm:block text-sm">User</span>
                <ChevronDown className="w-4 h-4" />
              </button>
              <div className="dropdown-menu">
                <div className="px-3 py-2 border-b border-[var(--border-color)]">
                  <p className="font-medium text-sm">Current User</p>
                  <p className="text-xs text-[var(--fg-muted)]">user@agentic-ai.com</p>
                </div>
                <button className="dropdown-item w-full justify-start">
                  <Settings className="w-4 h-4" />
                  Settings
                </button>
                <div className="dropdown-divider" />
                <button className="dropdown-item w-full justify-start text-[var(--accent-danger)]">
                  <LogOut className="w-4 h-4" />
                  Sign Out
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}