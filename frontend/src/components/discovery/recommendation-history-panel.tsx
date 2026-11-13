"use client"

import * as React from "react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { History, RefreshCw, CheckCircle2, XCircle, AlertTriangle, Clock, HelpCircle, Eye, Activity, Sparkles, ShieldAlert, EyeOff } from "lucide-react"
import { automationApi, RecommendationOutcomeResponse, CurrentConditionResponse, RecommendationDecisionResponse, RecommendationExplanationResponse } from "@/lib/api/automation"

interface RecommendationHistoryPanelProps {
  warehouseId: number
  sessionId?: string
}

export function RecommendationHistoryPanel({ warehouseId, sessionId }: RecommendationHistoryPanelProps) {
  const [historyItems, setHistoryItems] = React.useState<RecommendationOutcomeResponse[]>([])
  const [isLoading, setIsLoading] = React.useState<boolean>(false)
  const [error, setError] = React.useState<string | null>(null)

  const [selectedCondition, setSelectedCondition] = React.useState<CurrentConditionResponse | null>(null)
  const [selectedDecision, setSelectedDecision] = React.useState<RecommendationDecisionResponse | null>(null)
  const [selectedExplanation, setSelectedExplanation] = React.useState<RecommendationExplanationResponse | null>(null)
  const [evaluatingId, setEvaluatingId] = React.useState<number | null>(null)

  const fetchHistory = React.useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await automationApi.getRecommendationHistory(warehouseId, sessionId)
      setHistoryItems(res.items || [])
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load recommendation outcome history."
      setError(msg)
    } finally {
      setIsLoading(false)
    }
  }, [warehouseId, sessionId])

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchHistory()
  }, [fetchHistory])

  const handleEvaluateConditionAndDecision = async (item: RecommendationOutcomeResponse) => {
    setEvaluatingId(item.id)
    setSelectedCondition(null)
    setSelectedDecision(null)
    setSelectedExplanation(null)
    try {
      const schema = (item.target?.schema as string | undefined) || "public"
      const table = (item.target?.table as string | undefined) || ""
      const column = item.target?.column as string | undefined

      const candidate = {
        recommendation_id: item.recommendation_id,
        action_type: item.action_type,
        schema,
        table,
        column,
        target: item.target,
        session_id: item.session_id || sessionId,
      }

      // Parallel query for R3 current condition, R4 decision, and R6 explanation
      const [condRes, decRes, expRes] = await Promise.all([
        automationApi.getCurrentCondition(warehouseId, item.action_type, schema, table, column, item.recommendation_id),
        automationApi.evaluateRecommendationDecision(warehouseId, candidate),
        automationApi.explainRecommendation(warehouseId, candidate),
      ])

      setSelectedCondition(condRes)
      setSelectedDecision(decRes)
      setSelectedExplanation(expRes)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to evaluate current warehouse condition and decision explanation."
      setError(msg)
    } finally {
      setEvaluatingId(null)
    }
  }

  const getOutcomeBadge = (outcome: string) => {
    switch (outcome.toUpperCase()) {
      case "ACHIEVED":
      case "VERIFIED":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-3 w-3 mr-1" />
            {outcome}
          </span>
        )
      case "NOT_ACHIEVED":
      case "VERIFICATION_FAILED":
      case "FAILED":
      case "REJECTED":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20">
            <XCircle className="h-3 w-3 mr-1" />
            {outcome}
          </span>
        )
      case "UNCERTAIN":
      case "INCONCLUSIVE":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertTriangle className="h-3 w-3 mr-1" />
            {outcome}
          </span>
        )
      case "EXECUTING":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Clock className="h-3 w-3 mr-1 animate-spin" />
            EXECUTING
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
            <HelpCircle className="h-3 w-3 mr-1" />
            {outcome}
          </span>
        )
    }
  }

  const getConditionBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case "PRESENT":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/15 text-purple-300 border border-purple-500/30">
            <Eye className="h-3.5 w-3.5 mr-1 text-purple-400" />
            PRESENT
          </span>
        )
      case "RESOLVED":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
            <CheckCircle2 className="h-3.5 w-3.5 mr-1 text-emerald-400" />
            RESOLVED
          </span>
        )
      case "UNCERTAIN":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30">
            <AlertTriangle className="h-3.5 w-3.5 mr-1 text-amber-400" />
            UNCERTAIN
          </span>
        )
      case "NOT_MEASURABLE":
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
            <HelpCircle className="h-3.5 w-3.5 mr-1 text-slate-400" />
            NOT MEASURABLE
          </span>
        )
    }
  }

  const getDecisionBadge = (decision: string) => {
    switch (decision.toUpperCase()) {
      case "PROPOSE":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/40">
            <Sparkles className="h-3.5 w-3.5 mr-1 text-indigo-400" />
            PROPOSE
          </span>
        )
      case "SUPPRESS":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
            <EyeOff className="h-3.5 w-3.5 mr-1 text-slate-400" />
            SUPPRESS
          </span>
        )
      case "REVIEW":
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40">
            <ShieldAlert className="h-3.5 w-3.5 mr-1 text-amber-400" />
            REVIEW
          </span>
        )
    }
  }

  return (
    <Card className="bg-slate-900 border-slate-800">
      <CardHeader className="border-b border-slate-800 bg-slate-950/50 pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <History className="h-5 w-5 text-indigo-400" />
            <CardTitle className="text-lg text-slate-100">
              Recommendation History & Decision Engine (R1–R4)
            </CardTitle>
          </div>
          <button
            onClick={fetchHistory}
            disabled={isLoading}
            className="p-1.5 rounded-md bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700 transition-colors disabled:opacity-50"
            title="Refresh History"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </CardHeader>
      <CardContent className="pt-6 space-y-6">
        {error && (
          <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Current Condition, R4 Decision & R6 Explanation Inspector */}
        {(selectedCondition || selectedDecision || selectedExplanation) && (
          <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
              <div className="flex items-center space-x-2">
                <Activity className="h-4 w-4 text-indigo-400" />
                <span className="text-sm font-semibold text-slate-200">
                  R4 Decision & R6 Explanation Engine
                </span>
              </div>
              <div className="flex items-center space-x-2">
                {selectedCondition && getConditionBadge(selectedCondition.condition_status)}
                {selectedDecision && getDecisionBadge(selectedDecision.decision)}
                {selectedExplanation?.lifecycle_state && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono bg-slate-800 text-indigo-300 border border-slate-700">
                    R5: {selectedExplanation.lifecycle_state}
                  </span>
                )}
              </div>
            </div>

            {/* R6 Deterministic Summary */}
            {selectedExplanation?.summary && (
              <div className="p-3 rounded bg-indigo-950/40 border border-indigo-500/30 text-xs text-indigo-200 space-y-1">
                <div className="font-semibold text-indigo-300 flex items-center space-x-1.5">
                  <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
                  <span>R6 Explanation Summary</span>
                </div>
                <p className="leading-relaxed text-slate-200">{selectedExplanation.summary}</p>
              </div>
            )}

            {selectedDecision && (
              <div className="space-y-1.5 text-xs text-slate-300">
                <div className="flex items-center space-x-2">
                  <span className="font-semibold text-slate-400">Reason Code:</span>
                  <span className="font-mono text-indigo-300">{selectedDecision.reason_code}</span>
                </div>
                <div>
                  <span className="font-semibold text-slate-400">Decision Rationale:</span>{" "}
                  <span>{selectedDecision.reason}</span>
                </div>
              </div>
            )}

            {selectedCondition && (
              <p className="text-xs text-slate-300">
                <span className="font-semibold text-slate-400">Condition Observed at Decision Time:</span> {selectedCondition.reason}
              </p>
            )}

            {/* Uncertainty Warning Box */}
            {selectedExplanation?.uncertainty && (
              <div className="p-2.5 rounded bg-amber-500/10 border border-amber-500/25 text-xs text-amber-300 flex items-start space-x-2">
                <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold">Uncertainty Disclosed:</span> [{selectedExplanation.uncertainty.status}] {selectedExplanation.uncertainty.reason}
                </div>
              </div>
            )}

            {selectedCondition && selectedCondition.evidence.length > 0 && (
              <div className="space-y-1.5 pt-2 border-t border-slate-800/80">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                  Catalog Evidence:
                </span>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {selectedCondition.evidence.map((ev, i) => (
                    <div key={i} className="p-2 rounded bg-slate-900 border border-slate-800 text-xs space-y-0.5">
                      <div className="flex justify-between text-slate-400 text-[11px]">
                        <span className="font-mono">{ev.source}.{ev.field}</span>
                        <span className="font-mono text-indigo-300">{String(ev.value ?? "None")}</span>
                      </div>
                      <div className="text-slate-300 text-[11px]">{ev.interpretation}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex justify-between items-center text-[11px] text-slate-500 pt-1">
              <span>Evaluated at: {new Date(selectedDecision?.evaluated_at || selectedCondition?.evaluated_at || selectedExplanation?.generated_at || "").toLocaleString()}</span>
              <button
                onClick={() => {
                  setSelectedCondition(null)
                  setSelectedDecision(null)
                  setSelectedExplanation(null)
                }}
                className="text-slate-400 hover:text-slate-200 underline"
              >
                Close
              </button>
            </div>
          </div>
        )}

        {isLoading && historyItems.length === 0 ? (
          <div className="text-center py-8 text-slate-400 text-sm">
            Loading recommendation history...
          </div>
        ) : historyItems.length === 0 ? (
          <div className="text-center py-8 text-slate-500 text-sm">
            No historical recommendation records found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase font-semibold">
                  <th className="py-2.5 px-3">Action</th>
                  <th className="py-2.5 px-3">Target</th>
                  <th className="py-2.5 px-3">Fingerprint</th>
                  <th className="py-2.5 px-3">Approval</th>
                  <th className="py-2.5 px-3">Execution</th>
                  <th className="py-2.5 px-3">Verification</th>
                  <th className="py-2.5 px-3">Supervisor</th>
                  <th className="py-2.5 px-3">Final Outcome</th>
                  <th className="py-2.5 px-3">R4 Decision Engine</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {historyItems.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-800/30 text-slate-300">
                    <td className="py-3 px-3 font-mono text-indigo-300">
                      {item.action_type}
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-400">
                      {item.target ? `${item.target.schema || "public"}.${item.target.table || ""}` : "—"}
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-400 text-[11px]" title={item.fingerprint || ""}>
                      {item.fingerprint ? item.fingerprint.substring(0, 8) : "—"}
                    </td>
                    <td className="py-3 px-3 font-semibold text-slate-300">
                      {item.approval_status || "PROPOSED"}
                    </td>
                    <td className="py-3 px-3 font-semibold text-slate-300">
                      {item.execution_status || "PENDING"}
                    </td>
                    <td className="py-3 px-3 font-semibold text-slate-300">
                      {item.verification_status || "PENDING"}
                    </td>
                    <td className="py-3 px-3 font-semibold text-slate-300">
                      {item.objective_status || "PENDING"}
                    </td>
                    <td className="py-3 px-3">
                      {getOutcomeBadge(item.final_outcome)}
                    </td>
                    <td className="py-3 px-3">
                      <button
                        onClick={() => handleEvaluateConditionAndDecision(item)}
                        disabled={evaluatingId === item.id}
                        className="inline-flex items-center px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors text-[11px] font-medium border border-slate-700 disabled:opacity-50"
                        title="Evaluate R4 decision engine state for candidate"
                      >
                        <Sparkles className={`h-3 w-3 mr-1 ${evaluatingId === item.id ? "animate-spin text-indigo-400" : "text-indigo-400"}`} />
                        {evaluatingId === item.id ? "Evaluating..." : "Evaluate R4"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
