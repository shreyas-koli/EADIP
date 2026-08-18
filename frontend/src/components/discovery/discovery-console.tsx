"use client"

import { useState, useEffect } from "react"
import { Terminal, Clock, CheckCircle2, XCircle, Loader2 } from "lucide-react"

type AgentState = "WAITING" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED"

interface AgentData {
  name: string
  status: AgentState
  startedAt?: number
  durationMs?: number
  logs: string[]
  error?: string
}

interface DiscoveryConsoleProps {
  warehouseName: string
  isComplete: boolean
  events: Record<string, unknown>[]
  totalDurationMs?: number
  isInitializing?: boolean
  initCountdown?: number
}

// Convert ISO string to timestamp
const parseTime = (isoString?: string) => {
  return isoString ? new Date(isoString).getTime() : undefined
}

// Format duration
const formatDuration = (ms: number) => {
  const seconds = (ms / 1000).toFixed(2)
  return `${seconds.padStart(5, '0')}s`
}

export function DiscoveryConsole({ warehouseName, isComplete, events, totalDurationMs, isInitializing, initCountdown }: DiscoveryConsoleProps) {
  const [now, setNow] = useState<number>(() => Date.now())
  
  // Update live timer
  useEffect(() => {
    if (isComplete) return
    const interval = setInterval(() => setNow(Date.now()), 50)
    return () => clearInterval(interval)
  }, [isComplete])

  // Compute agents state directly during render
  const agents: Record<string, AgentData> = {}
  let globalStart: number | null = null

  events.forEach(ev => {
    const e = ev as Record<string, unknown>
    const eventType = e.event as string
    const agentName = e.agent as string
    const tasks = e.tasks as string[] | undefined
    const timestamp = e.timestamp as string | undefined
    const message = e.message as string | undefined
    const errorMsg = e.error as string | undefined

    if (eventType === "discovery_started") {
      if (!globalStart) globalStart = parseTime(timestamp) || now
      tasks?.forEach((t: string) => {
        if (!agents[t]) {
          agents[t] = { name: t, status: "WAITING", logs: [] }
        }
      })
    }

    if (agentName && !agents[agentName]) {
      agents[agentName] = { name: agentName, status: "WAITING", logs: [] }
    }

    const agent = agentName ? agents[agentName] : null

    if (eventType === "agent_started" && agent) {
      agent.status = "RUNNING"
      agent.startedAt = parseTime(timestamp) || now
      if (!globalStart) globalStart = agent.startedAt
    } else if (eventType === "agent_completed" && agent) {
      agent.status = "COMPLETED"
      if (agent.startedAt) {
        const finishedAt = parseTime(timestamp) || now
        agent.durationMs = finishedAt - agent.startedAt
      }
    } else if (eventType === "agent_failed" && agent) {
      agent.status = "FAILED"
      agent.error = errorMsg || "Execution failed"
      if (agent.startedAt) {
        const finishedAt = parseTime(timestamp) || now
        agent.durationMs = finishedAt - agent.startedAt
      }
    } else if (eventType === "agent_skipped" && agent) {
      agent.status = "SKIPPED"
    } else if (eventType === "agent_progress" && agent) {
      if (message) {
        agent.logs.push(message)
        if (agent.logs.length > 5) agent.logs.shift()
      }
    } else if (eventType === "agent_progress" && !agent && message) {
       const match = message.match(/Agent '([^']+)'/)
       if (match && agents[match[1]]) {
          agents[match[1]].logs.push(message)
          if (agents[match[1]].logs.length > 5) agents[match[1]].logs.shift()
       }
    }
  })

  let activeCount = 0
  let completedCount = 0

  Object.values(agents).forEach(a => {
    if (a.status === "RUNNING") activeCount++
    if (a.status === "COMPLETED" || a.status === "FAILED" || a.status === "SKIPPED") completedCount++
  })

  // Calculate total runtime
  const getGlobalRuntime = () => {
    if (totalDurationMs) return formatDuration(totalDurationMs)
    if (isInitializing) return `${(5 - (initCountdown || 0)).toFixed(2)}s`
    if (!globalStart) return "00.00s"
    if (isComplete) return "" // wait for totalDurationMs
    return formatDuration(now - globalStart)
  }

  return (
    <div className="w-full bg-[#0a0a0a] border border-slate-800 rounded-lg overflow-hidden font-mono text-sm shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-slate-900/50 border-b border-slate-800">
        <div className="flex items-center space-x-3">
          <Terminal className="h-4 w-4 text-emerald-500" />
          <span className="text-slate-200 font-semibold tracking-wide">EADIP DISCOVERY ENGINE</span>
          <span className="text-slate-500 text-xs px-2 py-0.5 rounded-full bg-slate-800/50">
            Target: {warehouseName}
          </span>
        </div>
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 text-slate-400">
            <Clock className="h-4 w-4" />
            <span className="w-16 text-right tabular-nums">{getGlobalRuntime()}</span>
          </div>
          <div className="flex items-center space-x-2">
            {isComplete ? (
              <span className="text-emerald-400 font-semibold flex items-center gap-1.5"><CheckCircle2 className="h-4 w-4" /> COMPLETED</span>
            ) : (
              <span className="text-emerald-500 font-semibold flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> RUNNING</span>
            )}
          </div>
        </div>
      </div>

      {/* Agents Body */}
      <div className="p-4 space-y-4">
        {isInitializing && (
          <div className="text-blue-400 font-medium">
            <span className="text-slate-500">[{new Date().toLocaleTimeString(undefined, { hour12: false })}]</span> Preparing multi-agent discovery... {initCountdown}s
          </div>
        )}
        
        {Object.values(agents).length === 0 && !isComplete && !isInitializing && (
          <div className="text-slate-500 italic">Starting discovery execution...</div>
        )}
        
        {Object.values(agents).map(agent => {
          let duration = "WAITING"
          if (agent.status === "COMPLETED" || agent.status === "FAILED") {
            duration = agent.durationMs ? formatDuration(agent.durationMs) : "???"
          } else if (agent.status === "RUNNING" && agent.startedAt) {
            duration = formatDuration(now - agent.startedAt)
          } else if (agent.status === "SKIPPED") {
            duration = "SKIPPED"
          }

          return (
            <div key={agent.name} className="flex flex-col space-y-1">
              <div className="flex items-center justify-between group">
                <div className="flex items-center space-x-3">
                  {agent.status === "WAITING" && <span className="text-slate-600">○</span>}
                  {agent.status === "RUNNING" && <Loader2 className="h-4 w-4 text-emerald-500 animate-spin" />}
                  {agent.status === "COMPLETED" && <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
                  {agent.status === "FAILED" && <XCircle className="h-4 w-4 text-red-500" />}
                  {agent.status === "SKIPPED" && <span className="text-slate-500">-</span>}
                  
                  <span className={`font-medium ${
                    agent.status === "WAITING" ? "text-slate-500" :
                    agent.status === "FAILED" ? "text-red-400" :
                    agent.status === "SKIPPED" ? "text-slate-500 line-through" :
                    "text-slate-200"
                  }`}>
                    {agent.name.replace("_agent", "").split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')} Agent
                  </span>
                </div>
                <div className={`tabular-nums w-16 text-right ${agent.status === "RUNNING" ? "text-emerald-400" : "text-slate-500"}`}>
                  {duration}
                </div>
              </div>

              {/* Live logs/activity tree */}
              {agent.logs.length > 0 && agent.status === "RUNNING" && (
                <div className="pl-7 space-y-0.5 text-slate-500 text-xs">
                  {agent.logs.map((log, i) => (
                    <div key={i} className="flex items-center space-x-2">
                      <span className="text-slate-700">{i === agent.logs.length - 1 ? "└─" : "├─"}</span>
                      <span className="truncate">{log}</span>
                    </div>
                  ))}
                  {/* Fake a trailing ... for the active step */}
                  <div className="flex items-center space-x-2">
                    <span className="text-slate-700">└─</span>
                    <span className="animate-pulse text-emerald-700">...</span>
                  </div>
                </div>
              )}
              
              {agent.status === "FAILED" && agent.error && (
                <div className="pl-7 text-red-400/80 text-xs mt-1">
                  └─ Error: {agent.error}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Footer / Stats */}
      <div className="px-4 py-2 bg-slate-900/50 border-t border-slate-800 text-xs text-slate-400 flex items-center justify-between">
        <div>
          Parallel execution: <span className="text-slate-200">{isInitializing ? 0 : activeCount}</span> agent{activeCount === 1 ? '' : 's'} active
        </div>
        <div>
          Completed: <span className="text-slate-200">{completedCount}</span> / {Object.keys(agents).length || 5}
        </div>
      </div>
    </div>
  )
}
