"use client"

import * as React from "react"
import { QueryResult, explorerApi } from "@/lib/api/explorer"
import { DatabaseTable } from "@/lib/api/explorer"
import { Button } from "@/components/ui/button"
import { Play, Square, AlertCircle, CheckCircle2, Clock, Rows3, AlertTriangle } from "lucide-react"

interface SqlConsoleProps {
  warehouseId: number
  selectedTable: DatabaseTable | null
  initialQuery?: string
}

const PLACEHOLDER_SQL = `-- Write a SQL query and press Run (Ctrl+Enter)
SELECT 1;`

function buildContextSql(table: DatabaseTable): string {
  return `SELECT *\nFROM "${table.schema_name}"."${table.name}"\nLIMIT 50;`
}

export function SqlConsole({ warehouseId, selectedTable, initialQuery }: SqlConsoleProps) {
  const [sql, setSql] = React.useState(initialQuery || "")
  const [result, setResult] = React.useState<QueryResult | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [isRunning, setIsRunning] = React.useState(false)
  const abortRef = React.useRef<AbortController | null>(null)
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  // Update sql if initialQuery changes from outside
  React.useEffect(() => {
    if (initialQuery) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSql(initialQuery)
    }
  }, [initialQuery])

  // When a table is selected and editor is empty (or contains only placeholder),
  // offer a starter query — but never overwrite user-written SQL.
  const [lastContextKey, setLastContextKey] = React.useState<string | null>(null)
  const contextKey = selectedTable
    ? `${selectedTable.schema_name}.${selectedTable.name}`
    : null

  if (contextKey && contextKey !== lastContextKey) {
    setLastContextKey(contextKey)
    // Only pre-fill if editor is empty / has placeholder
    setSql((prev) => {
      const trimmed = prev.trim()
      if (!trimmed || trimmed === PLACEHOLDER_SQL.trim()) {
        return buildContextSql(selectedTable!)
      }
      return prev
    })
  }

  const handleRun = React.useCallback(async () => {
    const query = sql.trim()
    if (!query || isRunning) return

    // Cancel any in-flight request
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setIsRunning(true)
    setResult(null)
    setError(null)

    try {
      const data = await explorerApi.executeQuery(warehouseId, query, controller.signal)
      setResult(data)
    } catch (err) {
      if ((err as Error).name === "AbortError") return // user cancelled
      const e = err as Error
      setError(e.message || "Query failed.")
    } finally {
      setIsRunning(false)
    }
  }, [sql, isRunning, warehouseId])

  const handleCancel = () => {
    abortRef.current?.abort()
    setIsRunning(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault()
      handleRun()
    }
  }

  const handleClear = () => {
    setSql("")
    setResult(null)
    setError(null)
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Editor area */}
      <div className="flex flex-col rounded-lg border border-slate-700 bg-slate-950 overflow-hidden">
        {/* Editor toolbar */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-slate-800 bg-slate-900/80">
          <span className="text-xs font-mono text-slate-500">SQL Editor</span>
          <div className="flex items-center gap-1.5">
            {selectedTable && (
              <button
                onClick={() => setSql(buildContextSql(selectedTable))}
                className="text-xs text-slate-500 hover:text-blue-400 transition-colors px-2 py-0.5 rounded hover:bg-slate-800"
                title="Insert current table as starter query"
              >
                Insert table context
              </button>
            )}
            <button
              onClick={handleClear}
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-2 py-0.5 rounded hover:bg-slate-800"
            >
              Clear
            </button>
          </div>
        </div>

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={PLACEHOLDER_SQL}
          spellCheck={false}
          rows={8}
          className="
            w-full resize-y bg-transparent text-slate-200 font-mono text-sm
            px-4 py-3 focus:outline-none placeholder:text-slate-600
            leading-relaxed
          "
          style={{ minHeight: "160px", maxHeight: "400px" }}
        />

        {/* Run bar */}
        <div className="flex items-center justify-between px-3 py-2 border-t border-slate-800 bg-slate-900/50">
          <span className="text-xs text-slate-600">Ctrl+Enter to run</span>
          <div className="flex gap-2">
            {isRunning ? (
              <Button
                onClick={handleCancel}
                size="sm"
                variant="outline"
                className="h-8 border-red-800 text-red-400 hover:bg-red-950 gap-1.5"
              >
                <Square className="h-3.5 w-3.5" />
                Cancel
              </Button>
            ) : (
              <Button
                onClick={handleRun}
                size="sm"
                disabled={!sql.trim()}
                className="h-8 bg-blue-600 hover:bg-blue-700 text-white gap-1.5"
              >
                <Play className="h-3.5 w-3.5" />
                Run Query
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Running indicator */}
      {isRunning && (
        <div className="flex items-center gap-2 text-sm text-blue-400 px-1">
          <span className="inline-block w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
          Running query…
        </div>
      )}

      {/* Error state */}
      {error && !isRunning && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/20 p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-red-400">Query Error</p>
              <p className="text-sm text-red-300/80 mt-1 font-mono whitespace-pre-wrap">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {result && !isRunning && (
        <div className="flex flex-col gap-3">
          {/* Stats bar */}
          <div className="flex flex-wrap items-center gap-4 px-1">
            <div className="flex items-center gap-1.5 text-sm text-emerald-400">
              <CheckCircle2 className="h-4 w-4" />
              <span>Query completed</span>
            </div>
            <div className="flex items-center gap-1.5 text-sm text-slate-400">
              <Clock className="h-3.5 w-3.5" />
              <span>{result.execution_time_ms.toLocaleString()} ms</span>
            </div>
            <div className="flex items-center gap-1.5 text-sm text-slate-400">
              <Rows3 className="h-3.5 w-3.5" />
              <span>
                {result.returned_rows.toLocaleString()} row{result.returned_rows !== 1 ? "s" : ""} returned
              </span>
            </div>
            {result.truncated && (
              <div className="flex items-center gap-1.5 text-sm text-amber-400">
                <AlertTriangle className="h-3.5 w-3.5" />
                <span>Results truncated at the 1,000-row limit.</span>
              </div>
            )}
          </div>

          {/* Result table */}
          {result.columns.length === 0 ? (
            <p className="text-sm text-slate-500 italic px-1">Query returned no columns.</p>
          ) : result.returned_rows === 0 ? (
            <p className="text-sm text-slate-500 italic px-1">Query returned 0 rows.</p>
          ) : (
            <div className="overflow-x-auto rounded-md border border-slate-800 max-h-[500px] overflow-y-auto">
              <table className="w-full text-sm text-left whitespace-nowrap">
                <thead className="bg-slate-900 border-b border-slate-800 sticky top-0 z-10">
                  <tr>
                    {result.columns.map((col) => (
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
                  {result.rows.map((row, rowIdx) => (
                    <tr key={rowIdx} className="hover:bg-slate-800/40 transition-colors">
                      {row.map((cell, cellIdx) => (
                        <td
                          key={cellIdx}
                          className="px-4 py-2 text-slate-300 max-w-[350px] truncate"
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
          )}
        </div>
      )}
    </div>
  )
}
