import { fetchApi } from "./client"

export interface Warehouse {
  id: number
  owner_id?: number
  name: string
  description?: string
  db_type: string
  host: string
  port: number
  database_name: string
  username: string
  is_active: boolean
  updated_at: string
}

export interface WarehouseCreateRequest {
  name: string
  description?: string
  db_type: string
  host: string
  port: number
  database_name: string
  username: string
  password?: string
}

export interface WarehouseUpdateRequest {
  name?: string
  description?: string
  db_type?: string
  host?: string
  port?: number
  database_name?: string
  username?: string
  password?: string
}

export const warehousesApi = {
  list: () => 
    fetchApi<Warehouse[]>("/warehouses/", {
      method: "GET",
    }),
    
  get: (id: number) =>
    fetchApi<Warehouse>(`/warehouses/${id}`, {
      method: "GET",
    }),

  create: (data: WarehouseCreateRequest) =>
    fetchApi<Warehouse>("/warehouses/", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (id: number, data: WarehouseUpdateRequest) =>
    fetchApi<Warehouse>(`/warehouses/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  delete: (id: number) =>
    fetchApi<void>(`/warehouses/${id}`, {
      method: "DELETE",
    }),
}
