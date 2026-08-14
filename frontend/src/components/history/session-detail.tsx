"use client"

import * as React from "react"
import { discoveryApi, DiscoverySession } from "@/lib/api/discovery"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { AlertCircle, X, ChevronRight } from "lucide-react"

import { DiscoveryPipeline } from "@/components/discovery/discovery-pipeline"
import { DiscoveryResult } from "@/components/discovery/discovery-result"

interface SessionDetailProps {
  warehouseId: number
  warehouseName: string
  sessionId: string
  onClose: () => void
}

export function SessionDetail({ warehouseId, warehouseName, sessionId, onClose }: SessionDetailProps) {
  const [session, setSession] = React.useState<DiscoverySession | null>(null)
  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let mounted = true
    const fetchSession = async () => {
      try {
        setIsLoading(true)
        const data = await discoveryApi.getSession(warehouseId, sessionId)
        if (mounted) {
          setSession(data)
          setError(null)
        }
      } catch {
        if (mounted) {
          setError("Failed to load session details. The session may not exist or you don't have access.")
        }
      } finally {
        if (mounted) setIsLoading(false)
      }
    }
    fetchSession()
    return () => { mounted = false }
  }, [warehouseId, sessionId])

  if (isLoading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 min-h-[400px] flex items-center justify-center relative">
        <button onClick={onClose} className="absolute top-4 right-4 p-2 text-slate-500 hover:text-white rounded-full hover:bg-slate-800">
          <X className="h-5 w-5" />
        </button>
        <LoadingState message="Loading session details..." />
      </div>
    )
  }

  if (error || !session) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 relative">
        <button onClick={onClose} className="absolute top-4 right-4 p-2 text-slate-500 hover:text-white rounded-full hover:bg-slate-800">
          <X className="h-5 w-5" />
        </button>
        <EmptyState
          icon={AlertCircle}
          title="Session Not Found"
          description={error || "An unknown error occurred."}
        />
      </div>
    )
  }

  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="bg-slate-950 px-6 py-4 flex items-center justify-between border-b border-slate-800">
        <div className="flex items-center space-x-2 text-sm">
          <span className="text-slate-400">History</span>
          <ChevronRight className="h-4 w-4 text-slate-600" />
          <span className="text-blue-400 font-mono">{session.session_id.substring(0, 8)}...</span>
        </div>
        <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-white rounded-md hover:bg-slate-800 transition-colors">
          <X className="h-5 w-5" />
        </button>
      </div>
      
      <div className="p-6 space-y-8">
        {/* Pipeline Visual */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 overflow-hidden">
          <div className="text-center mb-8">
            <h3 className="text-lg font-semibold text-slate-200">Execution Pipeline</h3>
            <p className="text-sm text-slate-400 font-mono mt-1">{session.session_id}</p>
          </div>
          <div className="overflow-x-auto pb-4">
            <div className="min-w-[600px]">
              <DiscoveryPipeline 
                executions={session.agent_executions} 
                isRunning={session.status === "RUNNING"} 
              />
            </div>
          </div>
        </div>

        {/* Results Visual */}
        <DiscoveryResult 
          session={session} 
          warehouseName={warehouseName}
        />
      </div>
    </div>
  )
}
