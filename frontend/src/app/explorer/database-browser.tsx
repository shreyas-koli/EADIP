"use client"

import * as React from "react"
import { 
  DatabaseSchema, 
  DatabaseTable, 
  DatabaseColumn,
  explorerApi 
} from "@/lib/api/explorer"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { Button } from "@/components/ui/button"
import { 
  ChevronRight, 
  ChevronDown, 
  Database, 
  Table2, 
  Columns, 
  RefreshCw,
  AlertCircle,
  Key
} from "lucide-react"

interface DatabaseBrowserProps {
  warehouseId: number
}

export function DatabaseBrowser({ warehouseId }: DatabaseBrowserProps) {
  const [schemas, setSchemas] = React.useState<DatabaseSchema[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  // Lazy loading state maps
  const [tablesBySchema, setTablesBySchema] = React.useState<Record<string, DatabaseTable[]>>({})
  const [columnsByTable, setColumnsByTable] = React.useState<Record<string, DatabaseColumn[]>>({})
  
  const [loadingSchemas, setLoadingSchemas] = React.useState<Record<string, boolean>>({})
  const [loadingTables, setLoadingTables] = React.useState<Record<string, boolean>>({})

  // UI state
  const [expandedSchemas, setExpandedSchemas] = React.useState<Set<string>>(new Set())
  const [expandedTables, setExpandedTables] = React.useState<Set<string>>(new Set())
  const [selectedTable, setSelectedTable] = React.useState<DatabaseTable | null>(null)

  const fetchSchemas = React.useCallback(async (showLoading = true) => {
    try {
      if (showLoading) setIsLoading(true)
      const data = await explorerApi.getSchemas(warehouseId)
      setSchemas(data)
      setError(null)
    } catch (err) {
      const e = err as Error
      setError(e.message || "Failed to load schemas.")
    } finally {
      if (showLoading) setIsLoading(false)
    }
  }, [warehouseId])

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
    fetchSchemas()
  }, [])

  const handleRefresh = async () => {
    await fetchSchemas(true)
    // Clear inner caches
    setTablesBySchema({})
    setColumnsByTable({})
    setExpandedSchemas(new Set())
    setExpandedTables(new Set())
    setSelectedTable(null)
  }

  const toggleSchema = async (schemaName: string) => {
    const newExpanded = new Set(expandedSchemas)
    if (newExpanded.has(schemaName)) {
      newExpanded.delete(schemaName)
      setExpandedSchemas(newExpanded)
    } else {
      newExpanded.add(schemaName)
      setExpandedSchemas(newExpanded)
      
      // Lazy load tables if not loaded
      if (!tablesBySchema[schemaName]) {
        try {
          setLoadingSchemas(prev => ({ ...prev, [schemaName]: true }))
          const tables = await explorerApi.getTables(warehouseId, schemaName)
          setTablesBySchema(prev => ({ ...prev, [schemaName]: tables }))
        } catch (err) {
          // Handle individual load error
          console.error("Failed to load tables", err)
        } finally {
          setLoadingSchemas(prev => ({ ...prev, [schemaName]: false }))
        }
      }
    }
  }

  const toggleTable = async (table: DatabaseTable) => {
    const tableKey = `${table.schema_name}.${table.name}`
    const newExpanded = new Set(expandedTables)
    
    // Always select the table when clicked
    setSelectedTable(table)
    
    if (newExpanded.has(tableKey)) {
      newExpanded.delete(tableKey)
      setExpandedTables(newExpanded)
    } else {
      newExpanded.add(tableKey)
      setExpandedTables(newExpanded)
      
      // Lazy load columns if not loaded
      if (!columnsByTable[tableKey]) {
        try {
          setLoadingTables(prev => ({ ...prev, [tableKey]: true }))
          const columns = await explorerApi.getColumns(warehouseId, table.schema_name, table.name)
          setColumnsByTable(prev => ({ ...prev, [tableKey]: columns }))
        } catch (err) {
          console.error("Failed to load columns", err)
        } finally {
          setLoadingTables(prev => ({ ...prev, [tableKey]: false }))
        }
      }
    }
  }

  if (isLoading) {
    return (
      <Card className="border-slate-800 bg-slate-900/50">
        <div className="flex h-64 items-center justify-center">
          <LoadingState message="Loading database structure..." />
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="border-slate-800 bg-slate-900/50">
        <EmptyState
          icon={AlertCircle}
          title="Failed to load structure"
          description={error}
          action={<Button onClick={handleRefresh} variant="outline">Retry</Button>}
        />
      </Card>
    )
  }

  if (schemas.length === 0) {
    return (
      <Card className="border-slate-800 bg-slate-900/50">
        <EmptyState
          icon={Database}
          title="Empty Database"
          description="No user schemas were found in this database."
          action={<Button onClick={handleRefresh} variant="outline"><RefreshCw className="mr-2 h-4 w-4" /> Refresh</Button>}
        />
      </Card>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {/* Left Pane: Tree View */}
      <Card className="col-span-1 border-slate-800 bg-slate-900/50 flex flex-col max-h-[800px]">
        <CardHeader className="flex flex-row items-center justify-between py-4 px-4 border-b border-slate-800">
          <CardTitle className="text-sm font-semibold flex items-center">
            <Database className="mr-2 h-4 w-4 text-blue-500" />
            DATABASE
          </CardTitle>
          <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={handleRefresh} title="Refresh structure">
            <RefreshCw className="h-4 w-4 text-slate-400" />
          </Button>
        </CardHeader>
        <CardContent className="flex-1 overflow-y-auto p-2">
          <div className="space-y-1">
            {schemas.map(schema => (
              <div key={schema.name}>
                {/* Schema Node */}
                <button
                  onClick={() => toggleSchema(schema.name)}
                  className="flex w-full items-center py-1.5 px-2 text-sm text-slate-300 hover:bg-slate-800 rounded-md transition-colors text-left"
                >
                  {expandedSchemas.has(schema.name) ? (
                    <ChevronDown className="mr-1 h-4 w-4 text-slate-500 shrink-0" />
                  ) : (
                    <ChevronRight className="mr-1 h-4 w-4 text-slate-500 shrink-0" />
                  )}
                  <span className="font-medium truncate">{schema.name}</span>
                </button>
                
                {/* Schema Children (Tables) */}
                {expandedSchemas.has(schema.name) && (
                  <div className="ml-5 border-l border-slate-800 pl-2 py-1 space-y-1">
                    {loadingSchemas[schema.name] ? (
                      <div className="text-xs text-slate-500 py-1 pl-4">Loading tables...</div>
                    ) : tablesBySchema[schema.name]?.length === 0 ? (
                      <div className="text-xs text-slate-500 py-1 pl-4 italic">No tables</div>
                    ) : (
                      tablesBySchema[schema.name]?.map(table => {
                        const tableKey = `${schema.name}.${table.name}`
                        const isSelected = selectedTable?.schema_name === schema.name && selectedTable?.name === table.name
                        
                        return (
                          <div key={tableKey}>
                            {/* Table Node */}
                            <button
                              onClick={() => toggleTable(table)}
                              className={`flex w-full items-center py-1 px-2 text-sm rounded-md transition-colors text-left ${
                                isSelected ? "bg-blue-900/30 text-blue-400" : "text-slate-400 hover:bg-slate-800 hover:text-slate-300"
                              }`}
                            >
                              {expandedTables.has(tableKey) ? (
                                <ChevronDown className="mr-1 h-3.5 w-3.5 text-slate-500 shrink-0" />
                              ) : (
                                <ChevronRight className="mr-1 h-3.5 w-3.5 text-slate-500 shrink-0" />
                              )}
                              <Table2 className="mr-2 h-3.5 w-3.5 shrink-0 opacity-70" />
                              <span className="truncate">{table.name}</span>
                            </button>
                            
                            {/* Table Children (Columns) */}
                            {expandedTables.has(tableKey) && (
                              <div className="ml-5 border-l border-slate-800 pl-2 py-1 space-y-1">
                                {loadingTables[tableKey] ? (
                                  <div className="text-xs text-slate-500 py-1 pl-2">Loading columns...</div>
                                ) : columnsByTable[tableKey]?.length === 0 ? (
                                  <div className="text-xs text-slate-500 py-1 pl-2 italic">No columns</div>
                                ) : (
                                  columnsByTable[tableKey]?.map(column => (
                                    <div key={column.name} className="flex items-center py-0.5 px-2 text-xs text-slate-500 group">
                                      <Columns className="mr-2 h-3 w-3 opacity-50 shrink-0" />
                                      <span className="truncate flex-1 group-hover:text-slate-300 transition-colors">
                                        {column.name}
                                      </span>
                                      {column.is_primary_key && (
                                        <span title="Primary Key">
                                          <Key className="h-3 w-3 text-amber-500/70 ml-1" />
                                        </span>
                                      )}
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
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Right Pane: Details */}
      <div className="col-span-1 md:col-span-2">
        {selectedTable ? (
          <Card className="border-slate-800 bg-slate-900/50 max-h-[800px] flex flex-col">
            <CardHeader className="border-b border-slate-800">
              <CardTitle className="text-lg flex items-center">
                <Table2 className="mr-2 h-5 w-5 text-blue-500" />
                {selectedTable.name}
              </CardTitle>
              <div className="flex gap-4 text-sm text-slate-400 mt-2">
                <div>Schema: <span className="text-slate-200">{selectedTable.schema_name}</span></div>
                <div>Rows: <span className="text-slate-200">~{selectedTable.estimated_row_count.toLocaleString()}</span></div>
                {columnsByTable[`${selectedTable.schema_name}.${selectedTable.name}`] && (
                  <div>Columns: <span className="text-slate-200">{columnsByTable[`${selectedTable.schema_name}.${selectedTable.name}`].length}</span></div>
                )}
              </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto p-0">
              {loadingTables[`${selectedTable.schema_name}.${selectedTable.name}`] ? (
                <div className="p-8 flex justify-center">
                  <LoadingState message="Loading columns..." />
                </div>
              ) : (
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-slate-400 uppercase bg-slate-900 sticky top-0 border-b border-slate-800">
                    <tr>
                      <th className="px-4 py-3 font-medium">Column Name</th>
                      <th className="px-4 py-3 font-medium">Data Type</th>
                      <th className="px-4 py-3 font-medium">Nullable</th>
                      <th className="px-4 py-3 font-medium text-right">Position</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/50">
                    {columnsByTable[`${selectedTable.schema_name}.${selectedTable.name}`]?.map((col) => (
                      <tr key={col.name} className="hover:bg-slate-800/50">
                        <td className="px-4 py-3 font-medium text-slate-200 flex items-center">
                          {col.name}
                          {col.is_primary_key && (
                            <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-500 border border-amber-500/20">
                              PK
                            </span>
                          )}
                          {col.foreign_key && (
                            <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20" title={`References ${col.foreign_key.referred_schema}.${col.foreign_key.referred_table}`}>
                              FK
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-emerald-400/80 font-mono text-xs">{col.data_type}</td>
                        <td className="px-4 py-3 text-slate-400">{col.nullable ? "Yes" : "No"}</td>
                        <td className="px-4 py-3 text-slate-500 text-right">{col.position}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        ) : (
          <Card className="border-slate-800 bg-slate-900/50 h-full border-dashed flex items-center justify-center min-h-[300px]">
            <div className="text-center text-slate-500">
              <Table2 className="h-12 w-12 mx-auto mb-4 opacity-20" />
              <p>Select a table from the sidebar to view its structure</p>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
