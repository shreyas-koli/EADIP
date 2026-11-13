"use client"

import * as React from "react"
import { PageContainer } from "@/components/layout/page-container"
import { EmptyState } from "@/components/ui/empty-state"
import { LoadingState } from "@/components/ui/loading-state"
import { AlertCircle, Database, Server, Compass } from "lucide-react"

import { warehousesApi, Warehouse } from "@/lib/api/warehouses"
import { DatabaseBrowser } from "./database-browser"

export default function ExplorerPage() {
  const [warehouses, setWarehouses] = React.useState<Warehouse[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [selectedWarehouseId, setSelectedWarehouseId] = React.useState<string>("")

  const fetchWarehouses = React.useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await warehousesApi.list()
      setWarehouses(data.sort((a, b) => a.name.localeCompare(b.name)))
      setError(null)
      if (data.length > 0 && !selectedWarehouseId) {
        setSelectedWarehouseId(data[0].id.toString())
      }
    } catch (err) {
      const e = err as Error
      setError(e.message || "Failed to load warehouses.")
    } finally {
      setIsLoading(false)
    }
  }, [selectedWarehouseId])

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchWarehouses()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const selectedWarehouse = warehouses.find((w) => w.id.toString() === selectedWarehouseId)

  if (isLoading && warehouses.length === 0) {
    return (
      <PageContainer title="Warehouse Explorer" fullWidth>
        <div className="flex h-[600px] items-center justify-center">
          <LoadingState message="Connecting to Warehouse Object Catalog..." />
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer title="Warehouse Explorer" fullWidth>
      {/* Top Controls Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 border-b border-slate-800/80 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="p-1 rounded-md bg-cyan-500/10 text-cyan-400">
              <Compass className="h-4 w-4" />
            </span>
            <span className="text-[11px] font-bold uppercase tracking-widest text-cyan-400">
              Interactive Data Studio
            </span>
          </div>
          <h2 className="text-2xl font-extrabold tracking-tight text-white">
            Warehouse Explorer & Visual Analytics
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Database object hierarchy, SQL worksheet console, data previews, and Snowflake-style visual charting.
          </p>
        </div>

        {/* Warehouse Switcher */}
        {warehouses.length > 0 && (
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900/80 px-3 py-1.5 shadow-sm">
              <Server className="h-4 w-4 text-cyan-400 shrink-0" />
              <div className="flex flex-col">
                <span className="text-[10px] font-medium uppercase text-slate-500">Active Warehouse</span>
                <select
                  id="warehouse-select"
                  value={selectedWarehouseId}
                  onChange={(e) => setSelectedWarehouseId(e.target.value)}
                  className="bg-transparent text-xs font-semibold text-slate-100 focus:outline-none cursor-pointer pr-4"
                >
                  {warehouses.map((w) => (
                    <option key={w.id} value={w.id.toString()} className="bg-slate-900 text-slate-200">
                      {w.name} ({w.db_type.toUpperCase()})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {selectedWarehouse && (
              <span className="text-[11px] font-mono uppercase px-2.5 py-1.5 rounded-lg bg-blue-950/60 text-blue-400 border border-blue-800/50">
                {selectedWarehouse.db_type}
              </span>
            )}
          </div>
        )}
      </div>

      {error ? (
        <EmptyState
          icon={AlertCircle}
          title="Warehouse Discovery Error"
          description={error}
          action={<button onClick={fetchWarehouses} className="text-xs text-cyan-400 underline">Retry</button>}
        />
      ) : warehouses.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No Warehouses Configured"
          description="Connect your first PostgreSQL, MySQL, Snowflake, or BigQuery instance to explore schemas."
        />
      ) : (
        selectedWarehouse && (
          <DatabaseBrowser key={selectedWarehouseId} warehouseId={parseInt(selectedWarehouseId)} />
        )
      )}
    </PageContainer>
  )
}
