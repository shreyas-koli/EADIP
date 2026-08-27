"use client"

import { useState, useEffect, useRef } from "react"
import { Terminal, Clock, CheckCircle2, Loader2, Activity, Play, Pause, RotateCcw, XCircle } from "lucide-react"

type AgentState = "WAITING" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED"

interface AgentData {
  name: string
  status: AgentState
  startedAt?: number
  durationMs?: number
  logs: string[]
  error?: string
}

interface ReplayState {
  isReplaying: boolean
  isPlaying: boolean
  currentIndex: number
  speed: number
  visibleEvents: Record<string, unknown>[]
  totalEvents: number
  isFinished: boolean
}

interface ReplayActions {
  startReplay: () => void
  pauseReplay: () => void
  restartReplay: () => void
  reset: () => void
  changeSpeed: (speed: 0.5 | 1 | 2 | 5) => void
}

interface DiscoveryConsoleProps {
  warehouseName: string
  isComplete: boolean
  actualSessionStatus?: string
  actualDurationMs?: number
  events: Record<string, unknown>[]
  replayState?: ReplayState
  replayActions?: ReplayActions
  isInitializing?: boolean
  initCountdown?: number
}

const parseTime = (isoString?: string) => {
  return isoString ? new Date(isoString).getTime() : undefined
}

const formatDuration = (ms: number) => {
  const seconds = (ms / 1000).toFixed(3)
  return `${seconds.padStart(6, '0')}s`
}

const formatLogTime = (isoString?: string) => {
  if (!isoString) return ""
  const d = new Date(isoString)
  if (isNaN(d.getTime())) return ""
  
  const hh = d.getHours().toString().padStart(2, '0')
  const mm = d.getMinutes().toString().padStart(2, '0')
  const ss = d.getSeconds().toString().padStart(2, '0')
  const mmm = d.getMilliseconds().toString().padStart(3, '0')
  return `${hh}:${mm}:${ss}.${mmm}`
}

