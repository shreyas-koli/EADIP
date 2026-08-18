"use client"

import * as React from "react"
import { DiscoverySession } from "@/lib/api/discovery"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { AgentStatus } from "@/components/agent/agent-components"
import { CheckCircle2, Clock, Terminal, ShieldAlert, AlertTriangle, Info, ChevronDown, ChevronRight, Activity } from "lucide-react"

interface DiscoveryResultProps {
  session: DiscoverySession
  warehouseName: string
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

export function DiscoveryResult({ session, warehouseName }: DiscoveryResultProps) {
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
