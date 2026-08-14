"use client"

import * as React from "react"
import { PageContainer } from "@/components/layout/page-container"
import { EmptyState } from "@/components/ui/empty-state"
import { LoadingState } from "@/components/ui/loading-state"
import { Button } from "@/components/ui/button"
import { Database, Plus, AlertCircle } from "lucide-react"

import { warehousesApi, Warehouse, WarehouseCreateRequest, WarehouseUpdateRequest } from "@/lib/api/warehouses"
import { WarehouseCard } from "@/components/warehouse/warehouse-card"
import { WarehouseDialog } from "@/components/warehouse/warehouse-dialog"
import { WarehouseDeleteDialog } from "@/components/warehouse/warehouse-delete-dialog"

export default function WarehousesPage() {
  const [warehouses, setWarehouses] = React.useState<Warehouse[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  
  const [isFormOpen, setIsFormOpen] = React.useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = React.useState(false)
  const [selectedWarehouse, setSelectedWarehouse] = React.useState<Warehouse | null>(null)

  React.useEffect(() => {
    let mounted = true
    const fetchWarehouses = async () => {
      try {
        if (mounted) setIsLoading(true)
        const data = await warehousesApi.list()
        if (mounted) {
          setWarehouses(data.sort((a, b) => a.name.localeCompare(b.name)))
          setError(null)
        }
      } catch (err) {
        if (mounted) {
          const e = err as Error
          setError(e.message || "Failed to load warehouses.")
        }
      } finally {
        if (mounted) setIsLoading(false)
      }
    }
    fetchWarehouses()
    return () => { mounted = false }
  }, [])

  const handleAddClick = () => {
    setSelectedWarehouse(null)
    setIsFormOpen(true)
  }

  const handleEditClick = (warehouse: Warehouse) => {
    setSelectedWarehouse(warehouse)
    setIsFormOpen(true)
  }

  const handleDeleteClick = (warehouse: Warehouse) => {
    setSelectedWarehouse(warehouse)
    setIsDeleteOpen(true)
  }

  const refreshWarehouses = async () => {
    try {
      const data = await warehousesApi.list()
      setWarehouses(data.sort((a, b) => a.name.localeCompare(b.name)))
      setError(null)
    } catch (err) {
      const e = err as Error
      setError(e.message || "Failed to load warehouses.")
    }
  }

  const handleFormSubmit = async (data: WarehouseCreateRequest | WarehouseUpdateRequest) => {
    if (selectedWarehouse) {
      await warehousesApi.update(selectedWarehouse.id, data as WarehouseUpdateRequest)
    } else {
      await warehousesApi.create(data as WarehouseCreateRequest)
    }
    await refreshWarehouses()
  }

  const handleDeleteConfirm = async (id: number) => {
    await warehousesApi.delete(id)
    await refreshWarehouses()
  }

  if (isLoading && warehouses.length === 0) {
    return (
      <PageContainer title="Warehouses">
        <div className="flex h-[600px] items-center justify-center">
          <LoadingState message="Loading warehouses..." />
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer title="Warehouses">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Data Warehouses</h2>
          <p className="text-slate-400">Manage your connected databases and data sources.</p>
        </div>
        <Button onClick={handleAddClick} className="bg-blue-600 hover:bg-blue-700 text-white w-full sm:w-auto">
          <Plus className="mr-2 h-4 w-4" /> Add Warehouse
        </Button>
      </div>

      {error ? (
        <EmptyState
          icon={AlertCircle}
          title="Failed to load warehouses"
          description={error}
          action={<Button onClick={refreshWarehouses} variant="outline">Retry</Button>}
        />
      ) : warehouses.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No warehouses configured"
          description="Connect your first data warehouse to begin discovery and analysis."
          action={
            <Button onClick={handleAddClick}>
              <Plus className="mr-2 h-4 w-4" /> Add Warehouse
            </Button>
          }
        />
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {warehouses.map((w) => (
            <WarehouseCard 
              key={w.id} 
              warehouse={w} 
              onEdit={handleEditClick}
              onDelete={handleDeleteClick}
            />
          ))}
        </div>
      )}

      <WarehouseDialog 
        isOpen={isFormOpen}
        onClose={() => setIsFormOpen(false)}
        initialData={selectedWarehouse}
        onSubmit={handleFormSubmit}
      />

      <WarehouseDeleteDialog
        isOpen={isDeleteOpen}
        onClose={() => setIsDeleteOpen(false)}
        warehouse={selectedWarehouse}
        onConfirm={handleDeleteConfirm}
      />
    </PageContainer>
  )
}
