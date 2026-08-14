"use client"

import * as React from "react"
import { AgentExecution } from "@/lib/api/discovery"
import { AgentExecutionCard } from "./agent-execution-card"

interface DiscoveryPipelineProps {
  executions?: AgentExecution[]
  isRunning: boolean
}

export function DiscoveryPipeline({ executions = [], isRunning }: DiscoveryPipelineProps) {
  // Helper to find an execution by partial name
  const getExecution = (nameStr: string) => 
    executions.find(e => e.agent_name.toLowerCase().includes(nameStr.toLowerCase()))

  return (
    <div className="relative py-8 flex flex-col items-center">
      {/* Wave 1: Metadata & Statistics */}
      <div className="relative flex justify-center space-x-12 sm:space-x-32 mb-12">
        <AgentExecutionCard 
          name="Metadata Agent" 
          execution={getExecution("metadata")}
          isActive={isRunning} 
        />
        <AgentExecutionCard 
          name="Statistics Agent" 
          execution={getExecution("statistic")}
          isActive={isRunning} 
        />
      </div>

      {/* Downward Connector to Wave 2 */}
      <div className="absolute top-[108px] h-12 w-px bg-slate-700 hidden sm:block"></div>

      {/* Wave 2: Security & Data Quality */}
      <div className="relative flex justify-center space-x-12 sm:space-x-32 mb-12">
        {/* Horizontal line connecting from Wave 1 center */}
        <div className="absolute -top-12 h-12 w-full flex justify-center hidden sm:flex">
           <div className="w-[368px] border-t border-x border-slate-700 rounded-t-xl opacity-50"></div>
        </div>

        <AgentExecutionCard 
          name="Security Agent" 
          execution={getExecution("security")}
          isActive={isRunning} 
        />
        <AgentExecutionCard 
          name="Data Quality Agent" 
          execution={getExecution("data")}
          isActive={isRunning} 
        />
      </div>

      {/* Downward Connector to Wave 3 */}
      <div className="absolute top-[260px] h-12 w-full flex justify-center hidden sm:flex">
         <div className="w-[368px] border-b border-x border-slate-700 rounded-b-xl opacity-50"></div>
      </div>
      <div className="absolute top-[308px] h-6 w-px bg-slate-700 hidden sm:block"></div>

      {/* Wave 3: Recommendation */}
      <div className="relative flex justify-center">
        <AgentExecutionCard 
          name="Recommendation Agent" 
          execution={getExecution("recommendation")}
          isActive={isRunning} 
        />
      </div>
    </div>
  )
}
