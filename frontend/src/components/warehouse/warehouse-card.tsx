"use client"

import * as React from "react"
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Database, Edit2, Trash2, Server, Globe, Key } from "lucide-react"
import { Warehouse } from "@/lib/api/warehouses"

interface WarehouseCardProps {
  warehouse: Warehouse
  onEdit: (warehouse: Warehouse) => void
  onDelete: (warehouse: Warehouse) => void
}

export function WarehouseCard({ warehouse, onEdit, onDelete }: WarehouseCardProps) {
  return (
    <Card className="bg-slate-900/50 border-slate-800 flex flex-col hover:bg-slate-900 transition-colors">
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-slate-800 rounded-lg">
            <Database className="h-5 w-5 text-blue-400" />
          </div>
          <div>
            <CardTitle className="text-lg font-semibold text-slate-200">
              {warehouse.name}
            </CardTitle>
            <div className="text-sm text-slate-400 mt-1">
              <span className="uppercase font-semibold text-blue-400/80 mr-2">{warehouse.db_type}</span>
            </div>
          </div>
        </div>
        <Badge variant={warehouse.is_active ? "default" : "destructive"}>
          {warehouse.is_active ? "Active" : "Inactive"}
        </Badge>
      </CardHeader>
      
      <CardContent className="mt-4 flex-1">
        {warehouse.description && (
          <p className="text-sm text-slate-400 mb-4 line-clamp-2">
            {warehouse.description}
          </p>
        )}
        
        <div className="space-y-2 text-sm text-slate-300">
          <div className="flex items-center">
            <Globe className="mr-2 h-4 w-4 text-slate-500" />
            <span className="truncate">{warehouse.host}:{warehouse.port}</span>
          </div>
          <div className="flex items-center">
            <Server className="mr-2 h-4 w-4 text-slate-500" />
            <span className="truncate">{warehouse.database_name}</span>
          </div>
          <div className="flex items-center">
            <Key className="mr-2 h-4 w-4 text-slate-500" />
            <span className="truncate">{warehouse.username}</span>
          </div>
        </div>
      </CardContent>
      
      <CardFooter className="pt-4 border-t border-slate-800/50 flex justify-end space-x-2">
        <Button 
          variant="outline" 
          size="sm" 
          onClick={() => onEdit(warehouse)}
          className="border-slate-700 bg-transparent hover:bg-slate-800 text-slate-300"
        >
          <Edit2 className="mr-2 h-3.5 w-3.5" /> Edit
        </Button>
        <Button 
          variant="destructive" 
          size="sm" 
          onClick={() => onDelete(warehouse)}
          className="bg-red-900/50 hover:bg-red-900/80 text-red-200 border border-red-800/50"
        >
          <Trash2 className="mr-2 h-3.5 w-3.5" /> Delete
        </Button>
      </CardFooter>
    </Card>
  )
}
