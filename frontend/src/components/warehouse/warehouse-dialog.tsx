"use client"

import * as React from "react"
import { Warehouse, WarehouseCreateRequest, WarehouseUpdateRequest } from "@/lib/api/warehouses"
import { WarehouseForm } from "./warehouse-form"
import { AlertCircle } from "lucide-react"

interface WarehouseDialogProps {
  isOpen: boolean
  onClose: () => void
  initialData?: Warehouse | null
  onSubmit: (data: WarehouseCreateRequest | WarehouseUpdateRequest) => Promise<void>
}

export function WarehouseDialog({ isOpen, onClose, initialData, onSubmit }: WarehouseDialogProps) {
  const [error, setError] = React.useState<string | null>(null)
  const [isLoading, setIsLoading] = React.useState(false)

  // Reset error when dialog opens/closes
  React.useEffect(() => {
    if (isOpen) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setError(null)
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleSubmit = async (data: WarehouseCreateRequest | WarehouseUpdateRequest) => {
    setError(null)
    setIsLoading(true)
    try {
      await onSubmit(data)
      onClose()
    } catch (err) {
      const e = err as Error
      setError(e.message || "An unexpected error occurred. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  const isEdit = !!initialData

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-0">
      <div 
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity" 
        onClick={onClose}
        aria-hidden="true"
      />
      
      <div className="relative bg-slate-900 rounded-xl shadow-2xl border border-slate-700 w-full max-w-2xl overflow-hidden z-10 flex flex-col max-h-[90vh]">
        <div className="px-6 py-4 border-b border-slate-800 shrink-0 bg-slate-950/50">
          <h3 className="text-lg font-semibold text-slate-100">
            {isEdit ? "Edit Warehouse" : "Add New Warehouse"}
          </h3>
          <p className="text-sm text-slate-400 mt-1">
            {isEdit 
              ? "Update the connection details for this data warehouse." 
              : "Enter the connection details for your data warehouse."}
          </p>
        </div>
        
        <div className="p-6 overflow-y-auto flex-1">
          {error && (
            <div className="mb-6 rounded-md bg-red-500/10 p-4 border border-red-500/20 flex items-start">
              <AlertCircle className="h-5 w-5 text-red-500 mr-3 shrink-0 mt-0.5" />
              <div className="text-sm text-red-400">{error}</div>
            </div>
          )}
          
          <WarehouseForm 
            initialData={initialData}
            onSubmit={handleSubmit}
            onCancel={onClose}
            isLoading={isLoading}
          />
        </div>
      </div>
    </div>
  )
}
