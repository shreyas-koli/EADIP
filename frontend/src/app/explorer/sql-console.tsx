"use client"

import * as React from "react"
import { QueryResult, explorerApi } from "@/lib/api/explorer"
import { DatabaseTable } from "@/lib/api/explorer"
import { Button } from "@/components/ui/button"
import { 
  Play, 
  Square, 
  AlertCircle, 
  CheckCircle2, 
  Clock, 
  Rows3, 
  AlertTriangle, 
  Copy, 
  Check, 
  BarChart2
} from "lucide-react"

interface SqlConsoleProps {
  warehouseId: number
  selectedTable: DatabaseTable | null
  initialQuery?: string
  onQueryResult?: (result: QueryResult) => void
  onOpenChart?: () => void
}

const PLACEHOLDER_SQL = `-- Write your SQL query here. Press Ctrl+Enter to execute.
SELECT 1;`

function buildContextSql(table: DatabaseTable): string {
  return `SELECT *\nFROM "${table.schema_name}"."${table.name}"\nLIMIT 50;`
}

export function SqlConsole({ 
  warehouseId, 
  selectedTable, 
  initialQuery, 
  onQueryResult,
  onOpenChart 
}: SqlConsoleProps) {
  const [sql, setSql] = React.useState(initialQuery || "")
  const [result, setResult] = React.useState<QueryResult | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [isRunning, setIsRunning] = React.useState(false)
  const [copied, setCopied] = React.useState(false)
  const abortRef = React.useRef<AbortController | null>(null)
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  // Update sql if initialQuery changes from outside
  React.useEffect(() => {
    if (initialQuery) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSql(initialQuery)
    }
  }, [initialQuery])

  // Context pre-fill for new tables
  const [lastContextKey, setLastContextKey] = React.useState<string | null>(null)
  const contextKey = selectedTable
    ? `${selectedTable.schema_name}.${selectedTable.name}`
    : null

  if (contextKey && contextKey !== lastContextKey) {
    setLastContextKey(contextKey)
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

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setIsRunning(true)
    setResult(null)
    setError(null)

    try {
      const data = await explorerApi.executeQuery(warehouseId, query, controller.signal)
      setResult(data)
      onQueryResult?.(data)
    } catch (err) {
      if ((err as Error).name === "AbortError") return
      const e = err as Error
      setError(e.message || "Query failed.")
    } finally {
      setIsRunning(false)
    }
  }, [sql, isRunning, warehouseId, onQueryResult])

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

  const handleCopySql = () => {
    navigator.clipboard.writeText(sql)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Editor Frame */}
      <div className="flex flex-col rounded-xl border border-slate-800 bg-slate-950 shadow-xl overflow-hidden">
        {/* Editor Toolbar */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-800/80 bg-slate-900/70 backdrop-blur-sm">
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 rounded-full bg-cyan-400" />
            <span className="text-xs font-mono font-semibold text-slate-300">SQL Worksheet</span>
            {selectedTable && (
              <span className="text-[11px] font-mono text-cyan-400/80 bg-cyan-950/40 px-2 py-0.5 rounded border border-cyan-800/30">
                {selectedTable.schema_name}.{selectedTable.name}
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5">
            {selectedTable && (
              <button
                onClick={() => setSql(buildContextSql(selectedTable))}
                className="text-xs text-slate-400 hover:text-cyan-400 transition-colors px-2.5 py-1 rounded-md hover:bg-slate-800/60"
                title="Insert current table template query"
              >
                Insert table SELECT
              </button>
            )}
            <button
              onClick={handleCopySql}
              className="text-xs text-slate-400 hover:text-slate-200 transition-colors px-2 py-1 rounded-md hover:bg-slate-800/60 flex items-center gap-1"
              title="Copy SQL"
            >
              {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
              <span>{copied ? "Copied" : "Copy"}</span>
            </button>
            <button
              onClick={handleClear}
              className="text-xs text-slate-400 hover:text-rose-400 transition-colors px-2 py-1 rounded-md hover:bg-slate-800/60"
            >
              Clear
            </button>
          </div>
        </div>

        {/* Textarea Code Area */}
        <textarea
          ref={textareaRef}
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={PLACEHOLDER_SQL}
          spellCheck={false}
          rows={9}
          className="w-full resize-y bg-slate-950 text-cyan-100 font-mono text-sm px-4 py-3.5 focus:outline-none placeholder:text-slate-600 leading-relaxed selection:bg-blue-600 selection:text-white"
          style={{ minHeight: "180px", maxHeight: "450px" }}
        />

        {/* Action Run Bar */}
        <div className="flex items-center justify-between px-4 py-2.5 border-t border-slate-800/80 bg-slate-900/50">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span>Press <kbd className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">Ctrl+Enter</kbd> to run</span>
          </div>
          
          <div className="flex items-center gap-2">
            {isRunning ? (
              <Button
                onClick={handleCancel}
                size="sm"
                variant="outline"
                className="h-8 border-rose-800 text-rose-400 hover:bg-rose-950/40 gap-1.5 font-medium"
              >
                <Square className="h-3.5 w-3.5 fill-current" />
                Cancel Execution
              </Button>
            ) : (
              <Button
                onClick={handleRun}
                size="sm"
                disabled={!sql.trim()}
                className="h-8 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white gap-1.5 shadow-md shadow-blue-500/20 font-medium"
              >
                <Play className="h-3.5 w-3.5 fill-current" />
                Run Query
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Running Pulse Indicator */}
      {isRunning && (
        <div className="flex items-center gap-2.5 text-sm text-cyan-400 px-2 py-1 rounded-lg bg-cyan-950/20 border border-cyan-800/30">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
          <span className="font-medium">Executing query against warehouse engine…</span>
        </div>
      )}

      {/* Error state */}
      {error && !isRunning && (
        <div className="rounded-xl border border-rose-800/60 bg-rose-950/30 p-4 shadow-lg">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-rose-300">SQL Execution Error</p>
              <p className="text-xs text-rose-200/90 mt-1 font-mono whitespace-pre-wrap">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Results Section */}
      {result && !isRunning && (
        <div className="flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/80 p-4 shadow-xl">
          {/* Stats Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
            <div className="flex flex-wrap items-center gap-4 text-xs">
              <div className="flex items-center gap-1.5 text-emerald-400 font-semibold">
                <CheckCircle2 className="h-4 w-4" />
                <span>Execution Successful</span>
              </div>
              <div className="flex items-center gap-1.5 text-slate-400 font-mono">
                <Clock className="h-3.5 w-3.5 text-slate-500" />
                <span>{result.execution_time_ms.toLocaleString()} ms</span>
              </div>
              <div className="flex items-center gap-1.5 text-slate-400 font-mono">
                <Rows3 className="h-3.5 w-3.5 text-slate-500" />
                <span>{result.returned_rows.toLocaleString()} rows</span>
              </div>
              {result.truncated && (
                <div className="flex items-center gap-1.5 text-amber-400">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  <span>Results truncated at 1,000-row limit</span>
                </div>
              )}
            </div>

            {/* Visualize Shortcut Button */}
            {onOpenChart && result.rows.length > 0 && (
              <Button
                size="sm"
                variant="outline"
                onClick={onOpenChart}
                className="h-7 text-xs border-cyan-800/60 bg-cyan-950/40 text-cyan-300 hover:bg-cyan-900/60 hover:text-white gap-1.5"
              >
                <BarChart2 className="h-3.5 w-3.5" />
                Plot in Visual Canvas
              </Button>
            )}
          </div>

          {/* Result Table Preview */}
          {result.columns.length === 0 ? (
            <p className="text-xs text-slate-500 italic py-3">Query executed successfully, returning no columns.</p>
          ) : result.returned_rows === 0 ? (
            <p className="text-xs text-slate-500 italic py-3">Query returned 0 rows.</p>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-800 max-h-[420px] overflow-y-auto">
              <table className="w-full text-xs text-left whitespace-nowrap">
                <thead className="bg-slate-900/90 border-b border-slate-800 sticky top-0 z-10 backdrop-blur-md">
                  <tr>
                    {result.columns.map((col) => (
                      <th
                        key={col}
                        className="px-3.5 py-2.5 text-[11px] font-semibold text-slate-300 uppercase tracking-wider font-mono"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/40">
                  {result.rows.map((row, rowIdx) => (
                    <tr key={rowIdx} className="hover:bg-slate-900/60 transition-colors">
                      {row.map((cell, cellIdx) => (
                        <td
                          key={cellIdx}
                          className="px-3.5 py-2 text-slate-300 max-w-[320px] truncate font-mono text-[11px]"
                          title={cell === null ? "NULL" : String(cell)}
                        >
                          {cell === null ? (
                            <span className="text-slate-600 italic">NULL</span>
                          ) : typeof cell === "boolean" ? (
                            <span className={cell ? "text-emerald-400 font-semibold" : "text-rose-400 font-semibold"}>
                              {String(cell)}
                            </span>
                          ) : (
                            <span>{String(cell)}</span>
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
