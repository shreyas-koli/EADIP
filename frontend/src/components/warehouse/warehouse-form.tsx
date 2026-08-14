"use client"

import * as React from "react"
import { Warehouse, WarehouseCreateRequest, WarehouseUpdateRequest } from "@/lib/api/warehouses"
import { Button } from "@/components/ui/button"
import { Loader2 } from "lucide-react"

interface WarehouseFormProps {
  initialData?: Warehouse | null
  onSubmit: (data: WarehouseCreateRequest | WarehouseUpdateRequest) => Promise<void>
  onCancel: () => void
  isLoading?: boolean
}

export function WarehouseForm({ initialData, onSubmit, onCancel, isLoading }: WarehouseFormProps) {
  const isEdit = !!initialData

  const [formData, setFormData] = React.useState({
    name: initialData?.name || "",
    description: initialData?.description || "",
    db_type: initialData?.db_type || "PostgreSQL",
    host: initialData?.host || "",
    port: initialData?.port?.toString() || "5432",
    database_name: initialData?.database_name || "",
    username: initialData?.username || "",
    password: "",
  })

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    const baseData = {
      name: formData.name,
      description: formData.description || undefined,
      db_type: formData.db_type,
      host: formData.host,
      port: parseInt(formData.port, 10),
      database_name: formData.database_name,
      username: formData.username,
    }

    if (isEdit) {
      // For updates, only send password if it was entered
      const updateData: WarehouseUpdateRequest = { ...baseData }
      if (formData.password) {
        updateData.password = formData.password
      }
      await onSubmit(updateData)
    } else {
      // For creates, password is required
      const createData: WarehouseCreateRequest = {
        ...baseData,
        password: formData.password,
      }
      await onSubmit(createData)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm font-medium text-slate-300" htmlFor="name">
          Warehouse Name
        </label>
        <input
          id="name"
          name="name"
          type="text"
          required
          value={formData.name}
          onChange={handleChange}
          className="flex h-9 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-1 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="e.g. Production Analytics DB"
        />
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium text-slate-300" htmlFor="description">
          Description (Optional)
        </label>
        <textarea
          id="description"
          name="description"
          rows={2}
          value={formData.description}
          onChange={handleChange}
          className="flex w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Additional notes about this warehouse..."
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-300" htmlFor="db_type">
            Database Type
          </label>
          <select
            id="db_type"
            name="db_type"
            required
            value={formData.db_type}
            onChange={handleChange}
            className="flex h-9 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-1 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="PostgreSQL">PostgreSQL</option>
            <option value="MySQL">MySQL</option>
            <option value="SQL Server">SQL Server</option>
            <option value="Snowflake">Snowflake</option>
            <option value="BigQuery">BigQuery</option>
          </select>
        </div>
        
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-300" htmlFor="database_name">
            Database Name
          </label>
          <input
            id="database_name"
            name="database_name"
            type="text"
            required
            value={formData.database_name}
            onChange={handleChange}
            className="flex h-9 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-1 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="e.g. analytics"
          />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 space-y-2">
          <label className="text-sm font-medium text-slate-300" htmlFor="host">
            Host / IP Address
          </label>
          <input
            id="host"
            name="host"
            type="text"
            required
            value={formData.host}
            onChange={handleChange}
            className="flex h-9 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-1 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="db.example.com"
          />
        </div>
        
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-300" htmlFor="port">
            Port
          </label>
          <input
            id="port"
            name="port"
            type="number"
            min="1"
            max="65535"
            required
            value={formData.port}
            onChange={handleChange}
            className="flex h-9 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-1 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="5432"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-300" htmlFor="username">
            Username
          </label>
          <input
            id="username"
            name="username"
            type="text"
            required
            value={formData.username}
            onChange={handleChange}
            className="flex h-9 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-1 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            autoComplete="off"
            placeholder="readonly_user"
          />
        </div>
        
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-300" htmlFor="password">
            Password {isEdit && <span className="text-xs text-slate-500">(Leave blank to keep unchanged)</span>}
          </label>
          <input
            id="password"
            name="password"
            type="password"
            required={!isEdit}
            value={formData.password}
            onChange={handleChange}
            className="flex h-9 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-1 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            autoComplete="new-password"
            placeholder="••••••••"
          />
        </div>
      </div>

      <div className="flex justify-end space-x-3 pt-4 border-t border-slate-800">
        <Button type="button" variant="outline" onClick={onCancel} disabled={isLoading}>
          Cancel
        </Button>
        <Button type="submit" disabled={isLoading} className="bg-blue-600 hover:bg-blue-700 text-white">
          {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {isEdit ? "Save Changes" : "Add Warehouse"}
        </Button>
      </div>
    </form>
  )
}