export function DiscoveryConsole({ 
  warehouseName, 
  isComplete, 
  actualSessionStatus,
  actualDurationMs,
  events, 
  replayState,
  replayActions,
  isInitializing 
}: DiscoveryConsoleProps) {
  const [now, setNow] = useState<number>(() => Date.now())
  const logContainerRef = useRef<HTMLDivElement>(null)
  
  useEffect(() => {
    if (isComplete && !replayState?.isReplaying) return
    const interval = setInterval(() => setNow(Date.now()), 50)
    return () => clearInterval(interval)
  }, [isComplete, replayState?.isReplaying])

  // Auto-scroll logic
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [events.length, replayState?.currentIndex])

  const agents: Record<string, AgentData> = {}
  let globalStart: number | null = null

  const displayEvents = replayState?.isReplaying ? replayState.visibleEvents : events

  displayEvents.forEach(ev => {
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

  // Final Execution State Fix
  if (isComplete && !replayState?.isReplaying) {
    if (actualSessionStatus === "COMPLETED") {
      activeCount = 0
      completedCount = 6 // Hardcoded based on current architecture, or Object.keys(agents).length if dynamic
    }
  }

  // Calculate runtimes
  const getGlobalRuntime = () => {
    if (actualDurationMs && (!replayState?.isReplaying || replayState.isFinished)) return formatDuration(actualDurationMs)
    if (!globalStart) return "00.00s"
    if (isComplete && !replayState?.isReplaying) return "" 
    return formatDuration(now - globalStart)
  }

  const getReplayDuration = () => {
    if (!globalStart) return "0.000s";
    const lastEvent = displayEvents[displayEvents.length - 1];
    const ts = parseTime(lastEvent?.timestamp as string | undefined) || now;
    return formatDuration(ts - globalStart);
  }

  // Status Badge Logic
  const renderStatusBadge = () => {
    if (replayState?.isReplaying) {
      return <span className="text-purple-400 font-semibold flex items-center gap-2"><Play className="h-4 w-4" /> REPLAYING</span>
    }
    if (isComplete && actualSessionStatus === "FAILED") {
      return <span className="text-red-400 font-semibold flex items-center gap-2"><XCircle className="h-4 w-4" /> FAILED</span>
    }
    if (isComplete) {
      return <span className="text-emerald-400 font-semibold flex items-center gap-1.5"><CheckCircle2 className="h-4 w-4" /> COMPLETED</span>
    }
    if (isInitializing) {
      return <span className="text-blue-400 font-semibold flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> INITIALIZING</span>
    }
    return <span className="text-blue-400 font-semibold flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> RUNNING</span>
  }

  let fastestAgent = ""
  let slowestAgent = ""
  let minDuration = Infinity
  let maxDuration = -1

  if (isComplete && !replayState?.isReplaying) {
    Object.values(agents).forEach(a => {
      if (a.durationMs && a.durationMs > 0) {
        if (a.durationMs < minDuration) {
          minDuration = a.durationMs
          fastestAgent = a.name
        }
        if (a.durationMs > maxDuration) {
          maxDuration = a.durationMs
          slowestAgent = a.name
        }
      }
    })
  }

  return (
    <div className="w-full font-mono text-sm space-y-6">
      {/* Execution Monitor Header */}
      <div className="bg-[#0a0a0a] border border-slate-800 rounded-lg overflow-hidden shadow-2xl">
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
              <span className="w-20 text-right tabular-nums text-slate-200 font-medium">{getGlobalRuntime()}</span>
            </div>
            <div className="flex items-center space-x-2">
              {renderStatusBadge()}
            </div>
          </div>
        </div>
        <div className="px-4 py-3 flex items-center justify-between bg-slate-900/20 text-slate-400">
          <div>Parallel: <span className="text-slate-200 font-medium">{activeCount} active</span></div>
          <div>Completed: <span className="text-slate-200 font-medium">{completedCount} / 6</span></div>
        </div>
      </div>

      {/* Execution Log */}
      <div className="bg-[#0a0a0a] border border-slate-800 rounded-lg overflow-hidden shadow-xl flex flex-col">
        <div className="px-4 py-2 bg-slate-900/50 border-b border-slate-800 text-slate-300 font-semibold flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-slate-500" /> {replayState?.isReplaying ? "Replay Execution Log" : "Live Execution Log"}
          </div>
          {replayState?.isReplaying && (
            <div className="text-xs font-normal text-slate-400">
              Playback Time: <span className="text-slate-200">{getReplayDuration()}</span>
            </div>
          )}
        </div>
        <div 
          ref={logContainerRef}
          className="p-4 overflow-y-auto max-h-[300px] flex-grow space-y-1 text-xs"
        >
          {displayEvents.length === 0 && <span className="text-slate-600 italic">Awaiting pipeline initialization...</span>}
          {displayEvents.map((e, idx) => {
             const ev = e as Record<string, unknown>
             const ts = formatLogTime(ev.timestamp as string | undefined)
             const agent = ev.agent as string
             const eventName = ev.event as string
             
             let msg = ""
             let color = "text-slate-400"
             
             if (eventName === "discovery_started") { msg = "Discovery Engine initialized"; color = "text-blue-400" }
             else if (eventName === "agent_started") { msg = `${agent} started`; color = "text-emerald-400" }
             else if (eventName === "agent_progress") { msg = `${agent} → ${ev.message}`; color = "text-slate-300" }
             else if (eventName === "agent_completed") { msg = `${agent} completed`; color = "text-emerald-500 font-medium" }
             else if (eventName === "agent_failed") { msg = `${agent} failed: ${ev.error}`; color = "text-red-400" }
             else if (eventName === "discovery_completed") { msg = "Discovery Engine completed successfully"; color = "text-emerald-400 font-bold" }
             
             if (!msg) return null;
             
             const isActiveRow = replayState?.isReplaying && idx === displayEvents.length - 1;
             
             return (
               <div key={idx} className={`flex space-x-4 ${color} ${isActiveRow ? 'bg-slate-800/50 -mx-2 px-2 py-0.5 rounded' : ''}`}>
                 <span className="text-slate-500 w-24 flex-shrink-0 tabular-nums">{ts}</span>
                 <span className="truncate">{msg}</span>
               </div>
             )
          })}
        </div>
        
        {/* Replay Controls */}
        {isComplete && replayState && replayActions && (
          <div className="px-4 py-3 bg-slate-900/80 border-t border-slate-800 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <button 
                onClick={() => replayState.isPlaying ? replayActions.pauseReplay() : replayActions.startReplay()}
                className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-md transition-colors"
                title={replayState.isPlaying ? "Pause Replay" : "Play Replay"}
              >
                {replayState.isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              </button>
              <button 
                onClick={() => replayActions.restartReplay()}
                className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-md transition-colors"
                title="Restart Replay"
              >
                <RotateCcw className="h-4 w-4" />
              </button>
              
              <div className="ml-4 flex items-center space-x-2 text-xs">
                <span className="text-slate-400">Speed:</span>
                <select 
                  className="bg-slate-800 border-none text-slate-200 rounded px-2 py-1 outline-none"
                  value={replayState.speed}
                  onChange={(e) => replayActions.changeSpeed(Number(e.target.value) as 0.5 | 1 | 2 | 5)}
                >
                  <option value={0.5}>0.5x</option>
                  <option value={1}>1x</option>
                  <option value={2}>2x</option>
                  <option value={5}>5x</option>
                </select>
              </div>
            </div>
            
            <div className="flex items-center space-x-3 text-xs">
              <span className="text-slate-400">
                Event {replayState.isReplaying ? replayState.currentIndex + 1 : events.length} / {events.length}
              </span>
              <div className="w-32 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-purple-500 transition-all duration-200 ease-linear" 
                  style={{ width: `${(replayState.isReplaying ? (replayState.currentIndex + 1) / events.length : 1) * 100}%` }}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Performance Summary (Only shown on complete, hides on replay to prevent confusion) */}
      {isComplete && !replayState?.isReplaying && (
        <div className="bg-slate-900/50 border border-emerald-500/20 rounded-lg p-4 shadow-xl">
           <h4 className="text-emerald-400 font-semibold mb-4 flex items-center gap-2">
             {actualSessionStatus === "FAILED" ? (
               <><XCircle className="h-4 w-4 text-red-400" /> <span className="text-red-400">DISCOVERY FAILED</span></>
             ) : (
               <><CheckCircle2 className="h-4 w-4" /> DISCOVERY COMPLETED</>
             )}
           </h4>
           <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-slate-400">
             <div>
               <div className="text-xs mb-1 uppercase tracking-wider text-slate-500">Actual Execution</div>
               <div className="text-slate-200 font-medium text-base">{actualDurationMs ? formatDuration(actualDurationMs) : getGlobalRuntime()}</div>
             </div>
             <div>
               <div className="text-xs mb-1 uppercase tracking-wider text-slate-500">Agents</div>
               <div className="text-slate-200 font-medium text-base">{completedCount} / 6 completed</div>
             </div>
             <div>
               <div className="text-xs mb-1 uppercase tracking-wider text-slate-500">Fastest Agent</div>
               <div className="text-slate-200 font-medium text-base">{fastestAgent.replace("_agent", "") || "-"} <span className="text-slate-500 text-xs ml-1">{minDuration !== Infinity ? `${(minDuration/1000).toFixed(3)}s` : ''}</span></div>
             </div>
             <div>
               <div className="text-xs mb-1 uppercase tracking-wider text-slate-500">Slowest Agent</div>
               <div className="text-slate-200 font-medium text-base">{slowestAgent.replace("_agent", "") || "-"} <span className="text-slate-500 text-xs ml-1">{maxDuration !== -1 ? `${(maxDuration/1000).toFixed(3)}s` : ''}</span></div>
             </div>
           </div>
        </div>
      )}
    </div>
  )
}
