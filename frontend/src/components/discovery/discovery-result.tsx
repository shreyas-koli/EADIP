"use client"

import * as React from "react"
import { DiscoverySession } from "@/lib/api/discovery"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { AgentStatus } from "@/components/agent/agent-components"
import { CheckCircle2, Clock, Terminal } from "lucide-react"

interface DiscoveryResultProps {
  session: DiscoverySession
  warehouseName: string
}

export function DiscoveryResult({ session, warehouseName }: DiscoveryResultProps) {
  const executions = session.agent_executions || []
  
  return (
    <div className="space-y-6">
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

          {session.recommendations && Object.keys(session.recommendations).length > 0 && (
            <div className="space-y-3 pt-2">
              <h4 className="text-sm font-semibold text-slate-200">Key Recommendations</h4>
              <div className="rounded-lg bg-blue-900/10 border border-blue-900/30 p-4">
                <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap overflow-x-auto">
                  {JSON.stringify(session.recommendations, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
