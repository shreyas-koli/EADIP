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
}
