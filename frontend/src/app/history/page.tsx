"use client"

import * as React from "react"
import { useSearchParams } from "next/navigation"
import { PageContainer } from "@/components/layout/page-container"
import { EmptyState } from "@/components/ui/empty-state"
import { LoadingState } from "@/components/ui/loading-state"
import { History as HistoryIcon, AlertCircle, Database } from "lucide-react"

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
          const active = data.filter(w => w.is_active)
          setWarehouses(active)
          
          // Auto-select first active warehouse if none selected
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
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

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

  // Handle warehouse change
  const handleWarehouseSelect = (id: number) => {
    setSelectedWarehouseId(id)
    setPage(1)
    setSelectedSessionId(null)
  }

  const selectedWarehouseName = warehouses.find(w => w.id === selectedWarehouseId)?.name || "Unknown"

  if (isFetchingWarehouses) {
    return (
      <PageContainer title="History">
        <div className="flex h-[600px] items-center justify-center">
          <LoadingState message="Loading environment..." />
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer title="History">
      <div className="mb-8">
        <h2 className="text-2xl font-bold tracking-tight">Discovery History</h2>
        <p className="text-slate-400">Review past multi-agent execution runs and their results.</p>
      </div>

      <div className="grid gap-8 lg:grid-cols-12">
        {/* Left Column: Selector & List */}
        <div className="lg:col-span-5 space-y-6">
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
            <WarehouseSelector 
              warehouses={warehouses}
              selectedId={selectedWarehouseId}
              onSelect={handleWarehouseSelect}
            />
          </div>

          {selectedWarehouseId && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-slate-200">Execution Runs</h3>
                <HistoryFilters statusFilter={statusFilter} onStatusChange={(s) => { setStatusFilter(s); setPage(1); }} />
              </div>

              {error ? (
                <EmptyState icon={AlertCircle} title="Error" description={error} />
              ) : isFetchingHistory && historyItems.length === 0 ? (
                <div className="py-12 border border-slate-800 rounded-xl bg-slate-900/20">
                  <LoadingState message="Fetching history..." />
                </div>
              ) : (
                <div className="shadow-lg">
                  <HistoryList 
                    items={historyItems}
                    selectedSessionId={selectedSessionId}
                    onSelect={(session) => setSelectedSessionId(session.session_id)}
                  />
                  <HistoryPagination 
                    page={page}
                    pageSize={pageSize}
                    total={totalItems}
                    onPageChange={setPage}
                    disabled={isFetchingHistory}
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Details */}
        <div className="lg:col-span-7">
          {!selectedWarehouseId ? (
            <EmptyState
              icon={Database}
              title="No Warehouse Selected"
              description="Select a warehouse from the list to view its execution history."
            />
          ) : selectedSessionId ? (
            <div className="sticky top-6 lg:h-[calc(100vh-120px)] overflow-y-auto pr-2 pb-8 custom-scrollbar">
              <SessionDetail 
                warehouseId={selectedWarehouseId}
                warehouseName={selectedWarehouseName}
                sessionId={selectedSessionId}
                onClose={() => setSelectedSessionId(null)}
              />
            </div>
          ) : (
            <div className="h-full min-h-[400px] rounded-xl bg-slate-900/30 border border-slate-800 border-dashed flex flex-col items-center justify-center text-center p-8">
              <HistoryIcon className="h-12 w-12 text-slate-700 mb-4" />
              <h3 className="text-lg font-medium text-slate-300 mb-2">Select a Session</h3>
              <p className="text-sm text-slate-500 max-w-[250px]">
                Click on any discovery run from the list to view detailed execution pipelines and agent results.
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
      <PageContainer title="History">
        <div className="flex h-[600px] items-center justify-center">
          <LoadingState message="Loading environment..." />
        </div>
      </PageContainer>
    }>
      <HistoryContent />
    </React.Suspense>
  )
}
