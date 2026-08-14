"use client"

import * as React from "react"
import { DiscoveryHistoryResponse } from "@/lib/api/discovery"
import { AgentStatus } from "@/components/agent/agent-components"
import { Clock, Calendar, ArrowRight } from "lucide-react"

interface HistoryListProps {
  items: DiscoveryHistoryResponse[]
  selectedSessionId: string | null
  onSelect: (session: DiscoveryHistoryResponse) => void
}

export function HistoryList({ items, selectedSessionId, onSelect }: HistoryListProps) {
  if (items.length === 0) {
    return (
      <div className="py-12 text-center text-slate-500 border border-slate-800 rounded-xl bg-slate-900/20">
        No discovery runs found matching these criteria.
      </div>
    )
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    })
  }

  return (
    <div className="rounded-xl border border-slate-800 overflow-hidden bg-slate-900">
      <div className="grid grid-cols-12 gap-4 bg-slate-950 px-6 py-3 text-xs font-medium text-slate-400 uppercase tracking-wider border-b border-slate-800">
        <div className="col-span-5">Session & Time</div>
        <div className="col-span-3">Status</div>
        <div className="col-span-2 text-right">Duration</div>
        <div className="col-span-2 text-right">Action</div>
      </div>
      
      <div className="divide-y divide-slate-800/50">
        {items.map((item) => {
          const isSelected = item.session_id === selectedSessionId
          return (
            <button
              key={item.session_id}
              onClick={() => onSelect(item)}
              className={`w-full text-left grid grid-cols-12 gap-4 px-6 py-4 items-center transition-colors
                ${isSelected ? "bg-blue-900/20" : "hover:bg-slate-800/50"}
              `}
            >
              <div className="col-span-5 flex flex-col">
                <span className={`font-mono text-xs ${isSelected ? "text-blue-300" : "text-slate-300"}`}>
                  {item.session_id.substring(0, 18)}...
                </span>
                <span className="flex items-center text-xs text-slate-500 mt-1">
                  <Calendar className="h-3 w-3 mr-1" />
                  {formatDate(item.started_at)}
                </span>
              </div>
              
              <div className="col-span-3 flex items-center">
                <AgentStatus status={item.status} />
              </div>
              
              <div className="col-span-2 text-right text-xs text-slate-400 font-medium">
                {item.total_duration_ms ? (
                  <span className="flex items-center justify-end">
                    <Clock className="h-3 w-3 mr-1" />
                    {(item.total_duration_ms / 1000).toFixed(1)}s
                  </span>
                ) : (
                  "-"
                )}
              </div>
              
              <div className="col-span-2 flex justify-end">
                <div className={`p-1.5 rounded-full ${isSelected ? "bg-blue-600 text-white" : "text-slate-500 bg-slate-800"}`}>
                  <ArrowRight className="h-4 w-4" />
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
