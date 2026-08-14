"use client"

import * as React from "react"
import { Check, ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"

interface HistoryFiltersProps {
  statusFilter: string
  onStatusChange: (status: string) => void
}

export function HistoryFilters({ statusFilter, onStatusChange }: HistoryFiltersProps) {
  const [isOpen, setIsOpen] = React.useState(false)
  
  const options = [
    { value: "ALL", label: "All Statuses" },
    { value: "COMPLETED", label: "Completed" },
    { value: "FAILED", label: "Failed" }
  ]

  const activeLabel = options.find(o => o.value === statusFilter)?.label || "All Statuses"

  return (
    <div className="relative">
      <Button 
        variant="outline" 
        className="w-[180px] justify-between border-slate-700 bg-slate-900 text-slate-200"
        onClick={() => setIsOpen(!isOpen)}
      >
        {activeLabel}
        <ChevronDown className="h-4 w-4 opacity-50" />
      </Button>

      {isOpen && (
        <div className="absolute z-10 top-full mt-2 w-[180px] rounded-md border border-slate-800 bg-slate-900 shadow-xl overflow-hidden">
          {options.map((opt) => (
            <button
              key={opt.value}
              className="w-full text-left px-4 py-2 text-sm text-slate-300 hover:bg-slate-800 hover:text-white flex items-center justify-between"
              onClick={() => {
                onStatusChange(opt.value)
                setIsOpen(false)
              }}
            >
              {opt.label}
              {statusFilter === opt.value && <Check className="h-4 w-4 text-blue-500" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
