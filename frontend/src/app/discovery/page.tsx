"use client"

import * as React from "react"
import Link from "next/link"
import { PageContainer } from "@/components/layout/page-container"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { LoadingState } from "@/components/ui/loading-state"
import { 
  Play, 
  Activity, 
  History, 
  AlertCircle, 
  Cpu, 
  Radio, 
  Layers
} from "lucide-react"

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
  const [isConsoleVisible, setIsConsoleVisible] = React.useState(true)
  
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
          const active = data.filter((w) => w.is_active)
          setWarehouses(active)
          if (active.length > 0 && !selectedWarehouseId) {
            setSelectedWarehouseId(active[0].id)
          }
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
  }, [selectedWarehouseId])

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
          setStreamEvents((prev) => [...prev, event as Record<string, unknown>])
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

  const selectedWarehouse = warehouses.find((w) => w.id === selectedWarehouseId)
  const selectedWarehouseName = selectedWarehouse?.name || "Unknown"

  if (isFetchingWarehouses) {
    return (
      <PageContainer title="Autonomous Discovery">
        <div className="flex h-[600px] items-center justify-center">
          <LoadingState message="Initializing autonomous agent engine..." />
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer title="Autonomous Discovery">
      {/* Header Banner */}
      <div className="relative mb-8 overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-950 via-slate-900 to-indigo-950/40 p-6 shadow-2xl backdrop-blur-xl">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Cpu className="h-4 w-4 text-cyan-400" />
              <span className="text-[11px] font-bold uppercase tracking-widest text-cyan-400">
                Multi-Agent Intelligence Pipeline
              </span>
            </div>
            <h2 className="text-2xl font-extrabold tracking-tight text-white">
              Autonomous Discovery & Optimization
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Execute parallel multi-wave agents to profile schema metadata, statistical distributions, query bottlenecks, and generate deterministic recommendations.
            </p>
          </div>
          {resultSession && (
            <Link href={`/history?session=${resultSession.session_id}`}>
              <Button variant="outline" className="border-slate-700 bg-slate-900/80 hover:bg-slate-800 text-slate-200 gap-1.5 text-xs">
                <History className="h-4 w-4 text-cyan-400" /> View in Audit Timeline
              </Button>
            </Link>
          )}
        </div>
      </div>

      <div className="space-y-8">
        {/* Warehouse Selection & Launch Panel */}
        <div className="rounded-2xl border border-slate-800 bg-slate-950/80 p-6 shadow-xl backdrop-blur-xl">
          <WarehouseSelector 
            warehouses={warehouses}
            selectedId={selectedWarehouseId}
            onSelect={setSelectedWarehouseId}
            disabled={isRunning}
          />
          
          <div className="mt-6 pt-5 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <Radio className={`h-4 w-4 ${isRunning ? "text-cyan-400 animate-pulse" : "text-emerald-400"}`} />
              <span>Pipeline: <strong>Wave 1 (Ingest)</strong> → <strong>Wave 2 (Security & Quality)</strong> → <strong>Wave 3 (Supervisor)</strong></span>
            </div>

            <Button 
              onClick={handleRunDiscovery} 
              disabled={!selectedWarehouseId || isRunning}
              className={`w-full sm:w-auto font-semibold px-6 py-2.5 text-sm shadow-xl transition-all ${
                isRunning 
                  ? "bg-slate-800 text-slate-300 border border-slate-700" 
                  : "bg-gradient-to-r from-blue-600 via-indigo-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white shadow-blue-500/20"
              }`}
              size="lg"
            >
              {isRunning ? (
                <>
                  <Activity className="mr-2 h-4 w-4 text-cyan-400 animate-spin" /> Agents Executing…
                </>
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4 fill-current text-white" /> Execute Discovery Pipeline
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Live SSE Stream Console */}
        {isConsoleVisible && (streamEvents.length > 0 || isRunning) && (
          <div className="rounded-2xl border border-slate-800 bg-slate-950/90 shadow-2xl overflow-hidden">
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

        {/* Multi-Agent DAG Visual Pipeline */}
        {(isRunning || resultSession) && (
          <div className="rounded-2xl border border-slate-800 bg-slate-950/90 shadow-2xl p-6 overflow-hidden">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-4 mb-6">
              <div className="flex items-center gap-2">
                <Layers className="h-5 w-5 text-cyan-400" />
                <div>
                  <h3 className="text-base font-bold text-slate-100">Multi-Agent Execution Pipeline</h3>
                  <p className="text-xs text-slate-400">Directed Acyclic Graph (DAG) state progression</p>
                </div>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-cyan-400 border border-cyan-800/30">
                3 Waves • 6 Specialized Agents
              </span>
            </div>

            <div className="overflow-x-auto pb-4">
              <div className="min-w-[750px]">
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
          <div className="rounded-2xl border border-rose-800/60 bg-rose-950/30 p-6 shadow-xl">
            <EmptyState
              icon={AlertCircle}
              title="Execution Failed"
              description={error}
            />
          </div>
        )}

        {/* Ready Placeholder */}
        {!isRunning && !resultSession && !error && (
          <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-900/20 p-12 text-center flex flex-col items-center justify-center min-h-[300px]">
            <Activity className="h-12 w-12 text-slate-700 mb-3" />
            <h3 className="text-base font-semibold text-slate-300">Ready to Execute</h3>
            <p className="text-xs text-slate-500 max-w-sm mt-1">
              Select a target warehouse above and launch the autonomous multi-agent discovery pipeline to analyze performance, schema integrity, and action recommendations.
            </p>
          </div>
        )}

        {/* Completed Results with Controlled Actions & Audit Panel */}
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
