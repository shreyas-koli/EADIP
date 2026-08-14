import { fetchApi } from "./client"

export interface DiscoveryExecutionRequest {
  warehouse_id: number
}

export interface AgentExecution {
  agent_name: string
  status: "WAITING" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED"
  started_at: string
  finished_at?: string
  duration_ms?: number
  wave: number
  error?: string
}

export interface DiscoverySession {
  session_id: string
  warehouse_id: number
  started_at: string
  finished_at?: string
  total_duration_ms?: number
  status: "COMPLETED" | "FAILED" | "RUNNING"
  recommendations?: Record<string, unknown>
  agent_executions?: AgentExecution[]
}

export interface DiscoveryHistoryResponse {
  session_id: string
  warehouse_id: number
  started_at: string
  finished_at?: string
  status: "COMPLETED" | "FAILED" | "RUNNING"
  total_duration_ms?: number
}

export interface PaginatedDiscoveryHistory {
  items: DiscoveryHistoryResponse[]
  total: number
  page: number
  page_size: number
}



export const discoveryApi = {
  execute: (data: DiscoveryExecutionRequest) =>
    fetchApi<DiscoverySession>("/discovery/execute", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getHistory: (warehouseId: number, page: number = 1, pageSize: number = 10, status?: string) => {
    let url = `/warehouses/${warehouseId}/history?page=${page}&page_size=${pageSize}`
    if (status && status !== "ALL") {
      url += `&status=${status}`
    }
    return fetchApi<PaginatedDiscoveryHistory>(url, {
      method: "GET",
    })
  },

  getSession: (warehouseId: number, sessionId: string) =>
    fetchApi<DiscoverySession>(`/warehouses/${warehouseId}/history/${sessionId}`, {
      method: "GET",
    }),
}
