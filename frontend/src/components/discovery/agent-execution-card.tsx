"use client"

import * as React from "react"
import { AgentExecution } from "@/lib/api/discovery"
import { AgentStatus } from "@/components/agent/agent-components"
import { Card } from "@/components/ui/card"
import { Shield, FileText, BarChart, CheckSquare, Search, Lightbulb } from "lucide-react"

interface AgentExecutionCardProps {
  name: string
  execution?: AgentExecution
  isActive?: boolean
}

export function AgentExecutionCard({ name, execution, isActive }: AgentExecutionCardProps) {
  // Derive status
  const status = execution?.status || (isActive ? "RUNNING" : "WAITING")

  // Map agent name to icon
  const getIcon = (agentName: string) => {
    const n = agentName.toLowerCase()
    if (n.includes("metadata")) return <FileText className="h-5 w-5" />
    if (n.includes("statistic")) return <BarChart className="h-5 w-5" />
    if (n.includes("security")) return <Shield className="h-5 w-5" />
    if (n.includes("data quality") || n.includes("dataquality")) return <CheckSquare className="h-5 w-5" />
    if (n.includes("recommendation")) return <Lightbulb className="h-5 w-5" />
    return <Search className="h-5 w-5" />
  }

  // Visual styling based on status
  const borderStyles = {
    WAITING: "border-slate-800 bg-slate-900/40 text-slate-500",
    RUNNING: "border-blue-500/50 bg-slate-900 shadow-[0_0_15px_rgba(59,130,246,0.1)] ring-1 ring-blue-500/20",
    COMPLETED: "border-emerald-500/30 bg-slate-900/80",
    FAILED: "border-red-500/30 bg-slate-900/80",
    SKIPPED: "border-amber-500/30 bg-slate-900/80",
  }

  return (
    <Card className={`flex flex-col p-4 w-[240px] transition-all duration-500 ${borderStyles[status]}`}>
      <div className="flex items-center space-x-3 mb-4">
        <div className={`p-2 rounded-lg ${
          status === "WAITING" ? "bg-slate-800/50" : "bg-slate-800"
        }`}>
          {getIcon(name)}
        </div>
        <div className={`font-semibold text-sm ${
          status === "WAITING" ? "text-slate-400" : "text-slate-200"
        }`}>
          {name}
        </div>
      </div>
      
      <div className="flex items-center justify-between mt-auto">
        <AgentStatus status={status} />
        {execution?.duration_ms && (
          <span className="text-xs text-slate-500 font-medium">
            {(execution.duration_ms / 1000).toFixed(1)}s
          </span>
        )}
      </div>
    </Card>
  )
}
