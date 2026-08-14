"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { ChevronLeft, ChevronRight } from "lucide-react"

interface HistoryPaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (newPage: number) => void
  disabled?: boolean
}

export function HistoryPagination({ page, pageSize, total, onPageChange, disabled }: HistoryPaginationProps) {
  const totalPages = Math.ceil(total / pageSize)
  
  if (total === 0) return null

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800 bg-slate-900/50 rounded-b-xl">
      <div className="text-sm text-slate-400">
        Showing <span className="font-medium text-slate-200">{(page - 1) * pageSize + 1}</span> to{" "}
        <span className="font-medium text-slate-200">{Math.min(page * pageSize, total)}</span> of{" "}
        <span className="font-medium text-slate-200">{total}</span> results
      </div>
      
      <div className="flex space-x-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1 || disabled}
          className="border-slate-700 bg-slate-900 text-slate-300 hover:bg-slate-800"
        >
          <ChevronLeft className="h-4 w-4 mr-1" /> Prev
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages || disabled}
          className="border-slate-700 bg-slate-900 text-slate-300 hover:bg-slate-800"
        >
          Next <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </div>
    </div>
  )
}
