"use client"

import * as React from "react"
import Link from "next/link"
import { PageContainer } from "@/components/layout/page-container"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { EmptyState } from "@/components/ui/empty-state"
import { LoadingState } from "@/components/ui/loading-state"
import { AgentStatus } from "@/components/agent/agent-components"
import { 
  Activity, 
  Database, 
  AlertCircle, 
  Play, 
  Server, 
  Clock, 
  Compass, 
  ArrowRight, 
  ShieldCheck
} from "lucide-react"

import { warehousesApi, Warehouse } from "@/lib/api/warehouses"
import { discoveryApi, DiscoverySession } from "@/lib/api/discovery"

interface DashboardData {
  warehouses: Warehouse[]
  recentRuns: (DiscoverySession & { warehouseName: string; warehouseId: number })[]
  totalRuns: number
  healthyCount: number
  attentionCount: number
  engineCounts: Record<string, number>
}

export default function DashboardPage() {
  const [data, setData] = React.useState<DashboardData | null>(null)
  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    async function fetchDashboardData() {
      try {
        // 1. Fetch Warehouses
        const warehouses = await warehousesApi.list()
        
        // 2. Fetch history for each active warehouse
        let allRuns: (DiscoverySession & { warehouseName: string; warehouseId: number })[] = []
        let totalRuns = 0
        let healthyCount = 0
        let attentionCount = 0
        const engineCounts: Record<string, number> = {}

        warehouses.forEach((w) => {
          const type = (w.db_type || "OTHER").toUpperCase()
          engineCounts[type] = (engineCounts[type] || 0) + 1
        })

        if (warehouses.length > 0) {
          const historyPromises = warehouses.map((w) => discoveryApi.getHistory(w.id, 1, 5))
          const results = await Promise.allSettled(historyPromises)
          
          results.forEach((res, index) => {
            const w = warehouses[index]
            if (res.status === "fulfilled") {
              const history = res.value
              totalRuns += history.total
              
              const runsWithNames = history.items.map((run) => ({
                ...run,
                warehouseName: w.name,
                warehouseId: w.id,
              }))
              allRuns = [...allRuns, ...runsWithNames]
              
              if (history.items.length > 0) {
                if (history.items[0].status === "FAILED") {
                  attentionCount++
                } else {
                  healthyCount++
                }
              } else if (w.is_active) {
                healthyCount++
              }
            } else {
              attentionCount++
            }
          })
          
          allRuns.sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
        }

        setData({
          warehouses,
          recentRuns: allRuns.slice(0, 8),
          totalRuns,
          healthyCount,
          attentionCount,
          engineCounts,
        })
        
      } catch (err) {
        const e = err as Error
        setError(e.message || "Failed to load dashboard data.")
      } finally {
        setIsLoading(false)
      }
    }

    fetchDashboardData()
  }, [])

  if (isLoading) {
    return (
      <PageContainer title="Fleet Operations Cockpit">
        <div className="flex h-[600px] items-center justify-center">
          <LoadingState message="Connecting to AetherArchive Autonomous Fleet..." />
        </div>
      </PageContainer>
    )
  }

  if (error) {
    return (
      <PageContainer title="Fleet Operations Cockpit">
        <EmptyState
          icon={AlertCircle}
          title="Fleet Telemetry Error"
          description={error}
          action={<Button onClick={() => window.location.reload()} variant="outline">Retry Connection</Button>}
        />
      </PageContainer>
    )
  }

  if (data?.warehouses.length === 0) {
    return (
      <PageContainer title="Fleet Operations Cockpit">
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-8 shadow-2xl backdrop-blur-xl">
          <EmptyState
            icon={Database}
            title="No Warehouses Connected"
            description="Register your first PostgreSQL, MySQL, Snowflake, or BigQuery instance to initiate autonomous discovery and AI optimizations."
            action={
              <Link href="/warehouses">
                <Button className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-medium shadow-lg shadow-blue-500/20">
                  <Server className="mr-2 h-4 w-4" /> Connect Warehouse
                </Button>
              </Link>
            }
          />
        </div>
      </PageContainer>
    )
  }

  const successRate = data && data.totalRuns > 0
    ? Math.round(((data.totalRuns - data.attentionCount) / data.totalRuns) * 100)
    : 100

  return (
    <PageContainer title="Fleet Operations Cockpit">
      {/* Hero Action Header */}
      <div className="relative mb-8 overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-950 via-slate-900/90 to-blue-950/40 p-6 shadow-2xl backdrop-blur-xl">
        <div className="absolute right-0 top-0 -mt-12 -mr-12 h-64 w-64 rounded-full bg-cyan-500/10 blur-3xl pointer-events-none" />
        <div className="relative flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[11px] font-bold uppercase tracking-widest text-cyan-400">
                Autonomous Intelligence Active
              </span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Fleet Operations & Intelligence Cockpit
            </h2>
            <p className="text-sm text-slate-400 mt-1 max-w-xl">
              Real-time telemetry, multi-wave discovery execution status, and autonomous database recommendations.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link href="/explorer">
              <Button variant="outline" className="border-slate-700 bg-slate-900/80 hover:bg-slate-800 text-slate-200">
                <Compass className="mr-2 h-4 w-4 text-cyan-400" /> Open SQL Explorer
              </Button>
            </Link>
            <Link href="/discovery">
              <Button className="bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white shadow-lg shadow-blue-500/25">
                <Play className="mr-2 h-4 w-4 fill-current" /> Launch Discovery Run
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Primary KPI Metrics */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <Card className="border-slate-800/80 bg-slate-900/50 backdrop-blur-md hover:border-slate-700 transition-all">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Connected Warehouses
            </CardTitle>
            <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
              <Database className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-extrabold text-white font-mono">{data?.warehouses.length}</div>
            <div className="flex items-center gap-1.5 mt-2 text-xs text-slate-400">
              <span className="text-emerald-400 font-semibold">{data?.healthyCount} active</span>
              <span>•</span>
              <span className="text-slate-500">
                {Object.keys(data?.engineCounts || {}).join(", ")}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-800/80 bg-slate-900/50 backdrop-blur-md hover:border-slate-700 transition-all">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Discovery Executions
            </CardTitle>
            <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
              <Activity className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-extrabold text-white font-mono">{data?.totalRuns}</div>
            <div className="flex items-center gap-1.5 mt-2 text-xs text-slate-400">
              <span className="text-cyan-400 font-semibold">3 Multi-Agent Waves</span>
              <span>•</span>
              <span>Ingest, Audit, Optimize</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-800/80 bg-slate-900/50 backdrop-blur-md hover:border-slate-700 transition-all">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Fleet Reliability
            </CardTitle>
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
              <ShieldCheck className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-extrabold text-emerald-400 font-mono">
              {successRate}%
            </div>
            <div className="flex items-center gap-1.5 mt-2 text-xs text-slate-400">
              <span className="text-emerald-400 font-semibold">{data?.healthyCount} healthy</span>
              <span>fleet targets</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-800/80 bg-slate-900/50 backdrop-blur-md hover:border-slate-700 transition-all">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Attention Required
            </CardTitle>
            <div className={`p-2 rounded-lg ${data?.attentionCount ? "bg-amber-500/10 text-amber-400" : "bg-slate-800 text-slate-500"}`}>
              <AlertCircle className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className={`text-3xl font-extrabold font-mono ${data?.attentionCount ? "text-amber-400" : "text-slate-400"}`}>
              {data?.attentionCount}
            </div>
            <div className="flex items-center gap-1.5 mt-2 text-xs text-slate-400">
              {data?.attentionCount ? (
                <span className="text-amber-400 font-medium">1 or more runs need review</span>
              ) : (
                <span className="text-slate-500">All warehouse agents nominal</span>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Grid: Warehouse Fleet & Recent Activity */}
      <div className="grid gap-8 lg:grid-cols-5 mb-8">
        {/* Left: Connected Warehouses Fleet (3 Cols) */}
        <div className="lg:col-span-3 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-blue-400" />
              <h3 className="text-base font-bold tracking-tight text-white">Active Warehouse Fleet</h3>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-800 text-slate-400">
                {data?.warehouses.length}
              </span>
            </div>
            <Link href="/warehouses" className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1">
              Manage Warehouses <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {data?.warehouses.map((w) => (
              <div 
                key={w.id} 
                className="group relative flex flex-col justify-between rounded-xl border border-slate-800/80 bg-slate-900/60 p-4 hover:border-slate-700 hover:bg-slate-900/90 transition-all shadow-md"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
                        <Server className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <h4 className="font-semibold text-sm text-slate-100 truncate group-hover:text-cyan-300 transition-colors">
                          {w.name}
                        </h4>
                        <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700/60">
                          {w.db_type}
                        </span>
                      </div>
                    </div>
                    <Badge variant={w.is_active ? "default" : "destructive"} className="text-[10px]">
                      {w.is_active ? "Online" : "Offline"}
                    </Badge>
                  </div>

                  <p className="text-xs font-mono text-slate-400 truncate mb-3">
                    {w.host}:{w.port} • {w.database_name}
                  </p>
                </div>

                <div className="flex items-center justify-between border-t border-slate-800/80 pt-3">
                  <Link
                    href={`/explorer`}
                    className="text-xs text-slate-400 hover:text-cyan-400 flex items-center gap-1 font-medium transition-colors"
                  >
                    <Compass className="h-3.5 w-3.5" />
                    Explore SQL
                  </Link>
                  <Link
                    href={`/discovery`}
                    className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 font-medium transition-colors"
                  >
                    <Play className="h-3 w-3 fill-current" />
                    Run Discovery
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Recent Discovery Telemetry (2 Cols) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-cyan-400" />
              <h3 className="text-base font-bold tracking-tight text-white">Recent Execution Stream</h3>
            </div>
            <Link href="/history" className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1">
              Audit Logs <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          {data?.recentRuns.length === 0 ? (
            <Card className="border-slate-800 bg-slate-900/40 border-dashed">
              <CardContent className="p-8 flex flex-col items-center justify-center text-center">
                <Activity className="h-8 w-8 text-slate-600 mb-2" />
                <p className="text-sm text-slate-400 mb-3">No recent discovery executions recorded.</p>
                <Link href="/discovery">
                  <Button size="sm" variant="outline" className="border-slate-700">
                    Run First Session
                  </Button>
                </Link>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2.5">
              {data?.recentRuns.slice(0, 5).map((run) => (
                <Link
                  key={run.session_id}
                  href={`/history?session=${run.session_id}`}
                  className="block rounded-xl border border-slate-800/80 bg-slate-900/50 p-3.5 hover:border-slate-700 hover:bg-slate-900/80 transition-all group"
                >
                  <div className="flex items-center justify-between">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-slate-200 group-hover:text-cyan-300 transition-colors truncate">
                        {run.warehouseName}
                      </p>
                      <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-1">
                        <span className="flex items-center font-mono">
                          <Clock className="mr-1 h-3 w-3 text-slate-500" />
                          {new Date(run.started_at).toLocaleDateString()} {new Date(run.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                        {run.total_duration_ms && (
                          <span className="font-mono text-slate-400">
                            • {(run.total_duration_ms / 1000).toFixed(1)}s
                          </span>
                        )}
                      </div>
                    </div>
                    <AgentStatus status={run.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </PageContainer>
  )
}
