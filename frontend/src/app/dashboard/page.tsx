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
import { Activity, Database, CheckCircle, AlertCircle, Play, Server, Clock } from "lucide-react"

import { warehousesApi, Warehouse } from "@/lib/api/warehouses"
import { discoveryApi, DiscoverySession } from "@/lib/api/discovery"

interface DashboardData {
  warehouses: Warehouse[]
  recentRuns: (DiscoverySession & { warehouseName: string })[]
  totalRuns: number
  healthyCount: number
  attentionCount: number
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
        let allRuns: (DiscoverySession & { warehouseName: string })[] = []
        let totalRuns = 0
        let healthyCount = 0
        let attentionCount = 0

        if (warehouses.length > 0) {
          const historyPromises = warehouses.map(w => discoveryApi.getHistory(w.id, 1, 5))
          // We use allSettled to ensure one failing warehouse doesn't break the whole dashboard
          const results = await Promise.allSettled(historyPromises)
          
          results.forEach((res, index) => {
            const w = warehouses[index]
            if (res.status === "fulfilled") {
              const history = res.value
              totalRuns += history.total
              
              const runsWithNames = history.items.map(run => ({
                ...run,
                warehouseName: w.name
              }))
              allRuns = [...allRuns, ...runsWithNames]
              
              // Calculate health based on latest run
              if (history.items.length > 0) {
                if (history.items[0].status === "FAILED") {
                  attentionCount++
                } else {
                  healthyCount++
                }
              } else if (w.is_active) {
                healthyCount++ // Default active to healthy if no runs
              }
            } else {
              attentionCount++ // Failed to fetch history -> attention
            }
          })
          
          // Sort runs by started_at desc
          allRuns.sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
        }

        setData({
          warehouses,
          recentRuns: allRuns.slice(0, 5), // Top 5 recent across all
          totalRuns,
          healthyCount,
          attentionCount,
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
      <PageContainer title="Dashboard">
        <div className="flex h-[600px] items-center justify-center">
          <LoadingState message="Loading your data intelligence dashboard..." />
        </div>
      </PageContainer>
    )
  }

  if (error) {
    return (
      <PageContainer title="Dashboard">
        <EmptyState
          icon={AlertCircle}
          title="Failed to load data"
          description={error}
          action={<Button onClick={() => window.location.reload()} variant="outline">Retry</Button>}
        />
      </PageContainer>
    )
  }

  if (data?.warehouses.length === 0) {
    return (
      <PageContainer title="Dashboard">
        <EmptyState
          icon={Database}
          title="No warehouses registered yet"
          description="Connect your first data warehouse to begin intelligent discovery and analysis."
          action={
            <Link href="/warehouses">
              <Button>
                <Server className="mr-2 h-4 w-4" /> Add Warehouse
              </Button>
            </Link>
          }
        />
      </PageContainer>
    )
  }

  return (
    <PageContainer title="Dashboard">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Overview</h2>
          <p className="text-slate-400">Your enterprise data intelligence summary.</p>
        </div>
        <Link href="/discovery">
          <Button className="bg-blue-600 hover:bg-blue-700 text-white">
            <Play className="mr-2 h-4 w-4 fill-current" /> Run Discovery
          </Button>
        </Link>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">Total Warehouses</CardTitle>
            <Database className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{data?.warehouses.length}</div>
          </CardContent>
        </Card>
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">Discovery Runs</CardTitle>
            <Activity className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{data?.totalRuns}</div>
          </CardContent>
        </Card>
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">Healthy Connections</CardTitle>
            <CheckCircle className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-emerald-500">{data?.healthyCount}</div>
          </CardContent>
        </Card>
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">Attention Needed</CardTitle>
            <AlertCircle className={`h-4 w-4 ${data?.attentionCount ? "text-amber-500" : "text-slate-600"}`} />
          </CardHeader>
          <CardContent>
            <div className={`text-3xl font-bold ${data?.attentionCount ? "text-amber-500" : ""}`}>
              {data?.attentionCount}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium tracking-tight">Your Warehouses</h3>
            <Link href="/warehouses" className="text-sm text-blue-500 hover:underline">
              View all
            </Link>
          </div>
          <div className="grid gap-4">
            {data?.warehouses.slice(0, 3).map((w) => (
              <Card key={w.id} className="bg-slate-900/50 border-slate-800 hover:bg-slate-900 transition-colors">
                <CardContent className="p-4 flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="p-2 bg-slate-800 rounded-lg">
                      <Database className="h-5 w-5 text-blue-400" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-slate-200">{w.name}</h4>
                      <div className="text-sm text-slate-400 flex items-center mt-1">
                        <span className="uppercase text-xs font-semibold mr-2">{w.db_type}</span>
                        <span>•</span>
                        <span className="ml-2">{w.host}:{w.port}</span>
                      </div>
                    </div>
                  </div>
                  <Badge variant={w.is_active ? "default" : "destructive"}>
                    {w.is_active ? "Active" : "Inactive"}
                  </Badge>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium tracking-tight">Recent Discovery Runs</h3>
            <Link href="/history" className="text-sm text-blue-500 hover:underline">
              View history
            </Link>
          </div>
          
          {data?.recentRuns.length === 0 ? (
            <Card className="bg-slate-900/50 border-slate-800 border-dashed">
              <CardContent className="p-8 flex flex-col items-center justify-center text-center">
                <Activity className="h-8 w-8 text-slate-600 mb-4" />
                <p className="text-slate-400 mb-2">No discovery runs yet.</p>
                <Link href="/discovery">
                  <Button variant="outline" size="sm">Run First Discovery</Button>
                </Link>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {data?.recentRuns.map((run) => (
                <Card key={run.session_id} className="bg-slate-900/50 border-slate-800">
                  <CardContent className="p-4 flex items-center justify-between">
                    <div className="flex flex-col">
                      <span className="font-medium text-slate-200 mb-1">{run.warehouseName}</span>
                      <div className="flex items-center text-xs text-slate-500 space-x-3">
                        <span className="flex items-center">
                          <Clock className="mr-1 h-3 w-3" />
                          {new Date(run.started_at).toLocaleString()}
                        </span>
                        {run.total_duration_ms && (
                          <span>{(run.total_duration_ms / 1000).toFixed(1)}s</span>
                        )}
                      </div>
                    </div>
                    <AgentStatus status={run.status} />
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </PageContainer>
  )
}
