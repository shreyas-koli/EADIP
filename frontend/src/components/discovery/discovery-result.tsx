"use client"

import * as React from "react"
import { DiscoverySession } from "@/lib/api/discovery"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { AgentStatus } from "@/components/agent/agent-components"
import { CheckCircle2, Clock, Terminal, ShieldAlert, AlertTriangle, Info, ChevronDown, ChevronRight, Activity, Monitor, AlertCircle } from "lucide-react"

interface DiscoveryResultProps {
  session: DiscoverySession
  warehouseName: string
  monitoringResult?: Record<string, unknown> | null
}

interface PriorityAction {
  title: string
  problem: string
  why_it_matters: string
  recommended_action: string
  priority: string
  impact: string
  effort: string
  confidence: number
  source: string
  location?: {
    schema?: string
    table?: string
    column?: string
  }
}

interface PresentationData {
  overview: {
    total: number
    high: number
    medium: number
    low: number
  }
  priority_actions: PriorityAction[]
}

export function DiscoveryResult({ session, warehouseName, monitoringResult }: DiscoveryResultProps) {
  const [showRaw, setShowRaw] = React.useState(false)
  const executions = session.agent_executions || []
  
  const hasRecommendations = session.recommendations && Object.keys(session.recommendations).length > 0
  const presentation = session.recommendations?.presentation as PresentationData | undefined

  const getPriorityIcon = (priority: string) => {
    switch (priority.toUpperCase()) {
      case "HIGH": return <ShieldAlert className="h-5 w-5 text-red-500" />
      case "MEDIUM": return <AlertTriangle className="h-5 w-5 text-amber-500" />
      case "LOW": return <Info className="h-5 w-5 text-emerald-500" />
      default: return <Info className="h-5 w-5 text-slate-500" />
    }
  }

  return (
    <div className="space-y-6 pb-12">
      <Card className="bg-slate-900 border-emerald-500/30">
        <CardHeader className="border-b border-slate-800 bg-slate-950/50 pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <CheckCircle2 className="h-6 w-6 text-emerald-500" />
              <div>
                <CardTitle className="text-xl">Discovery Completed</CardTitle>
                <div className="text-sm text-slate-400 mt-1">
                  Target: <span className="text-slate-200 font-medium">{warehouseName}</span>
                </div>
              </div>
            </div>
            <div className="flex flex-col items-end">
              <AgentStatus status={session.status} />
              {session.total_duration_ms && (
                <div className="flex items-center text-xs text-slate-500 mt-1">
                  <Clock className="h-3 w-3 mr-1" />
                  {(session.total_duration_ms / 1000).toFixed(1)}s total
                </div>
              )}
            </div>
          </div>
        </CardHeader>
        
        <CardContent className="pt-6 space-y-6">
          {/* Agent Execution Table */}
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-slate-200 flex items-center">
              <Terminal className="h-4 w-4 mr-2 text-slate-400" />
              Agent Execution Summary
            </h4>
            
            <div className="rounded-lg border border-slate-800 overflow-hidden">
              <div className="bg-slate-950/50 px-4 py-2 border-b border-slate-800 grid grid-cols-12 gap-4 text-xs font-medium text-slate-400">
                <div className="col-span-6">Agent</div>
                <div className="col-span-4">Status</div>
                <div className="col-span-2 text-right">Duration</div>
              </div>
              <div className="divide-y divide-slate-800/50">
                {executions.map((exec) => (
                  <div key={exec.agent_name} className="px-4 py-3 grid grid-cols-12 gap-4 items-center bg-slate-900 hover:bg-slate-800/50 transition-colors">
                    <div className="col-span-6 font-medium text-slate-300 text-sm">
                      {exec.agent_name}
                    </div>
                    <div className="col-span-4">
                      <AgentStatus status={exec.status} />
                    </div>
                    <div className="col-span-2 text-right text-xs text-slate-500 font-mono">
                      {exec.duration_ms ? `${(exec.duration_ms / 1000).toFixed(2)}s` : "-"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Monitoring Summary */}
          {monitoringResult && (
            <MonitoringSummary data={monitoringResult} />
          )}

          {/* Presentation Layer rendering */}
          {presentation && (
            <div className="space-y-6 pt-4 border-t border-slate-800">
              
              {/* Database Health Summary */}
              <div>
                <h4 className="text-lg font-semibold text-slate-200 flex items-center mb-4">
                  <Activity className="h-5 w-5 mr-2 text-emerald-400" />
                  Database Health Summary
                </h4>
                <div className="grid grid-cols-4 gap-4">
                  <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4 text-center">
                    <div className="text-3xl font-bold text-slate-200">{presentation.overview.total}</div>
                    <div className="text-xs text-slate-400 mt-1 uppercase tracking-wider">Total</div>
                  </div>
                  <div className="bg-red-950/20 border border-red-900/30 rounded-lg p-4 text-center">
                    <div className="text-3xl font-bold text-red-400">{presentation.overview.high}</div>
                    <div className="text-xs text-red-500/70 mt-1 uppercase tracking-wider">High Priority</div>
                  </div>
                  <div className="bg-amber-950/20 border border-amber-900/30 rounded-lg p-4 text-center">
                    <div className="text-3xl font-bold text-amber-400">{presentation.overview.medium}</div>
                    <div className="text-xs text-amber-500/70 mt-1 uppercase tracking-wider">Medium Priority</div>
                  </div>
                  <div className="bg-emerald-950/20 border border-emerald-900/30 rounded-lg p-4 text-center">
                    <div className="text-3xl font-bold text-emerald-400">{presentation.overview.low}</div>
                    <div className="text-xs text-emerald-500/70 mt-1 uppercase tracking-wider">Low Priority</div>
                  </div>
                </div>
              </div>

              {/* Priority Actions */}
              {presentation.priority_actions && presentation.priority_actions.length > 0 && (
                <div className="space-y-10 pt-6">
                  <h4 className="text-xl font-bold text-slate-200 border-b border-slate-800 pb-2">Priority Actions</h4>
                  
                  {['HIGH', 'MEDIUM', 'LOW'].map((prioLevel) => {
                    const filteredActions = presentation.priority_actions.filter((a: PriorityAction) => a.priority === prioLevel)
                    if (filteredActions.length === 0) return null;
                    
                    return (
                      <div key={prioLevel} className="space-y-4">
                        <h5 className="text-sm font-semibold tracking-wider flex items-center space-x-2">
                          {getPriorityIcon(prioLevel)}
                          <span className={prioLevel === 'HIGH' ? 'text-red-400' : prioLevel === 'MEDIUM' ? 'text-amber-400' : 'text-emerald-400'}>
                            {prioLevel} PRIORITY ({filteredActions.length})
                          </span>
                        </h5>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                          {filteredActions.map((action: PriorityAction, idx: number) => (
                            <div key={idx} className={`rounded-xl border p-5 flex flex-col bg-slate-900/80 shadow-lg ${
                              action.priority === "HIGH" ? "border-red-900/50" :
                              action.priority === "MEDIUM" ? "border-amber-900/50" :
                              "border-slate-800"
                            }`}>
                              
                              <div className="flex items-start justify-between mb-3">
                                <div className="flex items-center space-x-3">
                                  {getPriorityIcon(action.priority)}
                                  <h5 className="text-base font-medium text-slate-200 leading-tight">{action.title}</h5>
                                </div>
                              </div>

                              {action.location && (action.location.schema || action.location.table) && (
                                <div className="flex items-center space-x-1 mb-4 text-xs font-mono bg-slate-950/50 px-2 py-1 rounded-md border border-slate-800 self-start">
                                  <span className="text-slate-400">{action.location.schema || "public"}</span>
                                  <span className="text-slate-600">.</span>
                                  <span className="text-sky-400">{action.location.table}</span>
                                  {action.location.column && (
                                    <>
                                      <span className="text-slate-600">.</span>
                                      <span className="text-purple-400">{action.location.column}</span>
                                    </>
                                  )}
                                </div>
                              )}

                              <div className="flex-1 space-y-4 mb-5">
                                <div>
                                  <h6 className="text-[10px] text-slate-500 uppercase tracking-wider font-bold mb-1">Problem</h6>
                                  <p className="text-sm text-slate-300">{action.problem}</p>
                                </div>
                                <div>
                                  <h6 className="text-[10px] text-slate-500 uppercase tracking-wider font-bold mb-1">Why It Matters</h6>
                                  <p className="text-sm text-slate-300">{action.why_it_matters}</p>
                                </div>
                                <div className="bg-indigo-950/20 border border-indigo-900/30 p-3 rounded-lg">
                                  <h6 className="text-[10px] text-indigo-400/80 uppercase tracking-wider font-bold mb-1">Recommended Action</h6>
                                  <p className="text-sm text-indigo-200">{action.recommended_action}</p>
                                </div>
                              </div>
                              
                              {/* Compact Metadata Footer */}
                              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-3 border-t border-slate-800/80 mt-auto">
                                <div className="flex items-center">
                                  <span className="text-[10px] text-slate-500 mr-1.5 uppercase">Impact:</span>
                                  <span className="text-xs font-medium text-slate-300">{action.impact}</span>
                                </div>
                                <div className="flex items-center">
                                  <span className="text-[10px] text-slate-500 mr-1.5 uppercase">Effort:</span>
                                  <span className="text-xs font-medium text-slate-300">{action.effort}</span>
                                </div>
                                <div className="flex items-center">
                                  <span className="text-[10px] text-slate-500 mr-1.5 uppercase">Confidence:</span>
                                  <span className="text-xs font-medium text-slate-300">{action.confidence}%</span>
                                </div>
                                <div className="flex items-center w-full mt-1">
                                  <span className="text-[10px] text-slate-500 mr-1.5 uppercase">Source:</span>
                                  <span className="text-xs text-slate-400 truncate">{action.source}</span>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* Fallback or Developer View for Raw JSON */}
          {hasRecommendations && (
            <div className="pt-6 border-t border-slate-800 mt-6">
              <button 
                onClick={() => setShowRaw(!showRaw)}
                className="flex items-center text-sm text-slate-400 hover:text-slate-300 transition-colors"
              >
                {showRaw ? <ChevronDown className="h-4 w-4 mr-1" /> : <ChevronRight className="h-4 w-4 mr-1" />}
                View Raw Diagnostic Data
              </button>
              
              {showRaw && (
                <div className="mt-4 rounded-lg bg-slate-950/80 border border-slate-800 p-4 overflow-hidden">
                  <pre className="text-xs text-slate-400 font-mono whitespace-pre-wrap overflow-x-auto max-h-[500px] overflow-y-auto">
                    {JSON.stringify(session.recommendations, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

interface MonitoringFinding {
  category: string
  severity: "CRITICAL" | "WARNING" | "INFO"
  title: string
  description?: string
  evidence?: Record<string, unknown> | string
}

interface MonitoringError {
  section?: string
  step?: string
  error: string
}

interface PgSession {
  duration_seconds: number
  query_text: string
}

interface PgProcess {
  pid: number
  db_state: string
  cpu_percent?: number
  memory_rss_bytes?: number
  os_status: string
}

function MonitoringSummary({ data }: { data: Record<string, unknown> }) {
  const summary = (data?.summary as Record<string, unknown>) || {}
  const findings = (data?.findings as MonitoringFinding[]) || []
  const errors = (data?.errors as MonitoringError[]) || []
  const partial = summary?.partial_failure === true
  
  const pg = {
    connections: data?.connections as Record<string, unknown>,
    queries: data?.queries as Record<string, unknown>,
    locks: data?.locks as Record<string, unknown>,
    transactions: data?.transactions as Record<string, unknown>,
    waiting: data?.waiting_queries as Record<string, unknown>,
    db: data?.database as Record<string, unknown>,
    perf: data?.performance as Record<string, unknown>,
  }
  const sys = (data?.system as Record<string, unknown>) || {}
  const cpu = sys?.cpu as Record<string, unknown>
  const memory = sys?.memory as Record<string, unknown>
  const disk = sys?.disk as Record<string, unknown>
  const network = sys?.network as Record<string, unknown>
  const pg_processes = sys?.pg_processes as Record<string, unknown>
  const net_deltas = network?.deltas as Record<string, unknown>
  const process_agg = pg_processes?.aggregate as Record<string, unknown>
  
  const formatMB = (bytes?: number) => {
    if (bytes === undefined || bytes === null) return "-"
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }
  const formatGB = (bytes?: number) => {
    if (bytes === undefined || bytes === null) return "-"
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
  }

  const [expanded, setExpanded] = React.useState(false)

  return (
    <div className="space-y-6 pt-4 border-t border-slate-800">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-lg font-semibold text-slate-200 flex items-center">
          <Monitor className="h-5 w-5 mr-2 text-blue-400" />
          Monitoring Result
        </h4>
        <div className="flex items-center space-x-3">
          {partial && (
            <div className="flex items-center text-amber-500 text-sm font-medium bg-amber-500/10 px-3 py-1 rounded-full border border-amber-500/20">
              <AlertCircle className="h-4 w-4 mr-2" />
              Partial Data
            </div>
          )}
          <div className={`px-4 py-1 rounded-full font-bold text-sm tracking-wider flex items-center ${
            summary.health_status === "CRITICAL" ? "bg-red-500/20 text-red-500 border border-red-500/30" :
            summary.health_status === "WARNING" ? "bg-amber-500/20 text-amber-500 border border-amber-500/30" :
            "bg-emerald-500/20 text-emerald-500 border border-emerald-500/30"
          }`}>
            {summary.health_status === "CRITICAL" && <ShieldAlert className="w-4 h-4 mr-2" />}
            {summary.health_status === "WARNING" && <AlertTriangle className="w-4 h-4 mr-2" />}
            {summary.health_status === "HEALTHY" && <CheckCircle2 className="w-4 h-4 mr-2" />}
            {(summary.health_status as string) || "UNKNOWN"}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* HOST */}
        <div className="bg-slate-900/60 border border-slate-700/50 rounded-xl p-5 shadow-sm">
          <h5 className="text-xs font-bold text-slate-400 tracking-wider uppercase mb-4 border-b border-slate-800 pb-2">Host / System</h5>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-slate-400 text-sm">CPU</span>
              <span className="text-slate-200 font-medium">{(cpu?.utilization_percent as number)?.toFixed(1) ?? "-"}%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-400 text-sm">Memory</span>
              <span className="text-slate-200 font-medium">{(memory?.utilization_percent as number)?.toFixed(1) ?? "-"}%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-400 text-sm">Disk</span>
              <span className="text-slate-200 font-medium">{(disk?.utilization_percent as number)?.toFixed(1) ?? "-"}%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-400 text-sm">Network</span>
              <span className="text-slate-200 font-medium text-xs">
                ↓ {(net_deltas?.recv_mb_s as number)?.toFixed(1) ?? "-"} / ↑ {(net_deltas?.sent_mb_s as number)?.toFixed(1) ?? "-"} MB/s
              </span>
            </div>
          </div>
        </div>

        {/* POSTGRESQL */}
        <div className="bg-slate-900/60 border border-slate-700/50 rounded-xl p-5 shadow-sm">
          <h5 className="text-xs font-bold text-slate-400 tracking-wider uppercase mb-4 border-b border-slate-800 pb-2">PostgreSQL</h5>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-slate-400 text-sm">Connections</span>
              <span className="text-slate-200 font-medium">{(pg.connections?.current as number) ?? "-"} / {(pg.connections?.maximum as number) ?? "-"}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-400 text-sm">Active</span>
              <span className="text-slate-200 font-medium">{(pg.queries?.running_count as number) ?? "-"}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-400 text-sm">Waiting</span>
              <span className="text-slate-200 font-medium">{(pg.waiting?.waiting_count as number) ?? "-"}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-400 text-sm">Blocking</span>
              <span className="text-slate-200 font-medium">{(pg.locks?.blocked_sessions as number) ?? "-"}</span>
            </div>
          </div>
        </div>

        {/* PG PROCESSES */}
        <div className="bg-slate-900/60 border border-slate-700/50 rounded-xl p-5 shadow-sm">
          <h5 className="text-xs font-bold text-slate-400 tracking-wider uppercase mb-4 border-b border-slate-800 pb-2">PG Processes</h5>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-slate-400 text-sm">Backend Processes</span>
              <span className="text-slate-200 font-medium">{(pg_processes?.pids_tracked as number) ?? "-"}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-400 text-sm">Aggregate CPU</span>
              <span className="text-slate-200 font-medium">{(process_agg?.total_cpu_percent as number)?.toFixed(1) ?? "-"}%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-400 text-sm">Aggregate Memory</span>
              <span className="text-slate-200 font-medium">{formatMB(process_agg?.total_memory_rss_bytes as number)}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-6">
        <h5 className="text-sm font-semibold tracking-wider text-slate-300 mb-3 uppercase">Findings & Alerts</h5>
        <div className="space-y-3">
          {findings.length === 0 && errors.length === 0 ? (
            <div className="flex items-center text-emerald-400 text-sm bg-emerald-500/10 px-4 py-4 rounded-xl border border-emerald-500/20 shadow-sm">
              <CheckCircle2 className="h-5 w-5 mr-3" />
              No monitoring issues detected. PostgreSQL and Host are operating normally.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {errors.map((err: MonitoringError, idx: number) => (
                <div key={`err-${idx}`} className="flex items-start space-x-3 bg-amber-500/10 px-4 py-4 rounded-xl border border-amber-500/30 shadow-sm">
                  <AlertTriangle className="h-5 w-5 text-amber-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <h6 className="text-sm font-semibold text-amber-500 uppercase tracking-wide">Warning: Telemetry Unavailable</h6>
                    <p className="text-xs text-amber-400/90 mt-1.5 leading-relaxed">{err.section || err.step}: {err.error}</p>
                  </div>
                </div>
              ))}
              {findings.map((finding: MonitoringFinding, idx: number) => {
                const isCorr = finding.category?.toUpperCase() === "CORRELATION"
                return (
                  <div key={`finding-${idx}`} className={`flex items-start space-x-3 px-4 py-4 rounded-xl border shadow-sm ${
                    isCorr ? "bg-indigo-500/10 border-indigo-500/30" :
                    finding.severity === "CRITICAL" ? "bg-red-500/10 border-red-500/30" :
                    finding.severity === "WARNING" ? "bg-amber-500/10 border-amber-500/30" :
                    "bg-slate-800/50 border-slate-700/50"
                  }`}>
                    {isCorr ? (
                      <Activity className="h-5 w-5 text-indigo-400 mt-0.5 flex-shrink-0" />
                    ) : finding.severity === "CRITICAL" ? (
                      <ShieldAlert className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
                    ) : finding.severity === "WARNING" ? (
                      <AlertTriangle className="h-5 w-5 text-amber-500 mt-0.5 flex-shrink-0" />
                    ) : (
                      <Info className="h-5 w-5 text-blue-400 mt-0.5 flex-shrink-0" />
                    )}
                    <div className="flex-1 w-full overflow-hidden">
                      <div className="flex justify-between items-center mb-1">
                        <h6 className={`text-[10px] font-bold uppercase tracking-wider ${
                          isCorr ? "text-indigo-400" :
                          finding.severity === "CRITICAL" ? "text-red-500" :
                          finding.severity === "WARNING" ? "text-amber-500" :
                          "text-blue-400"
                        }`}>
                          {isCorr ? "CORRELATION" : finding.severity}
                        </h6>
                        <span className="text-[10px] text-slate-500 uppercase font-medium">{finding.category}</span>
                      </div>
                      <p className="text-sm text-slate-200 font-medium leading-tight">{finding.title}</p>
                      {finding.description && (
                        <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">{finding.description}</p>
                      )}
                      {finding.evidence && (
                        <div className="mt-3 bg-slate-950/50 border border-slate-800/80 rounded-md p-2 text-xs font-mono text-slate-400 overflow-x-auto">
                          {typeof finding.evidence === 'object' ? Object.entries(finding.evidence as Record<string, unknown>).map(([k, v]) => (
                            <div key={k} className="flex space-x-2">
                              <span className="text-slate-500">{k}:</span>
                              <span className="text-slate-300">{Array.isArray(v) ? v.join(", ") : String(v)}</span>
                            </div>
                          )) : String(finding.evidence)}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Expandable Details Panel */}
      <div className="pt-4 border-t border-slate-800 mt-6">
        <button 
          onClick={() => setExpanded(!expanded)}
          className="flex items-center text-sm font-medium text-slate-400 hover:text-slate-300 transition-colors"
        >
          {expanded ? <ChevronDown className="h-4 w-4 mr-1" /> : <ChevronRight className="h-4 w-4 mr-1" />}
          View Detailed Telemetry
        </button>
        
        {expanded && (
          <div className="mt-6 space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              
              {/* Host Details */}
              <div className="space-y-4 bg-slate-900/30 p-5 rounded-xl border border-slate-800/50">
                <h5 className="text-sm font-semibold text-slate-300 border-b border-slate-800 pb-2">Host & System</h5>
                <div className="space-y-3">
                  <div>
                    <h6 className="text-xs text-slate-500 uppercase tracking-wider mb-1">CPU</h6>
                    <p className="text-sm text-slate-300 font-mono">{(cpu?.logical_cores as number) ?? "-"} logical cores, {(cpu?.physical_cores as number) ?? "-"} physical</p>
                  </div>
                  <div>
                    <h6 className="text-xs text-slate-500 uppercase tracking-wider mb-1">Memory</h6>
                    <p className="text-sm text-slate-300 font-mono">Total: {formatGB(memory?.total_bytes as number)} • Used: {formatGB(memory?.used_bytes as number)}</p>
                    <p className="text-sm text-slate-300 font-mono">Available: {formatGB(memory?.available_bytes as number)} • Swap: {(memory?.swap_percent as number) ?? "-"}%</p>
                  </div>
                  <div>
                    <h6 className="text-xs text-slate-500 uppercase tracking-wider mb-1">Disk ({(disk?.mountpoint as string) || '/'})</h6>
                    <p className="text-sm text-slate-300 font-mono">Capacity: {formatGB(disk?.capacity_bytes as number)} • Free: {formatGB(disk?.free_bytes as number)}</p>
                    <p className="text-sm text-slate-300 font-mono">Read: {(disk?.read_mb_s as number)?.toFixed(2) ?? "-"} MB/s • Write: {(disk?.write_mb_s as number)?.toFixed(2) ?? "-"} MB/s</p>
                  </div>
                  <div>
                    <h6 className="text-xs text-slate-500 uppercase tracking-wider mb-1">Network</h6>
                    <p className="text-sm text-slate-300 font-mono">RX: {(net_deltas?.recv_mb_s as number)?.toFixed(2) ?? "-"} MB/s • TX: {(net_deltas?.sent_mb_s as number)?.toFixed(2) ?? "-"} MB/s</p>
                    <p className="text-sm text-slate-300 font-mono">Errors: {(net_deltas?.errors_delta as number) ?? "-"} • Drops: {(net_deltas?.drops_delta as number) ?? "-"}</p>
                  </div>
                </div>
              </div>

              {/* Postgres Details */}
              <div className="space-y-4 bg-slate-900/30 p-5 rounded-xl border border-slate-800/50">
                <h5 className="text-sm font-semibold text-slate-300 border-b border-slate-800 pb-2">PostgreSQL Internal</h5>
                <div className="space-y-3">
                  <div>
                    <h6 className="text-xs text-slate-500 uppercase tracking-wider mb-1">Database Size</h6>
                    <p className="text-sm text-slate-300 font-mono">{(pg.db?.size_pretty as string) || "-"}</p>
                  </div>
                  <div>
                    <h6 className="text-xs text-slate-500 uppercase tracking-wider mb-1">Transactions</h6>
                    <p className="text-sm text-slate-300 font-mono">Idle in tx: {(pg.transactions?.idle_in_transaction as number) || 0} • Active: {(pg.transactions?.active as number) || 0}</p>
                  </div>
                  <div>
                    <h6 className="text-xs text-slate-500 uppercase tracking-wider mb-1">Performance</h6>
                    <p className="text-sm text-slate-300 font-mono">Cache Hit Ratio: {pg.perf?.cache_hit_ratio !== null && pg.perf?.cache_hit_ratio !== undefined ? `${pg.perf.cache_hit_ratio}%` : "-"}</p>
                  </div>
                  <div>
                    <h6 className="text-xs text-slate-500 uppercase tracking-wider mb-1">Active Queries</h6>
                    {Array.isArray(pg.queries?.sessions) && pg.queries.sessions.length > 0 ? (
                      <div className="max-h-32 overflow-y-auto space-y-2 mt-2">
                        {pg.queries.sessions.map((q: PgSession, i: number) => (
                          <div key={i} className="text-xs font-mono text-slate-400 bg-slate-950 p-2 rounded">
                            <span className="text-slate-500">[{q.duration_seconds}s]</span> {q.query_text}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-slate-500 font-mono">No active queries found.</p>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Process List */}
            {Array.isArray(pg_processes?.processes) && pg_processes.processes.length > 0 && (
              <div className="bg-slate-900/30 p-5 rounded-xl border border-slate-800/50">
                <h5 className="text-sm font-semibold text-slate-300 border-b border-slate-800 pb-3 mb-3">PostgreSQL OS Processes ({pg_processes.processes.length})</h5>
                <div className="max-h-60 overflow-y-auto">
                  <table className="w-full text-sm text-left font-mono">
                    <thead className="text-[10px] uppercase text-slate-500 sticky top-0 bg-slate-950 p-2">
                      <tr>
                        <th className="py-2 px-2">PID</th>
                        <th className="py-2 px-2">State</th>
                        <th className="py-2 px-2">CPU</th>
                        <th className="py-2 px-2">Memory (RSS)</th>
                        <th className="py-2 px-2">OS Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                      {pg_processes.processes.map((proc: PgProcess, i: number) => (
                        <tr key={i} className="hover:bg-slate-800/50">
                          <td className="py-2 px-2 text-slate-300">{proc.pid}</td>
                          <td className="py-2 px-2 text-sky-400">{proc.db_state}</td>
                          <td className="py-2 px-2 text-slate-300">{proc.cpu_percent?.toFixed(1)}%</td>
                          <td className="py-2 px-2 text-slate-300">{formatMB(proc.memory_rss_bytes)}</td>
                          <td className="py-2 px-2 text-slate-400">{proc.os_status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            
          </div>
        )}
      </div>
    </div>
  )
}


