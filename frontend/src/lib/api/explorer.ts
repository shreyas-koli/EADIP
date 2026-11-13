import { fetchApi } from "./client"

export interface DatabaseSchema {
  name: string
}

export interface DatabaseTable {
  name: string
  schema_name: string
  estimated_row_count: number
}

export interface DatabaseColumn {
  name: string
  data_type: string
  nullable: boolean
  position: number
  is_primary_key: boolean
  foreign_key?: {
    referred_table: string
    referred_schema: string
  }
}

export interface RowDataResponse {
  columns: string[]
  rows: (string | number | boolean | null)[][]
  limit: number
  offset: number
  returned_rows: number
  total_rows: number
  is_estimated_total: boolean
}

export interface QueryResult {
  columns: string[]
  rows: (string | number | boolean | null)[][]
  returned_rows: number
  execution_time_ms: number
  truncated: boolean
}

export interface ChatMessage {
  role: string
  content: string
}

export type AIProviderId = "openai" | "gemini" | "ollama"

export interface AssistantRequest {
  messages: ChatMessage[]
  schema_name?: string
  table_name?: string
  provider?: AIProviderId
}

export interface AssistantResponse {
  response: string
  provider_used: string
}

export interface ProviderStatus {
  id: AIProviderId
  name: string
  mode: "online" | "local"
  available: boolean
  reason: string | null
}

export interface ProvidersResponse {
  providers: ProviderStatus[]
  default_provider: string
}

export const explorerApi = {
  getSchemas: (warehouseId: number) =>
    fetchApi<DatabaseSchema[]>(`/warehouses/${warehouseId}/explorer/schemas`, {
      method: "GET",
    }),

  getTables: (warehouseId: number, schemaName: string) =>
    fetchApi<DatabaseTable[]>(`/warehouses/${warehouseId}/explorer/schemas/${schemaName}/tables`, {
      method: "GET",
    }),

  getColumns: (warehouseId: number, schemaName: string, tableName: string) =>
    fetchApi<DatabaseColumn[]>(`/warehouses/${warehouseId}/explorer/schemas/${schemaName}/tables/${tableName}/columns`, {
      method: "GET",
    }),

  getRows: (
    warehouseId: number,
    schemaName: string,
    tableName: string,
    limit: number = 50,
    offset: number = 0
  ) =>
    fetchApi<RowDataResponse>(
      `/warehouses/${warehouseId}/explorer/schemas/${schemaName}/tables/${tableName}/rows?limit=${limit}&offset=${offset}`,
      { method: "GET" }
    ),

  executeQuery: (warehouseId: number, sql: string, signal?: AbortSignal) =>
    fetchApi<QueryResult>(`/warehouses/${warehouseId}/explorer/query`, {
      method: "POST",
      body: JSON.stringify({ sql }),
      signal,
    }),

  chatAssistant: (warehouseId: number, payload: AssistantRequest, signal?: AbortSignal) =>
    fetchApi<AssistantResponse>(`/warehouses/${warehouseId}/explorer/assistant/chat`, {
      method: "POST",
      body: JSON.stringify(payload),
      signal,
    }),

  getAssistantProviders: (warehouseId: number) =>
    fetchApi<ProvidersResponse>(`/warehouses/${warehouseId}/explorer/assistant/providers`, {
      method: "GET",
    }),
}

