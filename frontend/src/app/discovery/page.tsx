"use client"

import * as React from "react"
import Link from "next/link"
import { PageContainer } from "@/components/layout/page-container"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { LoadingState } from "@/components/ui/loading-state"
import { Play, Activity, History, AlertCircle } from "lucide-react"

import { warehousesApi, Warehouse } from "@/lib/api/warehouses"
import { discoveryApi, DiscoverySession } from "@/lib/api/discovery"

import { WarehouseSelector } from "@/components/discovery/warehouse-selector"
import { DiscoveryPipeline } from "@/components/discovery/discovery-pipeline"
import { DiscoveryResult } from "@/components/discovery/discovery-result"
import { DiscoveryConsole } from "@/components/discovery/discovery-console"
import { useExecutionReplay } from "@/hooks/useExecutionReplay"

export default function DiscoveryPage() {
  const [warehouses, setWarehouses] = React.useState<Warehouse[]>([])
  const [selectedWarehouseId, setSelectedWarehouseId] = React.useState<number | null>(null)
  
  const [isFetchingWarehouses, setIsFetchingWarehouses] = React.useState(true)
  const [isRunning, setIsRunning] = React.useState(false)
  
  const [resultSession, setResultSession] = React.useState<DiscoverySession | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  
  // Streaming state
  const [streamEvents, setStreamEvents] = React.useState<Record<string, unknown>[]>([])
  const [isConsoleVisible, setIsConsoleVisible] = React.useState(false)
  
  // Initialization state
  const [isInitializing, setIsInitializing] = React.useState(false)
  const [initCountdown, setInitCountdown] = React.useState(5)
  
  // Monitoring result
  const [monitoringResult, setMonitoringResult] = React.useState<Record<string, unknown> | null>(null)

  // Replay System
  const replay = useExecutionReplay(streamEvents)

  React.useEffect(() => {
    let mounted = true
    const fetchWarehouses = async () => {
      try {
        const data = await warehousesApi.list()
        if (mounted) {
          const active = data.filter(w => w.is_active)
          setWarehouses(active)
        }
      } catch {
        if (mounted) {
          setError("Failed to load warehouses.")
        }
      } finally {
        if (mounted) setIsFetchingWarehouses(false)
      }
    }
    fetchWarehouses()
    return () => { mounted = false }
  }, [])

  const handleRunDiscovery = async () => {
    if (!selectedWarehouseId) return
    
    setIsRunning(true)
    setError(null)
    setResultSession(null)
    setStreamEvents([])
    setIsConsoleVisible(true)
    setMonitoringResult(null)
    
    setIsInitializing(false)
    setInitCountdown(0)
    replay.actions.reset()
    
    try {
      await discoveryApi.executeStream(
        { warehouse_id: selectedWarehouseId },
        (event) => {
          setStreamEvents(prev => [...prev, event as Record<string, unknown>])
          if (event.event === "discovery_completed") {
            setResultSession(event.session as DiscoverySession)
            if (event.monitoring) {
              setMonitoringResult(event.monitoring as Record<string, unknown>)
            }
            setIsRunning(false)
          } else if (event.event === "error") {
            setError((event.message as string) || "Discovery execution failed during stream.")
            setIsRunning(false)
          }
        }
      )
    } catch (err) {
      const e = err as Error
      setError(e.message || "Discovery execution failed. Please check backend logs.")
      setIsRunning(false)
    }
  }

  const selectedWarehouseName = warehouses.find(w => w.id === selectedWarehouseId)?.name || "Unknown"

  if (isFetchingWarehouses) {
    return (
      <PageContainer title="Discovery">
        <div className="flex h-[600px] items-center justify-center">
          <LoadingState message="Loading discovery engine..." />
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer title="Discovery">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Run Discovery</h2>
          <p className="text-slate-400">Execute multi-agent intelligence on your connected data warehouses.</p>
        </div>
        {resultSession && (
          <Link href={`/history?session=${resultSession.session_id}`}>
            <Button variant="outline" className="w-full sm:w-auto">
              <History className="mr-2 h-4 w-4" /> View History
            </Button>
          </Link>
        )}
      </div>

      <div className="space-y-8">
        {/* Controls */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
          <WarehouseSelector 
            warehouses={warehouses}
            selectedId={selectedWarehouseId}
            onSelect={setSelectedWarehouseId}
            disabled={isRunning}
          />
          
          <div className="mt-6 pt-6 border-t border-slate-800 flex justify-end">
            <Button 
              onClick={handleRunDiscovery} 
              disabled={!selectedWarehouseId || isRunning}
              className="bg-blue-600 hover:bg-blue-700 text-white w-full sm:w-auto"
              size="lg"
            >
              {isRunning ? (
                <>
                  <Activity className="mr-2 h-5 w-5 animate-pulse" /> Running Intelligence...
                </>
              ) : (
                <>
                  <Play className="mr-2 h-5 w-5 fill-current" /> Execute Discovery
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Live Console */}
        {isConsoleVisible && (
          <div className="mb-8">
            <DiscoveryConsole 
              warehouseName={selectedWarehouseName}
              isComplete={!isRunning && !!resultSession}
              actualSessionStatus={resultSession?.status}
              actualDurationMs={resultSession?.total_duration_ms}
              events={streamEvents}
              replayState={replay.state}
              replayActions={replay.actions}
              isInitializing={isInitializing}
              initCountdown={initCountdown}
            />
          </div>
        )}

        {/* Pipeline */}
        {(isRunning || resultSession) && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 overflow-hidden mb-8">
            <div className="text-center mb-8">
              <h3 className="text-lg font-semibold text-slate-200">Multi-Agent Execution Pipeline</h3>
              <p className="text-sm text-slate-400">Directed Acyclic Graph (DAG) progression</p>
            </div>
            <div className="overflow-x-auto pb-4">
              <div className="min-w-[600px]">
                <DiscoveryPipeline 
                  executions={resultSession?.agent_executions} 
                  isRunning={isRunning} 
                  events={replay.state.isReplaying ? replay.state.visibleEvents : streamEvents}
                  isReplaying={replay.state.isReplaying}
                  isInitializing={isInitializing}
                />
              </div>
            </div>
          </div>
        )}

        {/* Errors */}
        {error && (
          <EmptyState
            icon={AlertCircle}
            title="Execution Failed"
            description={error}
          />
        )}

        {/* Empty State */}
        {!isRunning && !resultSession && !error && (
           <div className="p-8 rounded-xl bg-slate-900/30 border border-slate-800 border-dashed text-center h-full flex flex-col items-center justify-center min-h-[300px]">
              <Activity className="h-10 w-10 text-slate-700 mb-4" />
              <h3 className="text-lg font-medium text-slate-400 mb-2">Ready to Execute</h3>
              <p className="text-sm text-slate-500 max-w-[200px] mx-auto">
                Select a warehouse and click Execute Discovery to begin.
              </p>
           </div>
        )}

        {/* Results */}
        {resultSession && (
          <DiscoveryResult 
            session={resultSession} 
            warehouseName={selectedWarehouseName}
            monitoringResult={monitoringResult}
          />
        )}
      </div>
    </PageContainer>
  )
}
