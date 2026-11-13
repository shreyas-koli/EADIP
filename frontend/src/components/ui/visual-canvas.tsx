"use client"

import * as React from "react"
import { 
  BarChart3, 
  LineChart, 
  PieChart, 
  AreaChart as AreaChartIcon, 
  SlidersHorizontal, 
  Filter, 
  Sparkles,
  Info
} from "lucide-react"

export interface VisualCanvasProps {
  columns: string[]
  rows: (string | number | boolean | null)[][]
  title?: string
  subtitle?: string
}

type ChartType = "line" | "bar" | "area" | "donut"
type AggregationType = "SUM" | "AVG" | "COUNT" | "MIN" | "MAX"

interface AggregatedDataPoint {
  label: string
  value: number
  rawCount: number
}

export function VisualCanvas({ columns, rows, title = "Visual Analytics", subtitle }: VisualCanvasProps) {
  // Identify numeric and non-numeric columns
  const columnTypes = React.useMemo(() => {
    const types: Record<string, "numeric" | "text"> = {}
    columns.forEach((col, idx) => {
      let isNum = true
      let nonNullCount = 0
      for (const row of rows.slice(0, 50)) {
        const val = row[idx]
        if (val !== null && val !== undefined && val !== "") {
          nonNullCount++
          if (isNaN(Number(val))) {
            isNum = false
            break
          }
        }
      }
      types[col] = nonNullCount > 0 && isNum ? "numeric" : "text"
    })
    return types
  }, [columns, rows])

  const numericColumns = columns.filter((col) => columnTypes[col] === "numeric")
  const textColumns = columns.filter((col) => columnTypes[col] === "text")

  // State
  const [chartType, setChartType] = React.useState<ChartType>("bar")
  const [userXAxisCol, setUserXAxisCol] = React.useState<string>("")
  const [userYAxisCol, setUserYAxisCol] = React.useState<string>("")

  const xAxisCol = (userXAxisCol && columns.includes(userXAxisCol)) 
    ? userXAxisCol 
    : (textColumns[0] || columns[0] || "")

  const yAxisCol = (userYAxisCol && columns.includes(userYAxisCol)) 
    ? userYAxisCol 
    : (numericColumns[0] || (columns.length > 1 ? columns[1] : columns[0]) || "")

  const [aggregation, setAggregation] = React.useState<AggregationType>("SUM")
  const [fillArea, setFillArea] = React.useState(true)
  const [showPoints, setShowPoints] = React.useState(true)
  const [showGrid, setShowGrid] = React.useState(true)
  const [showLabels, setShowLabels] = React.useState(false)
  
  // Dynamic filter state (Streamlit inspired)
  const [selectedCategories, setSelectedCategories] = React.useState<Set<string>>(new Set())
  const [hoveredPoint, setHoveredPoint] = React.useState<{ label: string; value: number; x: number; y: number } | null>(null)

  // Extract all unique categories for X-Axis
  const allCategories = React.useMemo(() => {
    const xIdx = columns.indexOf(xAxisCol)
    if (xIdx === -1) return []
    const set = new Set<string>()
    rows.forEach((r) => {
      const val = r[xIdx]
      set.add(val === null || val === undefined ? "NULL" : String(val))
    })
    return Array.from(set).slice(0, 30) // limit to 30 categories
  }, [columns, rows, xAxisCol])

  // Aggregate Data
  const aggregatedData: AggregatedDataPoint[] = React.useMemo(() => {
    const xIdx = columns.indexOf(xAxisCol)
    const yIdx = columns.indexOf(yAxisCol)
    if (xIdx === -1 || (aggregation !== "COUNT" && yIdx === -1)) return []

    const map = new Map<string, { sum: number; count: number; min: number; max: number }>()

    rows.forEach((row) => {
      const rawX = row[xIdx]
      const label = rawX === null || rawX === undefined ? "NULL" : String(rawX)

      // Filter out if user deselected this category
      if (selectedCategories.size > 0 && !selectedCategories.has(label)) {
        return
      }

      let yVal = 0
      if (yIdx !== -1) {
        const rawY = row[yIdx]
        const num = Number(rawY)
        yVal = isNaN(num) ? 0 : num
      }

      const existing = map.get(label) || { sum: 0, count: 0, min: Infinity, max: -Infinity }
      existing.sum += yVal
      existing.count += 1
      existing.min = Math.min(existing.min, yVal)
      existing.max = Math.max(existing.max, yVal)
      map.set(label, existing)
    })

    const result: AggregatedDataPoint[] = []
    map.forEach((metrics, label) => {
      let finalVal = 0
      if (aggregation === "SUM") finalVal = metrics.sum
      else if (aggregation === "AVG") finalVal = metrics.count > 0 ? metrics.sum / metrics.count : 0
      else if (aggregation === "COUNT") finalVal = metrics.count
      else if (aggregation === "MIN") finalVal = metrics.min === Infinity ? 0 : metrics.min
      else if (aggregation === "MAX") finalVal = metrics.max === -Infinity ? 0 : metrics.max

      result.push({
        label,
        value: Math.round(finalVal * 100) / 100,
        rawCount: metrics.count,
      })
    })

    // Sort by value descending for bar/donut, or natural label for line/area
    if (chartType === "bar" || chartType === "donut") {
      result.sort((a, b) => b.value - a.value)
    }

    return result.slice(0, 20) // max 20 data points for readability
  }, [columns, rows, xAxisCol, yAxisCol, aggregation, selectedCategories, chartType])

  // Summary Metrics
  const summary = React.useMemo(() => {
    if (aggregatedData.length === 0) return { total: 0, avg: 0, max: 0, min: 0 }
    let total = 0
    let max = -Infinity
    let min = Infinity
    aggregatedData.forEach((d) => {
      total += d.value
      if (d.value > max) max = d.value
      if (d.value < min) min = d.value
    })
    return {
      total: Math.round(total * 100) / 100,
      avg: Math.round((total / aggregatedData.length) * 100) / 100,
      max: max === -Infinity ? 0 : max,
      min: min === Infinity ? 0 : min,
    }
  }, [aggregatedData])

  const toggleCategory = (cat: string) => {
    const next = new Set(selectedCategories)
    if (next.has(cat)) {
      next.delete(cat)
    } else {
      next.add(cat)
    }
    setSelectedCategories(next)
  }

  const selectAllCategories = () => setSelectedCategories(new Set())

  // Render SVG Chart
  const svgWidth = 720
  const svgHeight = 340
  const margin = { top: 25, right: 30, bottom: 65, left: 65 }
  const chartW = svgWidth - margin.left - margin.right
  const chartH = svgHeight - margin.top - margin.bottom

  const maxValue = Math.max(...aggregatedData.map((d) => d.value), 1)
  const minValue = Math.min(...aggregatedData.map((d) => d.value), 0)
  const valueSpan = maxValue - minValue || 1

  return (
    <div className="flex flex-col gap-6 rounded-xl border border-slate-800 bg-slate-950/70 backdrop-blur-xl p-5 shadow-2xl">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-cyan-400" />
            <h3 className="text-lg font-bold tracking-tight text-slate-100">{title}</h3>
            <span className="rounded-full bg-cyan-950/60 px-2 py-0.5 text-[10px] font-semibold text-cyan-400 border border-cyan-800/40">
              Interactive Canvas
            </span>
          </div>
          {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
        </div>

        {/* Chart Type Selector */}
        <div className="flex items-center gap-1 rounded-lg border border-slate-800 bg-slate-900/90 p-1">
          <button
            onClick={() => setChartType("bar")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              chartType === "bar"
                ? "bg-blue-600 text-white shadow-sm shadow-blue-500/20"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
            }`}
          >
            <BarChart3 className="h-3.5 w-3.5" />
            Bar
          </button>
          <button
            onClick={() => setChartType("line")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              chartType === "line"
                ? "bg-blue-600 text-white shadow-sm shadow-blue-500/20"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
            }`}
          >
            <LineChart className="h-3.5 w-3.5" />
            Line
          </button>
          <button
            onClick={() => setChartType("area")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              chartType === "area"
                ? "bg-blue-600 text-white shadow-sm shadow-blue-500/20"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
            }`}
          >
            <AreaChartIcon className="h-3.5 w-3.5" />
            Area
          </button>
          <button
            onClick={() => setChartType("donut")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
              chartType === "donut"
                ? "bg-blue-600 text-white shadow-sm shadow-blue-500/20"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
            }`}
          >
            <PieChart className="h-3.5 w-3.5" />
            Donut
          </button>
        </div>
      </div>

      {/* Metric Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="rounded-lg border border-slate-800/90 bg-slate-900/40 p-3">
          <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">Total {aggregation}</span>
          <p className="text-xl font-bold text-slate-100 mt-1 font-mono">{summary.total.toLocaleString()}</p>
        </div>
        <div className="rounded-lg border border-slate-800/90 bg-slate-900/40 p-3">
          <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">Average</span>
          <p className="text-xl font-bold text-cyan-400 mt-1 font-mono">{summary.avg.toLocaleString()}</p>
        </div>
        <div className="rounded-lg border border-slate-800/90 bg-slate-900/40 p-3">
          <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">Peak Value</span>
          <p className="text-xl font-bold text-emerald-400 mt-1 font-mono">{summary.max.toLocaleString()}</p>
        </div>
        <div className="rounded-lg border border-slate-800/90 bg-slate-900/40 p-3">
          <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">Data Points</span>
          <p className="text-xl font-bold text-slate-300 mt-1 font-mono">{aggregatedData.length}</p>
        </div>
      </div>

      {/* Main Canvas + Control Drawer Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* SVG Visualization Canvas */}
        <div className="lg:col-span-3 flex flex-col rounded-xl border border-slate-800 bg-slate-950 p-4 relative overflow-hidden">
          {aggregatedData.length === 0 ? (
            <div className="flex h-[340px] flex-col items-center justify-center text-slate-500 text-sm">
              <Info className="h-8 w-8 text-slate-600 mb-2" />
              <span>No data points available for current configuration.</span>
              <span className="text-xs text-slate-600 mt-1">Try selecting different dimension or metric columns.</span>
            </div>
          ) : (
            <div className="relative w-full overflow-x-auto">
              {/* Tooltip Overlay */}
              {hoveredPoint && (
                <div
                  className="pointer-events-none absolute z-30 -translate-x-1/2 -translate-y-full rounded-lg border border-cyan-500/40 bg-slate-900/95 px-3 py-1.5 text-xs shadow-xl backdrop-blur-md transition-all"
                  style={{ left: hoveredPoint.x, top: hoveredPoint.y - 10 }}
                >
                  <p className="font-semibold text-slate-200">{hoveredPoint.label}</p>
                  <p className="font-mono text-cyan-400">
                    {aggregation}: <span className="font-bold text-white">{hoveredPoint.value.toLocaleString()}</span>
                  </p>
                </div>
              )}

              <svg
                viewBox={`0 0 ${svgWidth} ${svgHeight}`}
                className="w-full h-auto min-w-[500px]"
                onMouseLeave={() => setHoveredPoint(null)}
              >
                <defs>
                  {/* Linear Gradients for Bar / Area */}
                  <linearGradient id="primaryBarGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.9" />
                    <stop offset="100%" stopColor="#1d4ed8" stopOpacity="0.4" />
                  </linearGradient>
                  <linearGradient id="areaFillGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.5" />
                    <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.0" />
                  </linearGradient>
                  <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#38bdf8" />
                    <stop offset="100%" stopColor="#818cf8" />
                  </linearGradient>
                </defs>

                {/* Gridlines */}
                {showGrid && chartType !== "donut" && (
                  <g className="stroke-slate-800/80 stroke-dasharray-2">
                    {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
                      const y = margin.top + chartH * (1 - pct)
                      const val = minValue + valueSpan * pct
                      return (
                        <g key={i}>
                          <line x1={margin.left} y1={y} x2={svgWidth - margin.right} y2={y} strokeWidth="1" strokeDasharray="3 3" />
                          <text
                            x={margin.left - 10}
                            y={y + 4}
                            textAnchor="end"
                            className="fill-slate-500 text-[10px] font-mono"
                          >
                            {Math.round(val).toLocaleString()}
                          </text>
                        </g>
                      )
                    })}
                  </g>
                )}

                {/* BAR CHART */}
                {chartType === "bar" && (
                  <g>
                    {aggregatedData.map((d, i) => {
                      const barWidth = Math.min(36, Math.max(12, (chartW / aggregatedData.length) * 0.65))
                      const step = chartW / aggregatedData.length
                      const x = margin.left + i * step + (step - barWidth) / 2
                      const barH = ((d.value - Math.min(0, minValue)) / valueSpan) * chartH
                      const y = margin.top + chartH - barH

                      return (
                        <g
                          key={d.label + i}
                          className="cursor-pointer group"
                          onMouseEnter={() => setHoveredPoint({ label: d.label, value: d.value, x: x + barWidth / 2, y })}
                        >
                          <rect
                            x={x}
                            y={y}
                            width={barWidth}
                            height={Math.max(2, barH)}
                            rx="4"
                            fill="url(#primaryBarGrad)"
                            className="transition-all duration-200 group-hover:brightness-125 group-hover:filter group-hover:drop-shadow-[0_0_8px_rgba(56,189,248,0.5)]"
                          />
                          {showLabels && (
                            <text
                              x={x + barWidth / 2}
                              y={y - 6}
                              textAnchor="middle"
                              className="fill-slate-400 text-[9px] font-mono"
                            >
                              {d.value.toLocaleString()}
                            </text>
                          )}
                          {/* X-axis Label */}
                          <text
                            x={x + barWidth / 2}
                            y={margin.top + chartH + 18}
                            textAnchor="end"
                            transform={`rotate(-40, ${x + barWidth / 2}, ${margin.top + chartH + 18})`}
                            className="fill-slate-400 text-[10px] font-medium"
                          >
                            {d.label.length > 14 ? `${d.label.slice(0, 12)}…` : d.label}
                          </text>
                        </g>
                      )
                    })}
                  </g>
                )}

                {/* LINE & AREA CHART */}
                {(chartType === "line" || chartType === "area") && (
                  <g>
                    {(() => {
                      const points = aggregatedData.map((d, i) => {
                        const step = chartW / Math.max(1, aggregatedData.length - 1)
                        const x = margin.left + i * step
                        const y = margin.top + chartH - ((d.value - minValue) / valueSpan) * chartH
                        return { x, y, d }
                      })

                      // Smooth cubic curve path
                      let pathD = ""
                      points.forEach((p, i) => {
                        if (i === 0) pathD += `M ${p.x} ${p.y}`
                        else {
                          const prev = points[i - 1]
                          const cx = (prev.x + p.x) / 2
                          pathD += ` C ${cx} ${prev.y}, ${cx} ${p.y}, ${p.x} ${p.y}`
                        }
                      })

                      const areaD = `${pathD} L ${points[points.length - 1].x} ${margin.top + chartH} L ${points[0].x} ${margin.top + chartH} Z`

                      return (
                        <>
                          {/* Area Fill */}
                          {(chartType === "area" || fillArea) && (
                            <path d={areaD} fill="url(#areaFillGrad)" />
                          )}
                          {/* Line Path */}
                          <path
                            d={pathD}
                            fill="none"
                            stroke="url(#lineGrad)"
                            strokeWidth="3"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                          {/* Point Dots */}
                          {showPoints &&
                            points.map((p, i) => (
                              <g
                                key={i}
                                className="cursor-pointer group"
                                onMouseEnter={() => setHoveredPoint({ label: p.d.label, value: p.d.value, x: p.x, y: p.y })}
                              >
                                <circle
                                  cx={p.x}
                                  cy={p.y}
                                  r="4.5"
                                  className="fill-slate-950 stroke-cyan-400 stroke-2 transition-all duration-200 group-hover:r-6 group-hover:stroke-white group-hover:drop-shadow-[0_0_8px_rgba(6,182,212,0.8)]"
                                />
                                {showLabels && (
                                  <text
                                    x={p.x}
                                    y={p.y - 10}
                                    textAnchor="middle"
                                    className="fill-slate-300 text-[9px] font-mono"
                                  >
                                    {p.d.value.toLocaleString()}
                                  </text>
                                )}
                                <text
                                  x={p.x}
                                  y={margin.top + chartH + 18}
                                  textAnchor="end"
                                  transform={`rotate(-40, ${p.x}, ${margin.top + chartH + 18})`}
                                  className="fill-slate-400 text-[10px]"
                                >
                                  {p.d.label.length > 14 ? `${p.d.label.slice(0, 12)}…` : p.d.label}
                                </text>
                              </g>
                            ))}
                        </>
                      )
                    })()}
                  </g>
                )}

                {/* DONUT CHART */}
                {chartType === "donut" && (
                  <g transform={`translate(${svgWidth / 2}, ${svgHeight / 2})`}>
                    {(() => {
                      const total = aggregatedData.reduce((acc, curr) => acc + curr.value, 0) || 1
                      const radius = 105
                      const innerRadius = 60
                      let currentAngle = -Math.PI / 2

                      const colors = [
                        "#38bdf8", "#818cf8", "#34d399", "#f59e0b", 
                        "#f43f5e", "#a855f7", "#06b6d4", "#ec4899"
                      ]

                      return (
                        <>
                          {aggregatedData.map((d, i) => {
                            const sliceAngle = (d.value / total) * 2 * Math.PI
                            const startAngle = currentAngle
                            const endAngle = currentAngle + sliceAngle
                            currentAngle = endAngle

                            const x1 = Math.cos(startAngle) * radius
                            const y1 = Math.sin(startAngle) * radius
                            const x2 = Math.cos(endAngle) * radius
                            const y2 = Math.sin(endAngle) * radius

                            const ix1 = Math.cos(startAngle) * innerRadius
                            const iy1 = Math.sin(startAngle) * innerRadius
                            const ix2 = Math.cos(endAngle) * innerRadius
                            const iy2 = Math.sin(endAngle) * innerRadius

                            const largeArc = sliceAngle > Math.PI ? 1 : 0
                            const color = colors[i % colors.length]

                            const path = `
                              M ${ix1} ${iy1}
                              L ${x1} ${y1}
                              A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}
                              L ${ix2} ${iy2}
                              A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${ix1} ${iy1}
                              Z
                            `

                            return (
                              <path
                                key={d.label + i}
                                d={path}
                                fill={color}
                                className="cursor-pointer transition-transform duration-200 hover:scale-105 hover:brightness-125"
                                onMouseEnter={() => {
                                  setHoveredPoint({
                                    label: d.label,
                                    value: d.value,
                                    x: svgWidth / 2,
                                    y: svgHeight / 2 - 20,
                                  })
                                }}
                              />
                            )
                          })}
                          <circle cx="0" cy="0" r={innerRadius - 2} className="fill-slate-950" />
                          <text x="0" y="-4" textAnchor="middle" className="fill-slate-400 text-xs font-medium">
                            Total {aggregation}
                          </text>
                          <text x="0" y="18" textAnchor="middle" className="fill-white font-mono text-base font-bold">
                            {summary.total.toLocaleString()}
                          </text>
                        </>
                      )
                    })()}
                  </g>
                )}
              </svg>
            </div>
          )}

          {/* Dynamic Streamlit Category Filter Pills Bar */}
          {allCategories.length > 1 && (
            <div className="mt-3 border-t border-slate-800/80 pt-3">
              <div className="flex items-center justify-between mb-2">
                <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-400">
                  <Filter className="h-3 w-3 text-cyan-400" />
                  Filter by {xAxisCol}:
                </span>
                {selectedCategories.size > 0 && (
                  <button
                    onClick={selectAllCategories}
                    className="text-[11px] text-cyan-400 hover:text-cyan-300 transition-colors"
                  >
                    Reset Filter ({selectedCategories.size} selected)
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
                {allCategories.map((cat) => {
                  const isSelected = selectedCategories.has(cat) || selectedCategories.size === 0
                  return (
                    <button
                      key={cat}
                      onClick={() => toggleCategory(cat)}
                      className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium transition-all ${
                        isSelected
                          ? "bg-slate-800 text-slate-200 border border-slate-700 hover:border-slate-500"
                          : "bg-slate-900/40 text-slate-600 border border-slate-900 line-through"
                      }`}
                    >
                      {cat}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Right Configuration Drawer (Snowflake + Oracle Analytics inspired) */}
        <div className="flex flex-col gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
            <SlidersHorizontal className="h-4 w-4 text-blue-400" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300">Data Mapping</span>
          </div>

          {/* Dimension (X-Axis) */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-slate-400 flex items-center justify-between">
              <span>Dimension (X-Axis)</span>
              <span className="text-[10px] text-slate-500">Categorical</span>
            </label>
            <select
              value={xAxisCol}
              onChange={(e) => {
                setUserXAxisCol(e.target.value)
                setSelectedCategories(new Set())
              }}
              className="h-8 rounded-md border border-slate-800 bg-slate-950 px-2.5 text-xs text-slate-200 focus:border-blue-500 focus:outline-none"
            >
              {columns.map((col) => (
                <option key={col} value={col}>
                  {col} ({columnTypes[col] === "numeric" ? "#" : "Aa"})
                </option>
              ))}
            </select>
          </div>

          {/* Measure (Y-Axis) */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-slate-400 flex items-center justify-between">
              <span>Metric (Y-Axis)</span>
              <span className="text-[10px] text-slate-500">Numeric</span>
            </label>
            <select
              value={yAxisCol}
              onChange={(e) => setUserYAxisCol(e.target.value)}
              className="h-8 rounded-md border border-slate-800 bg-slate-950 px-2.5 text-xs text-slate-200 focus:border-blue-500 focus:outline-none"
            >
              {columns.map((col) => (
                <option key={col} value={col}>
                  {col} ({columnTypes[col] === "numeric" ? "#" : "Aa"})
                </option>
              ))}
            </select>
          </div>

          {/* Aggregation Function */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-slate-400">Aggregation Function</label>
            <select
              value={aggregation}
              onChange={(e) => setAggregation(e.target.value as AggregationType)}
              className="h-8 rounded-md border border-slate-800 bg-slate-950 px-2.5 text-xs text-slate-200 focus:border-blue-500 focus:outline-none"
            >
              <option value="SUM">SUM</option>
              <option value="AVG">AVG (Average)</option>
              <option value="COUNT">COUNT (Row Count)</option>
              <option value="MIN">MIN (Minimum)</option>
              <option value="MAX">MAX (Maximum)</option>
            </select>
          </div>

          {/* Appearance Toggles */}
          <div className="border-t border-slate-800 pt-3 flex flex-col gap-2.5">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Appearance</span>
            
            <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={showGrid}
                onChange={(e) => setShowGrid(e.target.checked)}
                className="rounded border-slate-700 bg-slate-950 text-blue-600 focus:ring-0"
              />
              Show Gridlines
            </label>

            {chartType !== "donut" && (
              <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showPoints}
                  onChange={(e) => setShowPoints(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-950 text-blue-600 focus:ring-0"
                />
                Show Data Points
              </label>
            )}

            {(chartType === "line" || chartType === "area") && (
              <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={fillArea}
                  onChange={(e) => setFillArea(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-950 text-blue-600 focus:ring-0"
                />
                Fill Area Gradient
              </label>
            )}

            <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={showLabels}
                onChange={(e) => setShowLabels(e.target.checked)}
                className="rounded border-slate-700 bg-slate-950 text-blue-600 focus:ring-0"
              />
              Display Value Labels
            </label>
          </div>
        </div>
      </div>
    </div>
  )
}
