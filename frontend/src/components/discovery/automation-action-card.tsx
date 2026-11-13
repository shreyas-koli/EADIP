"use client"

import * as React from "react"
import { ActionPlan, VerificationResultResponse, VerificationCheckDetail, SupervisorReanalysisResponse, automationApi } from "@/lib/api/automation"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Shield,
  Clock,
  Terminal,
  ChevronDown,
  ChevronUp,
  Loader2,
  FileCode,
  ShieldCheck,
  RotateCcw,
  CheckSquare,
  Activity,
} from "lucide-react"

interface AutomationActionCardProps {
  action: ActionPlan
  warehouseId: number
  sessionId: string
  onActionUpdated?: (updatedActionId: string, status: "APPROVED" | "REJECTED") => void
}

export function AutomationActionCard({
  action,
  warehouseId,
  sessionId,
  onActionUpdated,
}: AutomationActionCardProps) {
  const [currentStatus, setCurrentStatus] = React.useState<"PROPOSED" | "APPROVED" | "REJECTED" | "EXECUTING" | "COMPLETED" | "FAILED">(
    (action.status as "PROPOSED" | "APPROVED" | "REJECTED" | "EXECUTING" | "COMPLETED" | "FAILED") || "PROPOSED"
  )
  const [executed, setExecuted] = React.useState<boolean>(action.executed || false)
  const [isApproving, setIsApproving] = React.useState(false)
  const [isRejecting, setIsRejecting] = React.useState(false)
  const [isExecuting, setIsExecuting] = React.useState(false)
  const [showHighRiskModal, setShowHighRiskModal] = React.useState(false)
  const [showExecuteModal, setShowExecuteModal] = React.useState(false)
  const [rejectReason, setRejectReason] = React.useState("")
  const [showRejectForm, setShowRejectForm] = React.useState(false)
  const [expandedDetails, setExpandedDetails] = React.useState(false)
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null)

  const [verificationStatus, setVerificationStatus] = React.useState<
    "PENDING" | "VERIFYING" | "VERIFIED" | "VERIFICATION_FAILED" | "INCONCLUSIVE"
  >(
    (action.verification_status as "PENDING" | "VERIFYING" | "VERIFIED" | "VERIFICATION_FAILED" | "INCONCLUSIVE") || "PENDING"
  )
  const [verificationResult, setVerificationResult] = React.useState<VerificationResultResponse | null>(null)
  const [isVerifying, setIsVerifying] = React.useState(false)

  const [reanalysisStatus, setReanalysisStatus] = React.useState<
    "PENDING" | "REANALYZING" | "SUCCESSFUL_OUTCOME" | "UNSUCCESSFUL_OUTCOME" | "UNCERTAIN_OUTCOME"
  >(
    (action.reanalysis_status as "PENDING" | "REANALYZING" | "SUCCESSFUL_OUTCOME" | "UNSUCCESSFUL_OUTCOME" | "UNCERTAIN_OUTCOME") || "PENDING"
  )
  const [reanalysisResult, setReanalysisResult] = React.useState<SupervisorReanalysisResponse | null>(null)
  const [isReanalyzing, setIsReanalyzing] = React.useState(false)

  const handleVerifyClick = async () => {
    setIsVerifying(true)
    setErrorMessage(null)
    setVerificationStatus("VERIFYING")

    try {
      const res = await automationApi.verifyAction(warehouseId, sessionId, action.action_id)
      setVerificationResult(res)
      setVerificationStatus(res.status as "PENDING" | "VERIFYING" | "VERIFIED" | "VERIFICATION_FAILED" | "INCONCLUSIVE")
    } catch (err: unknown) {
      setVerificationStatus("INCONCLUSIVE")
      const msg = err instanceof Error ? err.message : "Verification failed."
      setErrorMessage(msg)
    } finally {
      setIsVerifying(false)
    }
  }

  const handleReanalyzeClick = async () => {
    setIsReanalyzing(true)
    setErrorMessage(null)
    setReanalysisStatus("REANALYZING")

    try {
      const res = await automationApi.reanalyzeAction(warehouseId, sessionId, action.action_id)
      setReanalysisResult(res)
      setReanalysisStatus(res.status as "PENDING" | "REANALYZING" | "SUCCESSFUL_OUTCOME" | "UNSUCCESSFUL_OUTCOME" | "UNCERTAIN_OUTCOME")
    } catch (err: unknown) {
      setReanalysisStatus("UNCERTAIN_OUTCOME")
      const msg = err instanceof Error ? err.message : "Re-analysis failed."
      setErrorMessage(msg)
    } finally {
      setIsReanalyzing(false)
    }
  }

  const isHighRisk = action.risk_level === "HIGH" || action.risk_level === "CRITICAL"

  const handleExecuteClick = () => {
    setErrorMessage(null)
    setShowExecuteModal(true)
  }

  const executeActionNow = async () => {
    setIsExecuting(true)
    setShowExecuteModal(false)
    setErrorMessage(null)
    setCurrentStatus("EXECUTING")

    try {
      const res = await automationApi.executeAction(warehouseId, sessionId, action.action_id)
      if (res.status === "COMPLETED") {
        setCurrentStatus("COMPLETED")
        setExecuted(true)
        if (onActionUpdated) {
          onActionUpdated(action.action_id, "APPROVED")
        }
      } else {
        setCurrentStatus("FAILED")
        setErrorMessage(res.error_message || "Action execution failed on target warehouse.")
      }
    } catch (err: unknown) {
      setCurrentStatus("FAILED")
      const msg = err instanceof Error ? err.message : "Action execution failed."
      setErrorMessage(msg)
    } finally {
      setIsExecuting(false)
    }
  }

  const handleApproveClick = () => {
    setErrorMessage(null)
    if (isHighRisk) {
      setShowHighRiskModal(true)
    } else {
      executeApprove()
    }
  }

  const executeApprove = async () => {
    setIsApproving(true)
    setShowHighRiskModal(false)
    setErrorMessage(null)

    try {
      await automationApi.approveAction(warehouseId, sessionId, action.action_id)
      setCurrentStatus("APPROVED")
      if (onActionUpdated) {
        onActionUpdated(action.action_id, "APPROVED")
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record action approval."
      setErrorMessage(msg)
    } finally {
      setIsApproving(false)
    }
  }

  const handleRejectSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsRejecting(true)
    setErrorMessage(null)

    try {
      await automationApi.rejectAction(warehouseId, sessionId, action.action_id, rejectReason)
      setCurrentStatus("REJECTED")
      setShowRejectForm(false)
      if (onActionUpdated) {
        onActionUpdated(action.action_id, "REJECTED")
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record action rejection."
      setErrorMessage(msg)
    } finally {
      setIsRejecting(false)
    }
  }

  const getRiskBadge = (risk: string) => {
    switch (risk?.toUpperCase()) {
      case "CRITICAL":
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-purple-950/60 text-purple-300 border border-purple-800/60 flex items-center gap-1"><Shield className="w-3 h-3 text-purple-400" /> CRITICAL RISK</span>
      case "HIGH":
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-red-950/60 text-red-300 border border-red-800/60 flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-red-400" /> HIGH RISK</span>
      case "MEDIUM":
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-amber-950/60 text-amber-300 border border-amber-800/60 flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-amber-400" /> MEDIUM RISK</span>
      case "LOW":
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-emerald-950/60 text-emerald-300 border border-emerald-800/60 flex items-center gap-1"><ShieldCheck className="w-3 h-3 text-emerald-400" /> LOW RISK</span>
      default:
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-slate-800 text-slate-300">{risk}</span>
    }
  }

  const getSafetyBadge = (safety: string) => {
    switch (safety?.toUpperCase()) {
      case "READ_ONLY":
        return <span className="px-2 py-0.5 text-xs font-mono rounded bg-emerald-950/40 text-emerald-400 border border-emerald-900/40">READ ONLY</span>
      case "REVERSIBLE_WRITE":
        return <span className="px-2 py-0.5 text-xs font-mono rounded bg-sky-950/40 text-sky-400 border border-sky-900/40">REVERSIBLE WRITE</span>
      case "IRREVERSIBLE_OR_HIGH_RISK":
        return <span className="px-2 py-0.5 text-xs font-mono rounded bg-red-950/40 text-red-400 border border-red-900/40">IRREVERSIBLE</span>
      default:
        return <span className="px-2 py-0.5 text-xs font-mono rounded bg-slate-800 text-slate-300">{safety}</span>
    }
  }

  return (
    <Card className={`bg-slate-900/90 border transition-all shadow-lg ${
      currentStatus === "APPROVED" ? "border-emerald-500/50 bg-slate-900/95" :
      currentStatus === "REJECTED" ? "border-slate-700/60 opacity-75" :
      isHighRisk ? "border-amber-500/30 hover:border-amber-500/50" : "border-slate-800 hover:border-slate-700"
    }`}>
      <CardHeader className="pb-3 border-b border-slate-800/80">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-mono uppercase text-sky-400 font-semibold bg-sky-950/60 px-2 py-0.5 rounded border border-sky-900/40">
                {action.action_type}
              </span>
              {getRiskBadge(action.risk_level)}
              {getSafetyBadge(action.safety_class)}
            </div>
            <CardTitle className="text-base font-medium text-slate-200 pt-1">
              {action.description || action.recommendation_type}
            </CardTitle>
          </div>

          <div className="flex items-center space-x-2">
            {currentStatus === "APPROVED" && !executed && (
              <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-700/50 shadow-sm">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                <span>APPROVED — Ready for Execution</span>
              </span>
            )}

            {currentStatus === "EXECUTING" && (
              <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-sky-950/80 text-sky-300 border border-sky-700/50 shadow-sm">
                <Loader2 className="w-3.5 h-3.5 text-sky-400 animate-spin" />
                <span>EXECUTING — In Progress</span>
              </span>
            )}

            {(currentStatus === "COMPLETED" || executed) && (
              <>
                {verificationStatus === "VERIFIED" && (
                  <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-700/50 shadow-sm">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                    <span>VERIFIED — Catalog Evidence Confirmed</span>
                  </span>
                )}
                {verificationStatus === "VERIFICATION_FAILED" && (
                  <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-red-950/80 text-red-300 border border-red-700/50 shadow-sm">
                    <XCircle className="w-3.5 h-3.5 text-red-400" />
                    <span>VERIFICATION FAILED — Expected State Absent</span>
                  </span>
                )}
                {verificationStatus === "INCONCLUSIVE" && (
                  <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-950/80 text-amber-300 border border-amber-700/50 shadow-sm">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                    <span>INCONCLUSIVE — Catalog Evidence Incomplete</span>
                  </span>
                )}
                {verificationStatus === "VERIFYING" && (
                  <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-950/80 text-blue-300 border border-blue-700/50 shadow-sm">
                    <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />
                    <span>VERIFYING — Analyzing Catalog State...</span>
                  </span>
                )}
                {verificationStatus === "PENDING" && (
                  <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-950/80 text-indigo-300 border border-indigo-700/50 shadow-sm">
                    <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400" />
                    <span>COMPLETED — Verification Pending</span>
                  </span>
                )}

                {/* Supervisor Re-analysis Badges */}
                {reanalysisStatus === "SUCCESSFUL_OUTCOME" && (
                  <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-950/90 text-emerald-300 border border-emerald-600/60 shadow-sm">
                    <Activity className="w-3.5 h-3.5 text-emerald-400" />
                    <span>SUPERVISOR — Objective Achieved</span>
                  </span>
                )}
                {reanalysisStatus === "UNSUCCESSFUL_OUTCOME" && (
                  <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-red-950/90 text-red-300 border border-red-600/60 shadow-sm">
                    <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                    <span>SUPERVISOR — Objective Not Achieved</span>
                  </span>
                )}
                {reanalysisStatus === "UNCERTAIN_OUTCOME" && (
                  <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-950/90 text-amber-300 border border-amber-600/60 shadow-sm">
                    <Clock className="w-3.5 h-3.5 text-amber-400" />
                    <span>SUPERVISOR — Outcome Uncertain</span>
                  </span>
                )}
                {reanalysisStatus === "REANALYZING" && (
                  <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-purple-950/80 text-purple-300 border border-purple-700/50 shadow-sm">
                    <Loader2 className="w-3.5 h-3.5 text-purple-400 animate-spin" />
                    <span>SUPERVISOR — Re-analyzing Outcome...</span>
                  </span>
                )}
              </>
            )}

            {currentStatus === "FAILED" && (
              <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-red-950/80 text-red-300 border border-red-700/50 shadow-sm">
                <XCircle className="w-3.5 h-3.5 text-red-400" />
                <span>FAILED — Execution Error</span>
              </span>
            )}

            {currentStatus === "REJECTED" && (
              <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700 shadow-sm">
                <XCircle className="w-3.5 h-3.5 text-slate-400" />
                <span>REJECTED — Not Executed</span>
              </span>
            )}

            {currentStatus === "PROPOSED" && (
              <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-950/60 text-amber-300 border border-amber-800/40">
                <Clock className="w-3.5 h-3.5 text-amber-400" />
                <span>PROPOSED — Approval Required</span>
              </span>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-4 space-y-4">
        {/* Target Details */}
        {action.target && (action.target.schema || action.target.table) && (
          <div className="flex items-center space-x-1 text-xs font-mono bg-slate-950 px-2.5 py-1.5 rounded-md border border-slate-800/80 self-start">
            <span className="text-slate-400">Target:</span>
            <span className="text-slate-300 ml-1">{action.target.schema || "public"}</span>
            <span className="text-slate-600">.</span>
            <span className="text-sky-400 font-semibold">{action.target.table}</span>
            {action.target.column && (
              <>
                <span className="text-slate-600">.</span>
                <span className="text-purple-400 font-semibold">{action.target.column}</span>
              </>
            )}
          </div>
        )}

        {/* Statement Preview */}
        {action.statement && (
          <div className="space-y-1.5">
            <div className="flex items-center text-xs font-semibold text-slate-400">
              <FileCode className="w-3.5 h-3.5 mr-1 text-sky-400" />
              Proposed Action Statement
            </div>
            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 font-mono text-xs text-sky-300 overflow-x-auto">
              <code>{action.statement}</code>
            </div>
          </div>
        )}

        {/* Expandable Technical Details */}
        <div>
          <button
            onClick={() => setExpandedDetails(!expandedDetails)}
            className="flex items-center text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors"
          >
            {expandedDetails ? <ChevronUp className="w-3.5 h-3.5 mr-1" /> : <ChevronDown className="w-3.5 h-3.5 mr-1" />}
            {expandedDetails ? "Hide Technical Details" : "View Preconditions, Safety Checks & Rollback Plan"}
          </button>

          {expandedDetails && (
            <div className="mt-3 space-y-3 pt-3 border-t border-slate-800 text-xs">
              {/* Preconditions */}
              {action.preconditions && action.preconditions.length > 0 && (
                <div className="space-y-1">
                  <span className="font-semibold text-slate-300 flex items-center">
                    <CheckSquare className="w-3 h-3 mr-1 text-emerald-400" /> Preconditions
                  </span>
                  <ul className="list-disc list-inside text-slate-400 space-y-0.5 font-mono">
                    {action.preconditions.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Safety Checks */}
              {action.safety_checks && action.safety_checks.length > 0 && (
                <div className="space-y-1">
                  <span className="font-semibold text-slate-300 flex items-center">
                    <ShieldCheck className="w-3 h-3 mr-1 text-sky-400" /> Safety Checks
                  </span>
                  <ul className="list-disc list-inside text-slate-400 space-y-0.5 font-mono">
                    {action.safety_checks.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Rollback Plan */}
              {action.rollback_plan && (
                <div className="space-y-1">
                  <span className="font-semibold text-slate-300 flex items-center">
                    <RotateCcw className="w-3 h-3 mr-1 text-purple-400" /> Rollback Plan
                  </span>
                  <p className="text-slate-400 font-mono">
                    {action.rollback_plan.description || "No description."}
                    {action.rollback_plan.statement && (
                      <span className="block mt-0.5 text-purple-300 font-mono bg-slate-950 p-1.5 rounded border border-slate-800">
                        {action.rollback_plan.statement}
                      </span>
                    )}
                  </p>
                </div>
              )}

              {/* Verification Plan */}
              {action.verification_plan && (
                <div className="space-y-1">
                  <span className="font-semibold text-slate-300 flex items-center">
                    <Terminal className="w-3 h-3 mr-1 text-amber-400" /> Verification Plan
                  </span>
                  <p className="text-slate-400 font-mono">
                    {action.verification_plan.description}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Error Notification */}
        {errorMessage && (
          <div className="p-2.5 rounded bg-red-950/40 border border-red-800/60 text-red-300 text-xs flex items-start space-x-2">
            <XCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Rejection Form */}
        {showRejectForm && (
          <form onSubmit={handleRejectSubmit} className="pt-2 space-y-2 border-t border-slate-800">
            <label className="block text-xs font-medium text-slate-300">
              Reason for Rejection (Optional)
            </label>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Explain why this action plan is being rejected..."
              maxLength={1000}
              className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-xs text-slate-200 focus:outline-none focus:border-red-500"
              rows={2}
            />
            <div className="flex items-center justify-end space-x-2">
              <button
                type="button"
                onClick={() => setShowRejectForm(false)}
                className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isRejecting}
                className="px-3 py-1.5 text-xs font-semibold bg-red-600 hover:bg-red-500 text-white rounded flex items-center space-x-1"
              >
                {isRejecting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <XCircle className="w-3.5 h-3.5" />}
                <span>Confirm Rejection</span>
              </button>
            </div>
          </form>
        )}

        {/* Proposed -> Approval / Rejection Action Buttons */}
        {currentStatus === "PROPOSED" && !showRejectForm && (
          <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-800/80">
            <button
              onClick={() => setShowRejectForm(true)}
              disabled={isApproving || isRejecting}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition-colors flex items-center space-x-1.5"
            >
              <XCircle className="w-4 h-4 text-slate-400" />
              <span>Reject Action</span>
            </button>

            <button
              onClick={handleApproveClick}
              disabled={isApproving || isRejecting}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white shadow-md hover:shadow-emerald-900/30 transition-all flex items-center space-x-1.5"
            >
              {isApproving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle2 className="w-4 h-4" />
              )}
              <span>Approve Action Plan</span>
            </button>
          </div>
        )}

        {/* Approved -> Execute Action Button */}
        {currentStatus === "APPROVED" && !executed && (
          <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-800/80">
            <button
              onClick={handleExecuteClick}
              disabled={isExecuting}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-sky-600 hover:bg-sky-500 text-white shadow-md hover:shadow-sky-900/30 transition-all flex items-center space-x-1.5"
            >
              {isExecuting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Terminal className="w-4 h-4 text-sky-200" />
              )}
              <span>Execute Action Plan</span>
            </button>
          </div>
        )}

        {/* Completed -> Verify Action Button */}
        {(currentStatus === "COMPLETED" || executed) && (
          <div className="flex flex-col space-y-3 pt-3 border-t border-slate-800/80">
            {verificationResult && verificationResult.checks && verificationResult.checks.length > 0 && (
              <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs space-y-2">
                <div className="font-semibold text-slate-300 flex items-center justify-between">
                  <span className="flex items-center">
                    <ShieldCheck className="w-3.5 h-3.5 mr-1 text-emerald-400" />
                    Catalog Verification Evidence
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">{verificationResult.verification_id}</span>
                </div>
                <div className="space-y-1">
                  {verificationResult.checks.map((c: VerificationCheckDetail, idx: number) => (
                    <div key={idx} className="flex items-start justify-between bg-slate-900/80 p-2 rounded border border-slate-800 font-mono">
                      <div>
                        <span className="text-slate-300 font-semibold">{c.description}</span>
                        <p className="text-slate-400 text-[11px] mt-0.5">{c.evidence}</p>
                      </div>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        c.status === "PASS" ? "bg-emerald-950 text-emerald-300 border border-emerald-800" :
                        c.status === "FAIL" ? "bg-red-950 text-red-300 border border-red-800" :
                        "bg-amber-950 text-amber-300 border border-amber-800"
                      }`}>
                        {c.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Supervisor Re-analysis Assessment Panel */}
            {reanalysisResult && (
              <div className="p-3 bg-purple-950/40 rounded-lg border border-purple-800/60 text-xs space-y-2">
                <div className="font-semibold text-purple-200 flex items-center justify-between">
                  <span className="flex items-center">
                    <Activity className="w-3.5 h-3.5 mr-1 text-purple-400" />
                    Supervisor Post-Execution Assessment
                  </span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    reanalysisResult.objective_status === "ACHIEVED" ? "bg-emerald-950 text-emerald-300 border border-emerald-700" :
                    reanalysisResult.objective_status === "NOT_ACHIEVED" ? "bg-red-950 text-red-300 border border-red-700" :
                    "bg-amber-950 text-amber-300 border border-amber-700"
                  }`}>
                    OBJECTIVE {reanalysisResult.objective_status}
                  </span>
                </div>
                <p className="text-slate-300 text-xs leading-relaxed">{reanalysisResult.conclusion}</p>
                {reanalysisResult.findings && reanalysisResult.findings.length > 0 && (
                  <ul className="list-disc list-inside text-slate-400 text-[11px] space-y-0.5">
                    {reanalysisResult.findings.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                )}
                {reanalysisResult.follow_up_required && reanalysisResult.follow_up_details && (
                  <div className="p-2 bg-slate-950 rounded border border-amber-800/60 text-amber-300 text-[11px] flex items-start space-x-1.5 mt-1">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold">Follow-Up Recommended ({reanalysisResult.follow_up_type}):</span>
                      <p className="text-slate-400">{String(reanalysisResult.follow_up_details.reason || reanalysisResult.follow_up_details.message)}</p>
                      <span className="inline-block mt-1 text-[10px] text-purple-300 bg-purple-950 px-2 py-0.5 rounded font-mono border border-purple-800">
                        Follow-up action proposed in PROPOSED state — Requires human approval
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="flex items-center justify-end space-x-3">
              <button
                onClick={handleVerifyClick}
                disabled={isVerifying}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white shadow-md hover:shadow-indigo-900/30 transition-all flex items-center space-x-1.5"
              >
                {isVerifying ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <ShieldCheck className="w-4 h-4 text-indigo-200" />
                )}
                <span>Verify Action Outcome</span>
              </button>

              <button
                onClick={handleReanalyzeClick}
                disabled={isReanalyzing}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-purple-600 hover:bg-purple-500 text-white shadow-md hover:shadow-purple-900/30 transition-all flex items-center space-x-1.5"
              >
                {isReanalyzing ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Activity className="w-4 h-4 text-purple-200" />
                )}
                <span>Re-analyze Outcome</span>
              </button>
            </div>
          </div>
        )}
      </CardContent>

      {/* High-Risk Confirmation Modal */}
      {showHighRiskModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-amber-500/50 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center space-x-3 text-amber-400">
              <AlertTriangle className="w-6 h-6 shrink-0" />
              <h3 className="text-lg font-bold text-slate-100">Approve High-Risk Action?</h3>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              This proposed action <strong className="text-amber-300">({action.action_type})</strong> on table{" "}
              <code className="text-sky-300 font-mono">{action.target?.table}</code> is classified as{" "}
              <strong className="text-red-400 uppercase">{action.risk_level} RISK</strong>.
            </p>

            <div className="p-3 bg-slate-950 rounded border border-slate-800 text-xs text-slate-400 font-mono">
              {action.statement || action.description}
            </div>

            <p className="text-xs text-slate-400 italic">
              Note: Approving this action authorizes it for the controlled execution phase.
            </p>

            <div className="flex items-center justify-end space-x-3 pt-2">
              <button
                onClick={() => setShowHighRiskModal(false)}
                className="px-4 py-2 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={executeApprove}
                className="px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg flex items-center space-x-1"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>Confirm Approval</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Execute Confirmation Modal */}
      {showExecuteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-sky-500/50 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center space-x-3 text-sky-400">
              <Terminal className="w-6 h-6 shrink-0" />
              <h3 className="text-lg font-bold text-slate-100">Execute Action Plan?</h3>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              This action has been approved. Executing it will <strong className="text-sky-300">modify the connected data warehouse</strong>.
            </p>

            <div className="space-y-1">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider font-bold">Action & Target</div>
              <div className="p-3 bg-slate-950 rounded border border-slate-800 text-xs text-sky-300 font-mono">
                {action.statement || `${action.action_type} on ${action.target?.table}`}
              </div>
            </div>

            <p className="text-xs text-slate-400 italic">
              Phase 5 Controlled Execution: Operation will execute with statement timeouts and strict pre-execution safety re-validation.
            </p>

            <div className="flex items-center justify-end space-x-3 pt-2">
              <button
                onClick={() => setShowExecuteModal(false)}
                className="px-4 py-2 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={executeActionNow}
                disabled={isExecuting}
                className="px-4 py-2 text-xs font-semibold text-white bg-sky-600 hover:bg-sky-500 rounded-lg flex items-center space-x-1.5 shadow-md shadow-sky-950"
              >
                {isExecuting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Terminal className="w-4 h-4" />}
                <span>Confirm & Execute</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </Card>
  )
}
