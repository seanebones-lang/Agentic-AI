export interface Checkpoint {
  checkpoint_id: string;
  agent_id: string;
  execution_id: string;
  state_snapshot: Record<string, any>;
  reason: string;
  context: Record<string, any>;
  question?: string;
  options: Record<string, any>;
  metadata: Record<string, any>;
  created_at: string;
  expires_at: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution: 'approved' | 'rejected' | 'escalated' | 'timeout' | 'cancelled' | null;
  resolution_notes: string | null;
  status: CheckpointStatus;
  priority: number;
  approval_chain: string[];
  current_approver_index: number;
  escalation_count: number;
  audit_trail: AuditEntry[];
}

export type CheckpointStatus = 
  | 'pending' 
  | 'approved' 
  | 'rejected' 
  | 'escalated' 
  | 'timeout' 
  | 'cancelled';

export interface AuditEntry {
  action: string;
  timestamp: string;
  actor: string | null;
  details: Record<string, any>;
}

export interface CheckpointStats {
  pending: number;
  approved: number;
  rejected: number;
  escalated: number;
  total: number;
}

export interface Api {
  baseUrl: string;
  getCheckpoints: () => Promise<Checkpoint[]>;
  getCheckpointStats: () => Promise<CheckpointStats>;
  getCheckpoint: (id: string) => Promise<Checkpoint>;
  approveCheckpoint: (id: string, approved: boolean, notes?: string) => Promise<void>;
  rejectCheckpoint: (id: string, notes?: string) => Promise<void>;
  escalateCheckpoint: (id: string) => Promise<void>;
}

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;
}