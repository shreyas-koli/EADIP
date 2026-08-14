"use client"

import * as React from "react"
import { Warehouse } from "@/lib/api/warehouses"
import { Database, Server } from "lucide-react"

interface WarehouseSelectorProps {
  warehouses: Warehouse[]
  selectedId: number | null
  onSelect: (id: number) => void
  disabled?: boolean
}

export function WarehouseSelector({ warehouses, selectedId, onSelect, disabled }: WarehouseSelectorProps) {
  if (warehouses.length === 0) {
    return (
      <div className="p-4 rounded-md bg-slate-900 border border-slate-800 text-slate-400 text-sm text-center">
        No active warehouses available. Please add an active warehouse first.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <label className="text-sm font-medium text-slate-300">
        Target Warehouse
      </label>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {warehouses.map(w => (
          <button
            key={w.id}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(w.id)}
            className={`
              text-left flex flex-col p-4 rounded-xl border transition-all
              ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
              ${selectedId === w.id 
                ? "bg-blue-900/20 border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.15)] ring-1 ring-blue-500" 
                : "bg-slate-900 border-slate-800 hover:border-slate-700 hover:bg-slate-800/50"}
            `}
          >
            <div className="flex items-center space-x-3 mb-2">
              <div className={`p-2 rounded-lg ${selectedId === w.id ? "bg-blue-500/20" : "bg-slate-800"}`}>
                <Database className={`h-4 w-4 ${selectedId === w.id ? "text-blue-400" : "text-slate-400"}`} />
              </div>
              <span className={`font-semibold ${selectedId === w.id ? "text-blue-100" : "text-slate-200"}`}>
                {w.name}
              </span>
            </div>
            <div className="flex items-center text-xs text-slate-500 space-x-2 pl-11">
              <span className="uppercase font-medium text-slate-400">{w.db_type}</span>
              <span>•</span>
              <span className="flex items-center truncate">
                <Server className="h-3 w-3 mr-1" />
                {w.host}:{w.port}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
