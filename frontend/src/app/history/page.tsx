"use client"

import * as React from "react"
import { useSearchParams } from "next/navigation"
import { PageContainer } from "@/components/layout/page-container"
import { EmptyState } from "@/components/ui/empty-state"
import { LoadingState } from "@/components/ui/loading-state"
import { History as HistoryIcon, AlertCircle, Database, ShieldCheck, Clock } from "lucide-react"

import { warehousesApi, Warehouse } from "@/lib/api/warehouses"
import { discoveryApi, DiscoveryHistoryResponse } from "@/lib/api/discovery"

import { WarehouseSelector } from "@/components/discovery/warehouse-selector"
import { HistoryList } from "@/components/history/history-list"
import { HistoryFilters } from "@/components/history/history-filters"
import { HistoryPagination } from "@/components/history/history-pagination"
import { SessionDetail } from "@/components/history/session-detail"

function HistoryContent() {
  const searchParams = useSearchParams()
  const urlSession = searchParams.get("session")

  const [warehouses, setWarehouses] = React.useState<Warehouse[]>([])
  const [selectedWarehouseId, setSelectedWarehouseId] = React.useState<number | null>(null)
  const [isFetchingWarehouses, setIsFetchingWarehouses] = React.useState(true)

  // History State
  const [historyItems, setHistoryItems] = React.useState<DiscoveryHistoryResponse[]>([])
  const [totalItems, setTotalItems] = React.useState(0)
  const [page, setPage] = React.useState(1)
  const pageSize = 10
  const [statusFilter, setStatusFilter] = React.useState("ALL")
  
  const [isFetchingHistory, setIsFetchingHistory] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  // Session Detail State
  const [selectedSessionId, setSelectedSessionId] = React.useState<string | null>(urlSession || null)

  // Load Warehouses
  React.useEffect(() => {
    let mounted = true
    const fetchWarehouses = async () => {
      try {
        const data = await warehousesApi.list()
        if (mounted) {
          const active = data.filter((w) => w.is_active)
          setWarehouses(active)
          
          if (active.length > 0 && !selectedWarehouseId) {
            setSelectedWarehouseId(active[0].id)
          }
        }
      } catch {
        if (mounted) setError("Failed to load warehouses.")
      } finally {
        if (mounted) setIsFetchingWarehouses(false)
      }
    }
    fetchWarehouses()
    return () => { mounted = false }
  }, [selectedWarehouseId])

  // Load History
  React.useEffect(() => {
    if (!selectedWarehouseId) return
    
    let mounted = true
    const fetchHistory = async () => {
      try {
        setIsFetchingHistory(true)
        setError(null)
        const data = await discoveryApi.getHistory(selectedWarehouseId, page, pageSize, statusFilter)
        if (mounted) {
          setHistoryItems(data.items)
          setTotalItems(data.total)
        }
      } catch {
        if (mounted) setError("Failed to load history.")
      } finally {
        if (mounted) setIsFetchingHistory(false)
      }
    }
    fetchHistory()
    return () => { mounted = false }
  }, [selectedWarehouseId, page, statusFilter])

  const handleWarehouseSelect = (id: number) => {
    setSelectedWarehouseId(id)
    setPage(1)
    setSelectedSessionId(null)
  }

  const selectedWarehouseName = warehouses.find((w) => w.id === selectedWarehouseId)?.name || "Unknown"

  if (isFetchingWarehouses) {
    return (
      <PageContainer title="Audit History">
        <div className="flex h-[600px] items-center justify-center">
          <LoadingState message="Connecting to Historical Audit Records..." />
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer title="Audit History">
      {/* Top Banner */}
      <div className="relative mb-8 overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950 p-6 shadow-2xl backdrop-blur-xl">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              <span className="text-[11px] font-bold uppercase tracking-widest text-emerald-400">
                Immutable Audit Trail
              </span>
            </div>
            <h2 className="text-2xl font-extrabold tracking-tight text-white">
              Discovery History & Recommendation Timeline
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Deterministic R1-R6 historical records: fingerprint matches, condition states, decision justifications, and lifecycle transitions.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400 bg-slate-900/80 px-3 py-1.5 rounded-lg border border-slate-800">
            <Clock className="h-3.5 w-3.5 text-cyan-400" />
            <span>{totalItems} recorded session{totalItems !== 1 ? "s" : ""}</span>
          </div>
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-12">
        {/* Left Column: Selector & List */}
        <div className="lg:col-span-5 space-y-6">
          <div className="rounded-2xl border border-slate-800 bg-slate-950/80 p-5 shadow-xl backdrop-blur-xl">
            <WarehouseSelector 
              warehouses={warehouses}
              selectedId={selectedWarehouseId}
              onSelect={handleWarehouseSelect}
            />
          </div>

          {selectedWarehouseId && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200">
                  Execution Runs
                </h3>
                <HistoryFilters statusFilter={statusFilter} onStatusChange={(s) => { setStatusFilter(s); setPage(1); }} />
              </div>

              {error ? (
                <EmptyState icon={AlertCircle} title="Error" description={error} />
              ) : isFetchingHistory && historyItems.length === 0 ? (
                <div className="py-12 border border-slate-800 rounded-2xl bg-slate-900/20">
                  <LoadingState message="Fetching history records..." />
                </div>
              ) : (
                <div className="rounded-2xl border border-slate-800/80 bg-slate-950/80 shadow-xl overflow-hidden">
                  <HistoryList 
                    items={historyItems}
                    selectedSessionId={selectedSessionId}
                    onSelect={(session) => setSelectedSessionId(session.session_id)}
                  />
                  <div className="border-t border-slate-800/80 bg-slate-900/40 p-3">
                    <HistoryPagination 
                      page={page}
                      pageSize={pageSize}
                      total={totalItems}
                      onPageChange={setPage}
                      disabled={isFetchingHistory}
                    />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Details Drawer */}
        <div className="lg:col-span-7">
          {!selectedWarehouseId ? (
            <EmptyState
              icon={Database}
              title="No Warehouse Selected"
              description="Select a warehouse from the list to view its execution history."
            />
          ) : selectedSessionId ? (
            <div className="sticky top-6 lg:h-[calc(100vh-140px)] overflow-y-auto pr-2 pb-8">
              <SessionDetail 
                warehouseId={selectedWarehouseId}
                warehouseName={selectedWarehouseName}
                sessionId={selectedSessionId}
                onClose={() => setSelectedSessionId(null)}
              />
            </div>
          ) : (
            <div className="h-full min-h-[420px] rounded-2xl bg-slate-950/60 border border-slate-800 border-dashed flex flex-col items-center justify-center text-center p-8">
              <HistoryIcon className="h-12 w-12 text-slate-700 mb-3" />
              <h3 className="text-base font-semibold text-slate-300">Select a Session</h3>
              <p className="text-xs text-slate-500 max-w-xs mt-1">
                Click on any discovery run from the execution list to inspect agent waves, execution logs, and recommendation decision audit records.
              </p>
            </div>
          )}
        </div>
      </div>
    </PageContainer>
  )
}

export default function HistoryPage() {
  return (
    <React.Suspense fallback={
      <PageContainer title="Audit History">
        <div className="flex h-[600px] items-center justify-center">
          <LoadingState message="Connecting to historical records..." />
        </div>
      </PageContainer>
    }>
      <HistoryContent />
    </React.Suspense>
  )
}
