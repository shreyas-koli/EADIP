"use client"

import * as React from "react"
import { AgentExecution } from "@/lib/api/discovery"
import { AgentExecutionCard } from "./agent-execution-card"

interface DiscoveryPipelineProps {
  executions?: AgentExecution[]
  isRunning: boolean
  events?: Record<string, unknown>[]
  isInitializing?: boolean
  isReplaying?: boolean
}

export function DiscoveryPipeline({ executions = [], isRunning, events = [], isInitializing = false, isReplaying = false }: DiscoveryPipelineProps) {
  // Helper to find an execution by partial name
  const getExecution = (nameStr: string) => 
    executions.find(e => e.agent_name.toLowerCase().includes(nameStr.toLowerCase()))

  return (
    <div className="relative py-8 flex flex-col items-center overflow-x-auto min-w-[900px] px-8">
      {/* Wave 1: Metadata, Statistics & Monitoring (3 parallel) */}
      <div className="relative flex justify-center gap-8 sm:gap-16 mb-16 w-full">
        <div className="z-10">
          <AgentExecutionCard 
            name="Metadata Agent" 
            execution={getExecution("metadata")}
            isActive={isRunning} 
            events={events}
            isInitializing={isInitializing}
            isReplaying={isReplaying}
          />
        </div>
        <div className="z-10">
          <AgentExecutionCard 
            name="Statistics Agent" 
            execution={getExecution("statistic")}
            isActive={isRunning} 
            events={events}
            isInitializing={isInitializing}
            isReplaying={isReplaying}
          />
        </div>
        <div className="z-10">
          <AgentExecutionCard 
            name="Monitoring Agent" 
            execution={getExecution("monitoring")}
            isActive={isRunning} 
            events={events}
            isInitializing={isInitializing}
            isReplaying={isReplaying}
          />
        </div>
      </div>

      {/* Connector: Wave 1 → Wave 2 */}
      {/* Center vertical stem down from Wave 1 */}
      <div className="absolute top-[148px] h-12 w-px bg-slate-700 hidden sm:block opacity-60"></div>
      {/* Horizontal bar splitting to Wave 2 cards */}
      <div className="absolute top-[196px] w-[340px] border-t border-slate-700 hidden sm:block opacity-50"></div>
      {/* Left drop to Security */}
      <div className="absolute top-[196px] left-[calc(50%-170px)] h-8 w-px bg-slate-700 hidden sm:block opacity-50"></div>
      {/* Right drop to Data Quality */}
      <div className="absolute top-[196px] right-[calc(50%-170px)] h-8 w-px bg-slate-700 hidden sm:block opacity-50"></div>

      {/* Wave 2: Security & Data Quality (2 parallel) */}
      <div className="relative flex justify-center gap-8 sm:gap-16 mb-16 w-full">
        <div className="z-10">
          <AgentExecutionCard 
            name="Security Agent" 
            execution={getExecution("security")}
            isActive={isRunning} 
            events={events}
            isInitializing={isInitializing}
            isReplaying={isReplaying}
          />
        </div>
        <div className="z-10">
          <AgentExecutionCard 
            name="Data Quality Agent" 
            execution={getExecution("data")}
            isActive={isRunning} 
            events={events}
            isInitializing={isInitializing}
            isReplaying={isReplaying}
          />
        </div>
      </div>

      {/* Connector: Wave 2 → Wave 3 */}
      {/* Left rise from Security */}
      <div className="absolute top-[420px] left-[calc(50%-170px)] h-8 w-px bg-slate-700 hidden sm:block opacity-50"></div>
      {/* Right rise from Data Quality */}
      <div className="absolute top-[420px] right-[calc(50%-170px)] h-8 w-px bg-slate-700 hidden sm:block opacity-50"></div>
      {/* Horizontal bar merging */}
      <div className="absolute top-[428px] w-[340px] border-b border-slate-700 hidden sm:block opacity-50"></div>
      {/* Center drop to Recommendation */}
      <div className="absolute top-[428px] h-10 w-px bg-slate-700 hidden sm:block opacity-50">
         <div className="absolute -bottom-2 -left-1.5 text-slate-500 text-xs">▼</div>
      </div>

      {/* Wave 3: Recommendation */}
      <div className="relative flex justify-center z-10 mt-4">
        <AgentExecutionCard 
          name="Recommendation Agent" 
          execution={getExecution("recommendation")}
          isActive={isRunning} 
          events={events}
          isInitializing={isInitializing}
          isReplaying={isReplaying}
        />
      </div>
    </div>
  )
}
