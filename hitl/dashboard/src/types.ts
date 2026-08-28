export interface Checkpoint {
  checkpoint_id: string
  agent_id: string
  execution_id: string
  state_snapshot: Record<string, any>
  reason: string
  context: Record<string, any>
  question?: string
  options?: Record<string, any>
  status: CheckpointStatus
  priority: number
  created_at: string
  updated_at: string
  timeout_seconds: number
  expires_at?: string
  approved?: boolean
  reviewer_id?: string
  reviewer_notes?: string
  resolved_at?: string
  escalation_count: number
  escalation_policy?: string
  approval_chain: string[]
  current_approver_index: number
  audit_trail: AuditEntry[]
  metadata: Record<string, any>
}

export type CheckpointStatus = 
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'timeout'
  | 'escalated'
  | 'cancelled'

export interface AuditEntry {
  timestamp: string
  action: string
  user_id?: string
  details?: Record<string, any>
  checkpoint_status: string
}

export interface Toast {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message: string
}

export interface Stats {
  pending: number
  approved: number
  rejected: number
  escalated: number
}

export const api = {
  async get<T>(url: string): Promise<T> {
    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    return response.json()
  },

  async post<T>(url: string, data: any): Promise<T> {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    return response.json()
  },
}