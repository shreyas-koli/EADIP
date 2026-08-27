"use client"

import * as React from "react"
import { AgentExecution } from "@/lib/api/discovery"
import { AgentStatus } from "@/components/agent/agent-components"
import { Card } from "@/components/ui/card"
import { Shield, FileText, BarChart, CheckSquare, Search, Lightbulb, Loader2, CheckCircle2, XCircle, Monitor } from "lucide-react"

interface AgentExecutionCardProps {
  name: string
  execution?: AgentExecution
  isActive?: boolean
  events?: Record<string, unknown>[]
  isInitializing?: boolean
  isReplaying?: boolean
}

const parseTime = (isoString?: string) => {
  return isoString ? new Date(isoString).getTime() : undefined
}

const formatDuration = (ms: number) => {
  const seconds = (ms / 1000).toFixed(3)
  return `${seconds.padStart(6, '0')}s`
}

export function AgentExecutionCard({ name, execution, isActive, events = [], isInitializing, isReplaying }: AgentExecutionCardProps) {
  // Map agent name to backend key
  const backendName = name.split(" ")[0].toLowerCase()

  // State
  const [progressFrames, setProgressFrames] = React.useState(0)
  const [now, setNow] = React.useState<number>(() => Date.now())
  
  // Timer loop & Progress animation
  React.useEffect(() => {
    // Start interval immediately when live
    if (isInitializing || isActive) {
      const interval = setInterval(() => {
        setNow(Date.now())
        setProgressFrames(f => (f + 1) % 15)
      }, 50)
      return () => clearInterval(interval)
    }
  }, [isInitializing, isActive])

  // Derive live state without useEffect
  let liveStatus: "WAITING" | "INITIALIZING" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED" = "WAITING"
  let startedAt: number | null = null
  let finishedAt: number | null = null
  let durationMs: number | null = null
  let activityLogs: string[] = []
  let currentProgress: number | null = null

  if (isInitializing) {
    liveStatus = "INITIALIZING"
    activityLogs = [`Preparing ${name}...`]
  } else if (!isActive && !execution) {
    liveStatus = "WAITING"
    if (backendName === "security" || backendName === "data") {
      activityLogs = ["Waiting for Wave 1 dependencies..."]
    } else if (backendName === "recommendation") {
      activityLogs = ["Waiting for upstream agents..."]
    } else {
      activityLogs = ["Queued for execution..."]
    }
  } else if (execution && !isReplaying) {
    // If we already have the final execution and are NOT replaying, set it
    liveStatus = execution.status as "COMPLETED" | "FAILED" | "SKIPPED" | "RUNNING" | "WAITING"
    if (execution.started_at) startedAt = parseTime(execution.started_at) || null
    if (execution.finished_at) finishedAt = parseTime(execution.finished_at) || null
    if (execution.duration_ms) durationMs = execution.duration_ms
    activityLogs = [execution.status === "FAILED" ? "Execution failed." : "Analysis completed."]
  } else {
    // Parse stream events to derive live state or replay display state
    events.forEach(ev => {
      const evAgent = ev.agent as string
      if (evAgent === backendName || (backendName === "data" && evAgent === "data_quality")) {
        if (ev.event === "agent_started") {
          liveStatus = "RUNNING"
          if (!startedAt) startedAt = parseTime(ev.timestamp as string) || now
        } else if (ev.event === "agent_completed") {
          liveStatus = "COMPLETED"
          if (!finishedAt) finishedAt = parseTime(ev.timestamp as string) || now
          if (startedAt && !durationMs) durationMs = finishedAt - startedAt
        } else if (ev.event === "agent_failed") {
          liveStatus = "FAILED"
          if (!finishedAt) finishedAt = parseTime(ev.timestamp as string) || now
          if (startedAt && !durationMs) durationMs = finishedAt - startedAt
        } else if (ev.event === "agent_skipped") {
          liveStatus = "SKIPPED"
        } else if (ev.event === "agent_progress") {
          if (ev.message) activityLogs.push(ev.message as string)
          if (ev.progress !== undefined && ev.progress !== null) {
            currentProgress = ev.progress as number
          }
        }
      }
    })
    
    if (liveStatus === "WAITING") {
      if (backendName === "security" || backendName === "data") {
        activityLogs = ["Waiting for Wave 1 dependencies..."]
      } else if (backendName === "recommendation") {
        activityLogs = ["Waiting for upstream agents..."]
      } else {
        activityLogs = ["Queued for execution..."]
      }
    }
  }

  // Ensure we show at most 3-4 logs to keep UI clean
  const visibleLogs = activityLogs.slice(-4)

  const getIcon = (n: string) => {
    const nl = n.toLowerCase()
    if (nl.includes("metadata")) return <FileText className="h-5 w-5" />
    if (nl.includes("statistic")) return <BarChart className="h-5 w-5" />
    if (nl.includes("security")) return <Shield className="h-5 w-5" />
    if (nl.includes("data")) return <CheckSquare className="h-5 w-5" />
    if (nl.includes("recommendation")) return <Lightbulb className="h-5 w-5" />
    if (nl.includes("monitoring")) return <Monitor className="h-5 w-5" />
    return <Search className="h-5 w-5" />
  }

  const borderStyles = {
    WAITING: "border-slate-800 bg-slate-900/40 text-slate-500",
    INITIALIZING: "border-blue-500/30 bg-slate-900 ring-1 ring-blue-500/10",
    RUNNING: "border-blue-500/50 bg-slate-900 shadow-[0_0_15px_rgba(59,130,246,0.1)] ring-1 ring-blue-500/20",
    COMPLETED: "border-emerald-500/50 bg-slate-900 ring-1 ring-emerald-500/20",
    FAILED: "border-red-500/50 bg-slate-900 ring-1 ring-red-500/20",
    SKIPPED: "border-slate-600/50 bg-slate-900/80 text-slate-400",
  }

  const isLive = liveStatus === "INITIALIZING" || liveStatus === "RUNNING" || liveStatus === "COMPLETED" || liveStatus === "FAILED"
  const showWaitLogs = liveStatus === "WAITING" && isActive

  const generateProgressString = () => {
    if (currentProgress !== null) {
      const length = 18
      const filled = Math.round((currentProgress / 100) * length)
      const empty = length - filled
      return `${'█'.repeat(filled)}${'░'.repeat(empty)} ${currentProgress}%`
    } else {
      const length = 18
      const pos = progressFrames
      const arr = Array(length).fill('░')
      for (let i = 0; i < 4; i++) {
        arr[(pos + i) % length] = '█'
      }
      return `[${arr.join('')}] Processing...`
    }
  }
  
  const formatClockTime = (ts: number) => {
    return new Date(ts).toLocaleTimeString(undefined, { hour12: false })
  }
  
  const currentElapsed = liveStatus === "RUNNING" && startedAt ? formatDuration(now - startedAt) : 
                   (durationMs ? formatDuration(durationMs) : (liveStatus === "INITIALIZING" ? "00.000s" : "---"))

  return (
    <Card className={`flex flex-col p-4 transition-all duration-500 ${borderStyles[liveStatus]} ${isLive || showWaitLogs ? 'w-[320px] min-h-[260px]' : 'w-[240px]'}`}>
      <div className="flex items-center space-x-3 mb-4">
        <div className={`p-2 rounded-lg ${
          liveStatus === "WAITING" ? "bg-slate-800/50" : "bg-slate-800"
        }`}>
          {getIcon(name)}
        </div>
        <div className={`font-semibold text-sm flex-grow ${
          liveStatus === "WAITING" ? "text-slate-400" : "text-slate-200"
        }`}>
          {name}
        </div>
        {liveStatus === "INITIALIZING" && <Loader2 className="h-4 w-4 animate-spin text-blue-400" />}
      </div>
      
      {/* CLI Processing UI */}
      {(isLive || showWaitLogs) && (
        <div className="flex flex-col space-y-3 font-mono text-[11px] leading-tight text-slate-400 bg-[#050505] p-3 rounded border border-slate-800/80 flex-grow relative overflow-hidden shadow-inner">
          
          <div className="flex justify-between items-center border-b border-slate-800 pb-2">
            <div className="flex items-center space-x-2">
              {liveStatus === "WAITING" && <span className="text-slate-500">● QUEUED</span>}
              {liveStatus === "RUNNING" && <span className="text-blue-400 flex items-center gap-1.5"><Loader2 className="h-3 w-3 animate-spin"/> RUNNING</span>}
              {liveStatus === "INITIALIZING" && <span className="text-blue-400 font-semibold tracking-wide">INITIALIZING</span>}
              {liveStatus === "COMPLETED" && <span className="text-emerald-400 flex items-center gap-1.5"><CheckCircle2 className="h-3 w-3" /> COMPLETED</span>}
              {liveStatus === "FAILED" && <span className="text-red-400 flex items-center gap-1.5"><XCircle className="h-3 w-3" /> FAILED</span>}
            </div>
          </div>

          <div className="flex flex-col space-y-1.5 py-1">
             <span className="text-slate-500 font-semibold mb-1">Current activity:</span>
             <div className="min-h-[3rem] flex flex-col justify-end">
               {visibleLogs.map((log, i) => (
                 <span key={i} className={`${i === visibleLogs.length - 1 ? 'text-slate-300 font-medium' : 'text-slate-600 truncate opacity-70'}`}>
                   {i === visibleLogs.length - 1 ? (liveStatus === "RUNNING" || liveStatus === "INITIALIZING" ? '→ ' : '✓ ') : '→ '}{log}
                 </span>
               ))}
             </div>
          </div>

          {(liveStatus === "RUNNING" || liveStatus === "INITIALIZING") && (
            <div className="flex items-center space-x-2 mt-auto pt-2">
              <span className="text-emerald-500 tracking-widest text-[11px] w-full flex items-center gap-2">
                Progress: {generateProgressString()}
              </span>
            </div>
          )}

          <div className="flex flex-col space-y-1 mt-auto pt-3 border-t border-slate-800/80">
             {startedAt && (
               <div className="flex justify-between">
                 <span className="text-slate-500">Started:</span>
                 <span className="text-slate-200">{formatClockTime(startedAt)}</span>
               </div>
             )}
             {(finishedAt || liveStatus === "COMPLETED") && finishedAt && (
               <div className="flex justify-between">
                 <span className="text-slate-500">Finished:</span>
                 <span className="text-slate-200">{formatClockTime(finishedAt)}</span>
               </div>
             )}
             <div className="flex justify-between mt-1">
               <span className="text-slate-500">{liveStatus === "COMPLETED" ? "Total execution time:" : "Elapsed:"}</span>
               <span className="text-slate-200">{currentElapsed}</span>
             </div>
          </div>
        </div>
      )}

      {!isLive && !showWaitLogs && (
        <div className="flex items-center justify-between mt-auto pt-2">
          <AgentStatus status={liveStatus as "WAITING" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED"} />
        </div>
      )}
    </Card>
  )
}
