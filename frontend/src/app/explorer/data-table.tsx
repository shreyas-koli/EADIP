"use client"

import * as React from "react"
import { RowDataResponse, explorerApi } from "@/lib/api/explorer"
import { Button } from "@/components/ui/button"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { RefreshCw, AlertCircle, Table2, ChevronLeft, ChevronRight } from "lucide-react"

const PAGE_SIZES = [50, 100] as const
type PageSize = (typeof PAGE_SIZES)[number]

interface DataTableProps {
  warehouseId: number
  schemaName: string
  tableName: string
}

export function DataTable({ warehouseId, schemaName, tableName }: DataTableProps) {
  const [data, setData] = React.useState<RowDataResponse | null>(null)
  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  const [pageSize, setPageSize] = React.useState<PageSize>(50)
  const [offset, setOffset] = React.useState(0)

  const currentPage = Math.floor(offset / pageSize) + 1
  const totalPages = data ? Math.max(1, Math.ceil(data.total_rows / pageSize)) : 1
  const startRow = offset + 1
  const endRow = data ? offset + data.returned_rows : offset

  const fetchRows = React.useCallback(
    async (newOffset: number = offset, newLimit: number = pageSize) => {
      try {
        setIsLoading(true)
        setError(null)
        const result = await explorerApi.getRows(warehouseId, schemaName, tableName, newLimit, newOffset)
        setData(result)
      } catch (err) {
        const e = err as Error
        setError(e.message || "Failed to load rows.")
      } finally {
        setIsLoading(false)
      }
    },
    [warehouseId, schemaName, tableName, offset, pageSize]
  )

  // Fetch on mount and when key props change
  // eslint-disable-next-line react-hooks/set-state-in-effect
  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setOffset(0)
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setData(null)
    fetchRows(0, pageSize)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [warehouseId, schemaName, tableName])

  const handlePageSizeChange = (newSize: PageSize) => {
    setPageSize(newSize)
    setOffset(0)
    fetchRows(0, newSize)
  }

  const handlePrev = () => {
    const newOffset = Math.max(0, offset - pageSize)
    setOffset(newOffset)
    fetchRows(newOffset)
  }

  const handleNext = () => {
    if (!data) return
    const newOffset = offset + pageSize
    setOffset(newOffset)
    fetchRows(newOffset)
  }

  const handleRefresh = () => {
    fetchRows(offset)
  }

  const hasNext = data ? offset + data.returned_rows < data.total_rows : false
  const hasPrev = offset > 0

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingState message="Loading rows..." />
      </div>
    )
  }

  if (error) {
    return (
      <EmptyState
        icon={AlertCircle}
        title="Failed to load rows"
        description={error}
        action={<Button onClick={handleRefresh} variant="outline"><RefreshCw className="mr-2 h-4 w-4" />Retry</Button>}
      />
    )
  }

  if (!data || data.columns.length === 0) {
    return (
      <EmptyState
        icon={Table2}
        title="Table contains no rows"
        description="This table is empty."
        action={<Button onClick={handleRefresh} variant="outline"><RefreshCw className="mr-2 h-4 w-4" />Refresh</Button>}
      />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="text-sm text-slate-400">
          {data.returned_rows === 0 ? (
            "No rows returned"
          ) : (
            <>
              Showing{" "}
              <span className="text-slate-200 font-medium">{startRow.toLocaleString()}–{endRow.toLocaleString()}</span>{" "}
              of{" "}
              <span className="text-slate-200 font-medium">
                {data.is_estimated_total ? "~" : ""}{data.total_rows.toLocaleString()}
              </span>
              {data.is_estimated_total && " (estimated)"}
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Page size:</span>
          {PAGE_SIZES.map((size) => (
            <button
              key={size}
              onClick={() => handlePageSizeChange(size)}
              className={`px-2 py-1 text-xs rounded border transition-colors ${
                pageSize === size
                  ? "bg-blue-600 border-blue-600 text-white"
                  : "border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-300"
              }`}
            >
              {size}
            </button>
          ))}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRefresh}
            className="h-7 w-7 p-0 ml-1"
            title="Refresh"
          >
            <RefreshCw className="h-3.5 w-3.5 text-slate-400" />
          </Button>
        </div>
      </div>

      {/* Scrollable Table */}
      <div className="overflow-x-auto rounded-md border border-slate-800">
        <table className="w-full text-sm text-left whitespace-nowrap">
          <thead className="bg-slate-900 border-b border-slate-800 sticky top-0 z-10">
            <tr>
              {data.columns.map((col) => (
                <th
                  key={col}
                  className="px-4 py-2.5 text-xs font-semibold text-slate-400 uppercase tracking-wide"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {data.rows.map((row, rowIdx) => (
              <tr
                key={rowIdx}
                className="hover:bg-slate-800/40 transition-colors"
              >
                {row.map((cell, cellIdx) => (
                  <td
                    key={cellIdx}
                    className="px-4 py-2 text-slate-300 max-w-[300px] truncate"
                    title={cell === null ? "NULL" : String(cell)}
                  >
                    {cell === null ? (
                      <span className="text-slate-600 italic font-mono text-xs">NULL</span>
                    ) : typeof cell === "boolean" ? (
                      <span className={`font-mono text-xs ${cell ? "text-emerald-400" : "text-rose-400"}`}>
                        {String(cell)}
                      </span>
                    ) : (
                      <span className="font-mono text-xs">{String(cell)}</span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between gap-2 pt-1">
        <Button
          variant="outline"
          size="sm"
          onClick={handlePrev}
          disabled={!hasPrev}
          className="h-8 px-3 border-slate-700 text-slate-300 disabled:opacity-30"
        >
          <ChevronLeft className="h-4 w-4 mr-1" />
          Previous
        </Button>

        <span className="text-xs text-slate-500">
          Page {currentPage.toLocaleString()}{totalPages > 1 ? ` of ~${totalPages.toLocaleString()}` : ""}
        </span>

        <Button
          variant="outline"
          size="sm"
          onClick={handleNext}
          disabled={!hasNext}
          className="h-8 px-3 border-slate-700 text-slate-300 disabled:opacity-30"
        >
          Next
          <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </div>
    </div>
  )
}
