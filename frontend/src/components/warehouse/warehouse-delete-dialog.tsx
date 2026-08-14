"use client"

import * as React from "react"
import { Warehouse } from "@/lib/api/warehouses"
import { Button } from "@/components/ui/button"
import { AlertTriangle, Loader2 } from "lucide-react"

interface WarehouseDeleteDialogProps {
  isOpen: boolean
  onClose: () => void
  warehouse: Warehouse | null
  onConfirm: (id: number) => Promise<void>
}

export function WarehouseDeleteDialog({ isOpen, onClose, warehouse, onConfirm }: WarehouseDeleteDialogProps) {
  const [error, setError] = React.useState<string | null>(null)
  const [isLoading, setIsLoading] = React.useState(false)

  React.useEffect(() => {
    if (isOpen) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setError(null)
    }
  }, [isOpen])

  if (!isOpen || !warehouse) return null

  const handleConfirm = async () => {
    setError(null)
    setIsLoading(true)
    try {
      await onConfirm(warehouse.id)
      onClose()
    } catch (err) {
      const e = err as Error
      setError(e.message || "Failed to delete warehouse. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-0">
      <div 
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity" 
        onClick={onClose}
        aria-hidden="true"
      />
      
      <div className="relative bg-slate-900 rounded-xl shadow-2xl border border-red-900/30 w-full max-w-md overflow-hidden z-10">
        <div className="p-6">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-900/30 mb-4">
            <AlertTriangle className="h-6 w-6 text-red-500" aria-hidden="true" />
          </div>
          <div className="text-center">
            <h3 className="text-lg font-semibold text-slate-100 mb-2">
              Delete Warehouse
            </h3>
            <p className="text-sm text-slate-400">
              Are you sure you want to delete <span className="font-semibold text-slate-200">{warehouse.name}</span>? 
              This action cannot be undone and will remove all associated discovery history.
            </p>
          </div>

          {error && (
            <div className="mt-4 rounded-md bg-red-500/10 p-3 text-sm text-red-400 border border-red-500/20 text-center">
              {error}
            </div>
          )}
        </div>
        
        <div className="bg-slate-950/50 px-6 py-4 flex items-center justify-end space-x-3 border-t border-slate-800">
          <Button 
            type="button" 
            variant="outline" 
            onClick={onClose}
            disabled={isLoading}
            className="bg-transparent border-slate-700 text-slate-300 hover:bg-slate-800"
          >
            Cancel
          </Button>
          <Button 
            type="button" 
            variant="destructive"
            onClick={handleConfirm}
            disabled={isLoading}
            className="bg-red-600 hover:bg-red-700 text-white"
          >
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Delete Warehouse
          </Button>
        </div>
      </div>
    </div>
  )
}
