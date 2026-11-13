"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { 
  Search, 
  LayoutDashboard, 
  Database, 
  Compass, 
  History, 
  Settings, 
  Play, 
  PlusCircle, 
  Code2, 
  ShieldAlert, 
  X,
  ArrowRight
} from "lucide-react"

interface CommandPaletteProps {
  isOpen: boolean
  onClose: () => void
}

interface CommandItem {
  id: string
  title: string
  subtitle?: string
  icon: React.ElementType
  category: "Navigation" | "Quick Actions"
  action: () => void
}

export function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
  const router = useRouter()
  const [query, setQuery] = React.useState("")
  const [selectedIndex, setSelectedIndex] = React.useState(0)
  const inputRef = React.useRef<HTMLInputElement>(null)

  const commands: CommandItem[] = React.useMemo(() => [
    // Navigation
    {
      id: "nav-dashboard",
      title: "Dashboard",
      subtitle: "Overview of warehouse health, fleet metrics, and recent activity",
      icon: LayoutDashboard,
      category: "Navigation",
      action: () => router.push("/dashboard"),
    },
    {
      id: "nav-warehouses",
      title: "Warehouses Management",
      subtitle: "Add, configure, test connections, and manage data warehouses",
      icon: Database,
      category: "Navigation",
      action: () => router.push("/warehouses"),
    },
    {
      id: "nav-explorer",
      title: "Warehouse Explorer & SQL Console",
      subtitle: "Browse schema tree, execute SQL queries, inspect tables, and plot charts",
      icon: Compass,
      category: "Navigation",
      action: () => router.push("/explorer"),
    },
    {
      id: "nav-discovery",
      title: "Autonomous Discovery Pipeline",
      subtitle: "Run multi-agent discovery, view live SSE logs, and inspect recommendations",
      icon: Play,
      category: "Navigation",
      action: () => router.push("/discovery"),
    },
    {
      id: "nav-history",
      title: "Audit History & Recommendation Timeline",
      subtitle: "Audit historical sessions, R1-R6 deterministic explanations, and outcomes",
      icon: History,
      category: "Navigation",
      action: () => router.push("/history"),
    },
    {
      id: "nav-settings",
      title: "Platform Settings",
      subtitle: "System preferences, API access, and user profile configuration",
      icon: Settings,
      category: "Navigation",
      action: () => router.push("/settings"),
    },
    // Quick Actions
    {
      id: "act-run-discovery",
      title: "Start Discovery Execution",
      subtitle: "Trigger full autonomous multi-wave intelligence pipeline",
      icon: Play,
      category: "Quick Actions",
      action: () => router.push("/discovery"),
    },
    {
      id: "act-connect-warehouse",
      title: "Connect New Warehouse",
      subtitle: "Register a PostgreSQL, MySQL, Snowflake, or BigQuery instance",
      icon: PlusCircle,
      category: "Quick Actions",
      action: () => router.push("/warehouses"),
    },
    {
      id: "act-sql-query",
      title: "New SQL Query Session",
      subtitle: "Open interactive worksheet with results table & visual analytics",
      icon: Code2,
      category: "Quick Actions",
      action: () => router.push("/explorer"),
    },
    {
      id: "act-view-approvals",
      title: "Review Action Plans & Approvals",
      subtitle: "Inspect pending recommendations awaiting controlled execution",
      icon: ShieldAlert,
      category: "Quick Actions",
      action: () => router.push("/discovery"),
    },
  ], [router])

  // Filter commands
  const filteredCommands = React.useMemo(() => {
    if (!query.trim()) return commands
    const q = query.toLowerCase()
    return commands.filter(
      (c) => c.title.toLowerCase().includes(q) || (c.subtitle && c.subtitle.toLowerCase().includes(q))
    )
  }, [commands, query])

  const handleClose = React.useCallback(() => {
    setQuery("")
    setSelectedIndex(0)
    onClose()
  }, [onClose])

  // Focus input when opened
  React.useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [isOpen])

  // Keyboard navigation
  React.useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault()
        handleClose()
      } else if (e.key === "ArrowDown") {
        e.preventDefault()
        setSelectedIndex((prev) => (prev + 1) % Math.max(1, filteredCommands.length))
      } else if (e.key === "ArrowUp") {
        e.preventDefault()
        setSelectedIndex((prev) => (prev - 1 + filteredCommands.length) % Math.max(1, filteredCommands.length))
      } else if (e.key === "Enter" && filteredCommands.length > 0) {
        e.preventDefault()
        const selected = filteredCommands[selectedIndex]
        if (selected) {
          selected.action()
          handleClose()
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [isOpen, filteredCommands, selectedIndex, handleClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-slate-950/80 backdrop-blur-md transition-opacity" 
        onClick={handleClose} 
      />

      {/* Palette Modal */}
      <div className="relative w-full max-w-2xl rounded-2xl border border-slate-700/80 bg-slate-900/95 shadow-2xl shadow-blue-950/30 overflow-hidden ring-1 ring-white/10 z-10 flex flex-col max-h-[75vh]">
        {/* Search Input Bar */}
        <div className="flex items-center px-4 py-3.5 border-b border-slate-800 bg-slate-950/60">
          <Search className="h-5 w-5 text-cyan-400 mr-3 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setSelectedIndex(0)
            }}
            placeholder="Type a command or search platform (e.g. 'warehouse', 'SQL', 'discovery')..."
            className="w-full bg-transparent text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none"
          />
          <button 
            onClick={handleClose} 
            className="rounded p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Command List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {filteredCommands.length === 0 ? (
            <div className="py-12 text-center text-sm text-slate-500">
              No matching commands or destinations found for &quot;{query}&quot;.
            </div>
          ) : (
            filteredCommands.map((item, idx) => {
              const isSelected = idx === selectedIndex
              const Icon = item.icon
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    item.action()
                    handleClose()
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`w-full flex items-center justify-between rounded-xl px-3.5 py-2.5 text-left transition-all ${
                    isSelected
                      ? "bg-blue-600/20 text-white border border-blue-500/30"
                      : "text-slate-300 hover:bg-slate-800/60 border border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`p-2 rounded-lg shrink-0 ${
                      isSelected ? "bg-blue-500 text-white" : "bg-slate-800 text-slate-400"
                    }`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <p className={`text-sm font-semibold truncate ${isSelected ? "text-cyan-300" : "text-slate-200"}`}>
                        {item.title}
                      </p>
                      {item.subtitle && (
                        <p className="text-xs text-slate-400 truncate mt-0.5">{item.subtitle}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 pl-3 shrink-0">
                    <span className="text-[10px] font-medium uppercase px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                      {item.category}
                    </span>
                    <ArrowRight className={`h-4 w-4 transition-transform ${isSelected ? "translate-x-0.5 text-cyan-400" : "text-slate-600"}`} />
                  </div>
                </button>
              )
            })
          )}
        </div>

        {/* Footer info bar */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-slate-800/80 bg-slate-950/40 text-[11px] text-slate-500">
          <div className="flex items-center gap-3">
            <span>Use <kbd className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[10px]">↑</kbd> <kbd className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[10px]">↓</kbd> to navigate</span>
            <span><kbd className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[10px]">↵</kbd> to select</span>
          </div>
          <span><kbd className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[10px]">ESC</kbd> to close</span>
        </div>
      </div>
    </div>
  )
}
