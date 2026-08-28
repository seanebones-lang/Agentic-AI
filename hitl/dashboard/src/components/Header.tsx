import React from 'react'
import { RefreshCw, Search, Bell, Settings, ChevronDown, CheckCircle, LogOut } from 'lucide-react'

interface HeaderProps {
  onRefresh: () => void
  onSearchChange: (value: string) => void
  searchValue: string
  onSettingsClick: () => void
  onProfileClick: () => void
  onLogoutClick: () => void
  pendingCount: number
}

export function Header({
  onRefresh,
  onSearchChange,
  searchValue,
  onSettingsClick,
  onProfileClick,
  onLogoutClick,
  pendingCount,
}: HeaderProps) {
  return (
    <header className="bg-secondary border-b border-primary sticky top-0 z-40">
      <div className="flex items-center justify-between h-16 px-4 sm:px-6">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-semibold text-fg-primary">HITL Dashboard</h1>
          <div className="hidden sm:block relative w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
            <input
              type="search"
              value={searchValue}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search checkpoints..."
              className="input pl-10 w-full"
              aria-label="Search checkpoints"
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onRefresh}
            className="btn btn-ghost btn-icon relative"
            aria-label="Refresh"
            title="Refresh"
          >
            <RefreshCw className="w-5 h-5" />
            {pendingCount > 0 && (
              <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-white text-xs flex items-center justify-center">
                {pendingCount > 9 ? '9+' : pendingCount}
              </span>
            )}
          </button>

          <button
            onClick={onSettingsClick}
            className="btn btn-ghost btn-icon"
            aria-label="Settings"
            title="Settings"
          >
            <Settings className="w-5 h-5" />
          </button>

          <div className="dropdown">
            <button
              onClick={onProfileClick}
              className="btn btn-ghost flex items-center gap-2"
              aria-label="User menu"
            >
              <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
                <CheckCircle className="w-5 h-5 text-blue-500" />
              </div>
              <span className="hidden sm:block text-sm font-medium">Operator</span>
              <ChevronDown className="w-4 h-4 text-muted" />
            </button>
            <div className="dropdown-menu">
              <div className="px-3 py-2 border-b border-primary">
                <p className="text-sm font-medium">Operator</p>
                <p className="text-xs text-muted">operator@company.com</p>
              </div>
              <button className="dropdown-item w-full" onClick={onSettingsClick}>
                <Settings className="w-4 h-4" />
                Settings
              </button>
              <div className="dropdown-divider" />
              <button className="dropdown-item w-full danger" onClick={onLogoutClick}>
                <LogOut className="w-4 h-4" />
                Logout
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}