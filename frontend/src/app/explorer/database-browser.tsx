"use client"

import * as React from "react"
import { 
  DatabaseSchema, 
  DatabaseTable, 
  DatabaseColumn,
  ChatMessage,
  QueryResult,
  explorerApi 
} from "@/lib/api/explorer"
import { Card } from "@/components/ui/card"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { Button } from "@/components/ui/button"
import { 
  ChevronRight, 
  ChevronDown, 
  Database, 
  Table2, 
  RefreshCw,
  AlertCircle,
  Bot,
  Search,
  Code2,
  Rows3,
  BarChart2,
  Folder,
  Layers,
  Clock
} from "lucide-react"
import { DataTable } from "./data-table"
import { SqlConsole } from "./sql-console"
import { AssistantChat } from "./assistant-chat"
import { VisualCanvas } from "@/components/ui/visual-canvas"

interface DatabaseBrowserProps {
  warehouseId: number
}

type ExplorerTab = "objects" | "query" | "results" | "chart" | "assistant"

export function DatabaseBrowser({ warehouseId }: DatabaseBrowserProps) {
  const [schemas, setSchemas] = React.useState<DatabaseSchema[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  // Search filter for objects
  const [searchFilter, setSearchFilter] = React.useState("")

  // Lazy loading state maps
  const [tablesBySchema, setTablesBySchema] = React.useState<Record<string, DatabaseTable[]>>({})
  const [columnsByTable, setColumnsByTable] = React.useState<Record<string, DatabaseColumn[]>>({})
  
  const [loadingSchemas, setLoadingSchemas] = React.useState<Record<string, boolean>>({})
  const [loadingTables, setLoadingTables] = React.useState<Record<string, boolean>>({})

  // UI state
  const [expandedSchemas, setExpandedSchemas] = React.useState<Set<string>>(new Set())
  const [expandedTables, setExpandedTables] = React.useState<Set<string>>(new Set())
  const [selectedTable, setSelectedTable] = React.useState<DatabaseTable | null>(null)
  const [activeTab, setActiveTab] = React.useState<ExplorerTab>("objects")
  
  // Data for Chart & Results
  const [latestQueryResult, setLatestQueryResult] = React.useState<QueryResult | null>(null)
  const [tableSampleData, setTableSampleData] = React.useState<{ columns: string[]; rows: (string | number | boolean | null)[][] } | null>(null)
  const [isLoadingSample, setIsLoadingSample] = React.useState(false)

  // AI Assistant state
  const [assistantQuery, setAssistantQuery] = React.useState<string | undefined>(undefined)
  const [conversations, setConversations] = React.useState<Record<string, ChatMessage[]>>({})

  const currentContextKey = selectedTable
    ? `${warehouseId}:${selectedTable.schema_name}.${selectedTable.name}`
    : `${warehouseId}:_global_`

  const handleMessagesChange = React.useCallback((key: string, newMessages: ChatMessage[]) => {
    setConversations((prev) => ({
      ...prev,
      [key]: newMessages,
    }))
  }, [])

  const handleSendToSqlConsole = React.useCallback((query: string) => {
    setAssistantQuery(query)
    setActiveTab("query")
  }, [])

  const fetchSchemas = React.useCallback(async (showLoading = true) => {
    try {
      if (showLoading) setIsLoading(true)
      const data = await explorerApi.getSchemas(warehouseId)
      setSchemas(data)
      setError(null)
      // Automatically expand the first schema (e.g. public)
      if (data.length > 0) {
        const firstSchema = data[0].name
        setExpandedSchemas(new Set([firstSchema]))
        // Preload tables for first schema
        setLoadingSchemas((prev) => ({ ...prev, [firstSchema]: true }))
        explorerApi.getTables(warehouseId, firstSchema).then((tbls) => {
          setTablesBySchema((prev) => ({ ...prev, [firstSchema]: tbls }))
          if (tbls.length > 0 && !selectedTable) {
            setSelectedTable(tbls[0])
          }
        }).finally(() => {
          setLoadingSchemas((prev) => ({ ...prev, [firstSchema]: false }))
        })
      }
    } catch (err) {
      const e = err as Error
      setError(e.message || "Failed to load database schemas.")
    } finally {
      if (showLoading) setIsLoading(false)
    }
  }, [warehouseId]) // eslint-disable-line react-hooks/exhaustive-deps

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchSchemas()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleRefresh = async () => {
    await fetchSchemas(true)
    setTablesBySchema({})
    setColumnsByTable({})
    setExpandedSchemas(new Set())
    setExpandedTables(new Set())
    setSelectedTable(null)
    setTableSampleData(null)
    setLatestQueryResult(null)
  }

  // Load sample table data when table is selected so Chart has data immediately
  React.useEffect(() => {
    if (!selectedTable) return
    let active = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsLoadingSample(true)
    explorerApi.getRows(warehouseId, selectedTable.schema_name, selectedTable.name, 50, 0)
      .then((res) => {
        if (active) {
          setTableSampleData({
            columns: res.columns,
            rows: res.rows,
          })
        }
      })
      .catch((err) => {
        console.error("Failed to load sample rows for charting", err)
      })
      .finally(() => {
        if (active) setIsLoadingSample(false)
      })

    return () => { active = false }
  }, [warehouseId, selectedTable])

  const toggleSchema = async (schemaName: string) => {
    const newExpanded = new Set(expandedSchemas)
    if (newExpanded.has(schemaName)) {
      newExpanded.delete(schemaName)
      setExpandedSchemas(newExpanded)
    } else {
      newExpanded.add(schemaName)
      setExpandedSchemas(newExpanded)
      
      if (!tablesBySchema[schemaName]) {
        try {
          setLoadingSchemas((prev) => ({ ...prev, [schemaName]: true }))
          const tables = await explorerApi.getTables(warehouseId, schemaName)
          setTablesBySchema((prev) => ({ ...prev, [schemaName]: tables }))
        } catch (err) {
          console.error("Failed to load tables", err)
        } finally {
          setLoadingSchemas((prev) => ({ ...prev, [schemaName]: false }))
        }
      }
    }
  }

  const toggleTable = async (table: DatabaseTable) => {
    const tableKey = `${table.schema_name}.${table.name}`
    const newExpanded = new Set(expandedTables)
    
    setSelectedTable(table)
    
    if (newExpanded.has(tableKey)) {
      newExpanded.delete(tableKey)
      setExpandedTables(newExpanded)
    } else {
      newExpanded.add(tableKey)
      setExpandedTables(newExpanded)
      
      if (!columnsByTable[tableKey]) {
        try {
          setLoadingTables((prev) => ({ ...prev, [tableKey]: true }))
          const columns = await explorerApi.getColumns(warehouseId, table.schema_name, table.name)
          setColumnsByTable((prev) => ({ ...prev, [tableKey]: columns }))
        } catch (err) {
          console.error("Failed to load columns", err)
        } finally {
          setLoadingTables((prev) => ({ ...prev, [tableKey]: false }))
        }
      }
    }
  }

  // Type Icon Helper (Oracle Analytics & Snowflake inspired)
  const getColumnTypeIcon = (dataType: string) => {
    const dt = dataType.toLowerCase()
    if (dt.includes("int") || dt.includes("num") || dt.includes("float") || dt.includes("double") || dt.includes("decimal")) {
      return (
        <span className="flex h-4 w-4 items-center justify-center rounded bg-amber-500/10 text-amber-400 font-mono text-[10px] font-bold" title={dataType}>
          #
        </span>
      )
    }
    if (dt.includes("time") || dt.includes("date") || dt.includes("year")) {
      return (
        <span className="flex h-4 w-4 items-center justify-center rounded bg-purple-500/10 text-purple-400 font-mono text-[10px]" title={dataType}>
          <Clock className="h-2.5 w-2.5" />
        </span>
      )
    }
    if (dt.includes("bool")) {
      return (
        <span className="flex h-4 w-4 items-center justify-center rounded bg-emerald-500/10 text-emerald-400 font-mono text-[10px] font-bold" title={dataType}>
          ✓
        </span>
      )
    }
    return (
      <span className="flex h-4 w-4 items-center justify-center rounded bg-cyan-500/10 text-cyan-400 font-sans text-[10px] font-bold" title={dataType}>
        Aa
      </span>
    )
  }

  // Determine active dataset for Visual Canvas & Results
  const activeDataset = React.useMemo(() => {
    if (latestQueryResult && latestQueryResult.columns.length > 0 && latestQueryResult.rows.length > 0) {
      return {
        columns: latestQueryResult.columns,
        rows: latestQueryResult.rows,
        title: "Query Results Visual Analytics",
        subtitle: `Aggregating ${latestQueryResult.returned_rows} rows from active SQL query execution`,
      }
    }
    if (tableSampleData && tableSampleData.columns.length > 0) {
      return {
        columns: tableSampleData.columns,
        rows: tableSampleData.rows,
        title: `${selectedTable ? `${selectedTable.schema_name}.${selectedTable.name}` : "Table"} Visual Analytics`,
        subtitle: `Aggregating ${tableSampleData.rows.length} rows preview`,
      }
    }
    return null
  }, [latestQueryResult, tableSampleData, selectedTable])

  if (isLoading) {
    return (
      <Card className="border-slate-800 bg-slate-900/40 shadow-xl backdrop-blur-xl">
        <div className="flex h-72 items-center justify-center">
          <LoadingState message="Discovering schemas, tables, and column metadata..." />
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="border-slate-800 bg-slate-900/40 shadow-xl">
        <EmptyState
          icon={AlertCircle}
          title="Failed to Load Warehouse Structure"
          description={error}
          action={<Button onClick={handleRefresh} variant="outline"><RefreshCw className="mr-2 h-4 w-4" /> Retry</Button>}
        />
      </Card>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[750px]">
      {/* ============================================================ */}
      {/* LEFT PANE: Database Objects Explorer (BigQuery & Snowflake) */}
      {/* ============================================================ */}
      <div className="lg:col-span-4 flex flex-col rounded-2xl border border-slate-800 bg-slate-950/90 shadow-xl overflow-hidden max-h-[850px]">
        {/* Explorer Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-900/70">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-cyan-400" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Objects Explorer
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-400">
              {schemas.length} schemas
            </span>
          </div>

          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 text-slate-400 hover:text-white"
            onClick={handleRefresh}
            title="Refresh Object Tree"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </div>

        {/* Search Filter Bar */}
        <div className="px-3 py-2 border-b border-slate-800/80 bg-slate-950">
          <div className="flex items-center rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1.5 text-xs text-slate-300">
            <Search className="h-3.5 w-3.5 text-slate-500 mr-2 shrink-0" />
            <input
              type="text"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Search tables & views..."
              className="w-full bg-transparent text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none"
            />
          </div>
        </div>

        {/* Object Tree */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {schemas.map((schema) => {
            const isSchemaExpanded = expandedSchemas.has(schema.name)
            const tables = tablesBySchema[schema.name] || []
            const filteredTables = searchFilter.trim()
              ? tables.filter((t) => t.name.toLowerCase().includes(searchFilter.toLowerCase()))
              : tables

            return (
              <div key={schema.name} className="space-y-0.5">
                {/* Schema Item */}
                <button
                  onClick={() => toggleSchema(schema.name)}
                  className="flex w-full items-center justify-between py-1.5 px-2 text-xs font-semibold text-slate-300 hover:bg-slate-900/80 rounded-lg transition-colors group"
                >
                  <div className="flex items-center gap-1.5 min-w-0">
                    {isSchemaExpanded ? (
                      <ChevronDown className="h-3.5 w-3.5 text-slate-500 shrink-0" />
                    ) : (
                      <ChevronRight className="h-3.5 w-3.5 text-slate-500 shrink-0" />
                    )}
                    <Folder className="h-3.5 w-3.5 text-blue-400 shrink-0" />
                    <span className="truncate group-hover:text-cyan-300 transition-colors font-mono">
                      {schema.name}
                    </span>
                  </div>
                  {tables.length > 0 && (
                    <span className="text-[10px] text-slate-500 font-mono">
                      {tables.length}
                    </span>
                  )}
                </button>

                {/* Tables List */}
                {isSchemaExpanded && (
                  <div className="ml-4 border-l border-slate-800/80 pl-2 space-y-0.5 py-0.5">
                    {loadingSchemas[schema.name] ? (
                      <div className="text-[11px] text-slate-500 py-1 pl-3 font-mono">Loading tables…</div>
                    ) : filteredTables.length === 0 ? (
                      <div className="text-[11px] text-slate-500 py-1 pl-3 italic">
                        {tables.length === 0 ? "No tables found" : "No matching tables"}
                      </div>
                    ) : (
                      filteredTables.map((table) => {
                        const tableKey = `${schema.name}.${table.name}`
                        const isTableExpanded = expandedTables.has(tableKey)
                        const isSelected = selectedTable?.schema_name === schema.name && selectedTable?.name === table.name
                        const columns = columnsByTable[tableKey] || []

                        return (
                          <div key={tableKey} className="space-y-0.5">
                            {/* Table Node */}
                            <button
                              onClick={() => toggleTable(table)}
                              className={`flex w-full items-center justify-between py-1 px-2 text-xs rounded-lg transition-all text-left group ${
                                isSelected
                                  ? "bg-blue-600/20 text-white border border-blue-500/30 font-medium"
                                  : "text-slate-400 hover:bg-slate-900 hover:text-slate-200 border border-transparent"
                              }`}
                            >
                              <div className="flex items-center gap-1.5 min-w-0">
                                {isTableExpanded ? (
                                  <ChevronDown className="h-3 w-3 text-slate-500 shrink-0" />
                                ) : (
                                  <ChevronRight className="h-3 w-3 text-slate-500 shrink-0" />
                                )}
                                <Table2 className={`h-3.5 w-3.5 shrink-0 ${isSelected ? "text-cyan-400" : "text-slate-500"}`} />
                                <span className="truncate">{table.name}</span>
                              </div>
                              <span className="text-[10px] text-slate-500 font-mono shrink-0 pl-1">
                                ~{table.estimated_row_count.toLocaleString()}
                              </span>
                            </button>

                            {/* Columns Subtree */}
                            {isTableExpanded && (
                              <div className="ml-4 border-l border-slate-800/80 pl-2 space-y-0.5 py-1">
                                {loadingTables[tableKey] ? (
                                  <div className="text-[10px] text-slate-500 py-0.5 pl-2 font-mono">Loading columns…</div>
                                ) : columns.length === 0 ? (
                                  <div className="text-[10px] text-slate-500 py-0.5 pl-2 italic">No columns</div>
                                ) : (
                                  columns.map((column) => (
                                    <div
                                      key={column.name}
                                      className="flex items-center justify-between py-0.5 px-2 text-[11px] text-slate-400 hover:text-slate-200 hover:bg-slate-900/50 rounded transition-colors group"
                                    >
                                      <div className="flex items-center gap-2 min-w-0">
                                        {getColumnTypeIcon(column.data_type)}
                                        <span className="truncate font-mono">{column.name}</span>
                                      </div>
                                      <div className="flex items-center gap-1 shrink-0">
                                        {column.is_primary_key && (
                                          <span className="px-1 py-0.2 rounded text-[9px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">
                                            PK
                                          </span>
                                        )}
                                        {column.foreign_key && (
                                          <span
                                            className="px-1 py-0.2 rounded text-[9px] font-bold bg-blue-500/20 text-cyan-400 border border-blue-500/30"
                                            title={`References ${column.foreign_key.referred_schema}.${column.foreign_key.referred_table}`}
                                          >
                                            FK
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  ))
                                )}
                              </div>
                            )}
                          </div>
                        )
                      })
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* ============================================================ */}
      {/* RIGHT PANE: Multi-Tab Workspace (Snowflake + Oracle) */}
      {/* ============================================================ */}
      <div className="lg:col-span-8 flex flex-col">
        {selectedTable ? (
          <div className="flex flex-col rounded-2xl border border-slate-800 bg-slate-950 shadow-2xl overflow-hidden min-h-[750px]">
            {/* Table Meta Header Bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-4 border-b border-slate-800 bg-slate-900/60 backdrop-blur-md">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-gradient-to-tr from-blue-600/30 to-cyan-500/20 border border-cyan-500/30 text-cyan-400 shadow-md">
                  <Table2 className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-slate-400">{selectedTable.schema_name}.</span>
                    <h3 className="text-lg font-bold text-white tracking-tight">{selectedTable.name}</h3>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-slate-400 mt-0.5">
                    <span>Rows: <strong className="text-slate-200 font-mono">~{selectedTable.estimated_row_count.toLocaleString()}</strong></span>
                    <span>•</span>
                    {columnsByTable[`${selectedTable.schema_name}.${selectedTable.name}`] && (
                      <span>Columns: <strong className="text-slate-200 font-mono">{columnsByTable[`${selectedTable.schema_name}.${selectedTable.name}`].length}</strong></span>
                    )}
                  </div>
                </div>
              </div>

              {/* Quick Query CTA */}
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setAssistantQuery(`SELECT *\nFROM "${selectedTable.schema_name}"."${selectedTable.name}"\nLIMIT 50;`)
                  setActiveTab("query")
                }}
                className="h-8 text-xs border-slate-700 bg-slate-900 hover:bg-slate-800 text-slate-200 gap-1.5"
              >
                <Code2 className="h-3.5 w-3.5 text-cyan-400" />
                New Worksheet
              </Button>
            </div>

            {/* Snowflake Style Workspace Tab Bar */}
            <div className="flex items-center justify-between px-6 border-b border-slate-800 bg-slate-950/80">
              <div className="flex items-center gap-2 py-2 overflow-x-auto">
                <button
                  onClick={() => setActiveTab("objects")}
                  className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all ${
                    activeTab === "objects"
                      ? "bg-blue-600 text-white shadow-sm shadow-blue-500/30"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
                  }`}
                >
                  <Layers className="h-3.5 w-3.5" />
                  Objects
                </button>

                <button
                  onClick={() => setActiveTab("query")}
                  className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all ${
                    activeTab === "query"
                      ? "bg-blue-600 text-white shadow-sm shadow-blue-500/30"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
                  }`}
                >
                  <Code2 className="h-3.5 w-3.5" />
                  Query
                </button>

                <button
                  onClick={() => setActiveTab("results")}
                  className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all ${
                    activeTab === "results"
                      ? "bg-blue-600 text-white shadow-sm shadow-blue-500/30"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
                  }`}
                >
                  <Rows3 className="h-3.5 w-3.5" />
                  Results
                </button>

                <button
                  onClick={() => setActiveTab("chart")}
                  className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all ${
                    activeTab === "chart"
                      ? "bg-gradient-to-r from-blue-600 to-cyan-600 text-white shadow-sm shadow-cyan-500/30"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
                  }`}
                >
                  <BarChart2 className="h-3.5 w-3.5 text-cyan-400" />
                  Chart
                </button>

                <button
                  onClick={() => setActiveTab("assistant")}
                  className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all ${
                    activeTab === "assistant"
                      ? "bg-purple-600 text-white shadow-sm shadow-purple-500/30"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
                  }`}
                >
                  <Bot className="h-3.5 w-3.5 text-purple-400" />
                  AI Assistant
                </button>
              </div>
            </div>

            {/* Tab Workspace Views */}
            <div className="flex-1 p-6 overflow-y-auto">
              {/* TAB 1: Objects (Structure & Columns) */}
              {activeTab === "objects" && (
                <div>
                  {loadingTables[`${selectedTable.schema_name}.${selectedTable.name}`] ? (
                    <div className="py-16 flex justify-center">
                      <LoadingState message="Inspecting column schema definition..." />
                    </div>
                  ) : (
                    <div className="rounded-xl border border-slate-800 overflow-hidden shadow-lg">
                      <table className="w-full text-xs text-left">
                        <thead className="bg-slate-900/90 border-b border-slate-800 text-[11px] text-slate-400 uppercase tracking-wider font-mono">
                          <tr>
                            <th className="px-4 py-3 font-semibold">Column Name</th>
                            <th className="px-4 py-3 font-semibold">Type</th>
                            <th className="px-4 py-3 font-semibold">Nullable</th>
                            <th className="px-4 py-3 font-semibold">Key Constraints</th>
                            <th className="px-4 py-3 font-semibold text-right">Position</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/50 bg-slate-950/60 font-mono">
                          {columnsByTable[`${selectedTable.schema_name}.${selectedTable.name}`]?.map((col) => (
                            <tr key={col.name} className="hover:bg-slate-900/50 transition-colors">
                              <td className="px-4 py-3 font-medium text-slate-200 flex items-center gap-2">
                                {getColumnTypeIcon(col.data_type)}
                                <span>{col.name}</span>
                              </td>
                              <td className="px-4 py-3 text-emerald-400 font-semibold">{col.data_type}</td>
                              <td className="px-4 py-3 text-slate-400">{col.nullable ? "NULL" : "NOT NULL"}</td>
                              <td className="px-4 py-3">
                                {col.is_primary_key && (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30 mr-1.5">
                                    PRIMARY KEY
                                  </span>
                                )}
                                {col.foreign_key && (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-cyan-400 border border-blue-500/30" title={`References ${col.foreign_key.referred_schema}.${col.foreign_key.referred_table}`}>
                                    FK → {col.foreign_key.referred_table}
                                  </span>
                                )}
                              </td>
                              <td className="px-4 py-3 text-slate-500 text-right">{col.position}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: Query Console */}
              {activeTab === "query" && (
                <SqlConsole
                  warehouseId={warehouseId}
                  selectedTable={selectedTable}
                  initialQuery={assistantQuery}
                  onQueryResult={(data) => {
                    setLatestQueryResult(data)
                  }}
                  onOpenChart={() => setActiveTab("chart")}
                />
              )}

              {/* TAB 3: Results Table */}
              {activeTab === "results" && (
                <DataTable
                  key={`${selectedTable.schema_name}.${selectedTable.name}`}
                  warehouseId={warehouseId}
                  schemaName={selectedTable.schema_name}
                  tableName={selectedTable.name}
                />
              )}

              {/* TAB 4: Visual Analytics / Chart Canvas (Snowflake + Oracle) */}
              {activeTab === "chart" && (
                <div>
                  {isLoadingSample && !activeDataset ? (
                    <div className="py-16 flex justify-center">
                      <LoadingState message="Loading data points for visual canvas..." />
                    </div>
                  ) : activeDataset ? (
                    <VisualCanvas
                      columns={activeDataset.columns}
                      rows={activeDataset.rows}
                      title={activeDataset.title}
                      subtitle={activeDataset.subtitle}
                    />
                  ) : (
                    <div className="flex h-64 flex-col items-center justify-center rounded-xl border border-dashed border-slate-800 text-center p-6">
                      <BarChart2 className="h-10 w-10 text-slate-600 mb-2" />
                      <p className="text-sm font-semibold text-slate-300">No Data to Visualize</p>
                      <p className="text-xs text-slate-500 max-w-sm mt-1">
                        Run a SQL query or select a table with rows to generate interactive visual charts.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 5: AI Assistant */}
              {activeTab === "assistant" && (
                <div className="h-[600px] flex flex-col">
                  <AssistantChat
                    warehouseId={warehouseId}
                    selectedTable={selectedTable}
                    onSendToSqlConsole={handleSendToSqlConsole}
                    messages={conversations[currentContextKey] || []}
                    onMessagesChange={(msgs) => handleMessagesChange(currentContextKey, msgs)}
                  />
                </div>
              )}
            </div>
          </div>
        ) : (
          <Card className="border-slate-800 bg-slate-900/30 h-full border-dashed flex items-center justify-center min-h-[400px]">
            <div className="text-center text-slate-500 p-8">
              <Table2 className="h-12 w-12 mx-auto mb-3 opacity-20 text-cyan-400" />
              <h4 className="text-base font-semibold text-slate-400">Select Database Table</h4>
              <p className="text-xs text-slate-500 max-w-md mt-1">
                Choose a table from the Objects Explorer on the left to inspect columns, run SQL queries, preview rows, or plot visual charts.
              </p>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
