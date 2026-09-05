"use client"

import * as React from "react"
import { PageContainer } from "@/components/layout/page-container"
import { EmptyState } from "@/components/ui/empty-state"
import { LoadingState } from "@/components/ui/loading-state"
import { AlertCircle, Database } from "lucide-react"

import { warehousesApi, Warehouse } from "@/lib/api/warehouses"

import { DatabaseBrowser } from "./database-browser"

export default function ExplorerPage() {
  const [warehouses, setWarehouses] = React.useState<Warehouse[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  
  const [selectedWarehouseId, setSelectedWarehouseId] = React.useState<string>("")

  React.useEffect(() => {
    let mounted = true
    const fetchWarehouses = async () => {
      try {
        if (mounted) setIsLoading(true)
        const data = await warehousesApi.list()
        if (mounted) {
          setWarehouses(data.sort((a, b) => a.name.localeCompare(b.name)))
          setError(null)
          if (data.length > 0 && !selectedWarehouseId) {
            setSelectedWarehouseId(data[0].id.toString())
          }
        }
      } catch (err) {
        if (mounted) {
          const e = err as Error
          setError(e.message || "Failed to load warehouses.")
        }
      } finally {
        if (mounted) setIsLoading(false)
      }
    }
    fetchWarehouses()
    return () => { mounted = false }
  }, [selectedWarehouseId])

  const selectedWarehouse = warehouses.find(w => w.id.toString() === selectedWarehouseId)

  if (isLoading && warehouses.length === 0) {
    return (
      <PageContainer title="Warehouse Explorer">
        <div className="flex h-[600px] items-center justify-center">
          <LoadingState message="Loading warehouses..." />
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer title="Warehouse Explorer">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Warehouse Explorer</h2>
          <p className="text-slate-400">Select a warehouse to explore its schema and tables.</p>
        </div>
      </div>

      {error ? (
        <EmptyState
          icon={AlertCircle}
          title="Failed to load warehouses"
          description={error}
        />
      ) : warehouses.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No warehouses configured"
          description="Connect your first data warehouse to begin discovery and analysis."
        />
      ) : (
        <div className="flex flex-col gap-8">
          <div className="flex flex-col gap-2">
            <label htmlFor="warehouse-select" className="text-sm font-medium text-slate-300">
              Select Warehouse
            </label>
            <select
              id="warehouse-select"
              value={selectedWarehouseId}
              onChange={(e) => setSelectedWarehouseId(e.target.value)}
              className="flex h-10 w-full max-w-md items-center justify-between rounded-md border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <option value="" disabled>Select a warehouse...</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id.toString()}>
                  {w.name} ({w.db_type})
                </option>
              ))}
            </select>
          </div>

          <hr className="border-slate-800" />

          {selectedWarehouse && (
            <div className="mt-4">
              <DatabaseBrowser key={selectedWarehouseId} warehouseId={parseInt(selectedWarehouseId)} />
            </div>
          )}
        </div>
      )}
    </PageContainer>
  )
}
