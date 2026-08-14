import * as React from "react"
import { LucideIcon, CheckCircle2, XCircle, Clock, AlertCircle } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

export type AgentState = "WAITING" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED"

interface AgentStatusProps {
  status: AgentState
  className?: string
}

export function AgentStatus({ status, className }: AgentStatusProps) {
  const statusConfig = {
    WAITING: { icon: Clock, color: "text-slate-400", label: "Waiting" },
    RUNNING: { icon: Clock, color: "text-blue-500 animate-pulse", label: "Running" },
    COMPLETED: { icon: CheckCircle2, color: "text-emerald-500", label: "Completed" },
    FAILED: { icon: XCircle, color: "text-red-500", label: "Failed" },
    SKIPPED: { icon: AlertCircle, color: "text-yellow-500", label: "Skipped" },
  }

  const config = statusConfig[status]
  const Icon = config.icon

  return (
    <div className={cn("flex items-center space-x-2", className)}>
      <Icon className={cn("h-4 w-4", config.color)} />
      <span className={cn("text-sm font-medium", config.color)}>{config.label}</span>
    </div>
  )
}

interface AgentCardProps {
  name: string
  description: string
  icon: LucideIcon
  status: AgentState
  durationMs?: number
  className?: string
}

export function AgentCard({ name, description, icon: Icon, status, durationMs, className }: AgentCardProps) {
  return (
    <Card className={cn("flex flex-col", className)}>
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
        <div className="flex items-center space-x-2">
          <div className="rounded-md bg-slate-800 p-2">
            <Icon className="h-4 w-4 text-slate-300" />
          </div>
          <div className="space-y-1">
            <CardTitle className="text-base">{name}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="mt-auto flex items-center justify-between pt-4">
        <AgentStatus status={status} />
        {durationMs !== undefined && (
          <span className="text-xs text-slate-500">{durationMs}ms</span>
        )}
      </CardContent>
    </Card>
  )
}

interface AgentResultCardProps {
  title: string
  children: React.ReactNode
  className?: string
}

export function AgentResultCard({ title, children, className }: AgentResultCardProps) {
  return (
    <Card className={cn("overflow-hidden", className)}>
      <div className="border-b border-slate-800 bg-slate-900/50 px-4 py-3">
        <h4 className="text-sm font-semibold text-slate-200">{title}</h4>
      </div>
      <div className="p-4 bg-slate-950/50">
        {children}
      </div>
    </Card>
  )
}
