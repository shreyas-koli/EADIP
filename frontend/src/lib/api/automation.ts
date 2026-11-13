import { fetchApi } from "./client"

export interface ApprovalRequest {
  reason?: string
}

export interface ApprovalResponse {
  action_id: string
  session_id: string
  warehouse_id: number
  status: "APPROVED" | "REJECTED" | "PROPOSED"
  decision: "APPROVE" | "REJECT"
  approved_by: string
  approved_at: string
  executed: boolean // Always false in Phase 4!
  reason?: string
  message: string
}

export interface ActionPlan {
  action_id: string
  recommendation_type: string
  action_type: string
  status: "PROPOSED" | "APPROVED" | "REJECTED"
  automation_status: string
  target: {
    schema?: string
    table?: string
    column?: string
    [key: string]: unknown
  }
  description: string
  statement?: string
  parameters: Record<string, unknown>
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
  impact_level: string
  safety_class: "READ_ONLY" | "REVERSIBLE_WRITE" | "IRREVERSIBLE_OR_HIGH_RISK"
  preconditions: string[]
  safety_checks: string[]
  rollback_plan: {
    rollback_available: boolean
    statement?: string
    description?: string
    reason?: string
  }
  verification_plan: {
    verification_type: string
    description: string
    check_query?: string
  }
  requires_approval: boolean
  requires_verification: boolean
  is_destructive: boolean
  is_reversible: boolean
  is_executable: boolean
  executed: boolean
  verification_status?: string
  verification?: Record<string, unknown>
  reanalysis_status?: string
  reanalysis?: Record<string, unknown>
  created_at: string
  source_agent: string
  evidence: unknown[]
  approval?: {
    approval_id: number
    decision: string
    status: string
    approved_by: string
    reason?: string
    created_at?: string
  }
}

export interface ExecutionResultResponse {
  execution_id: number
  action_id: string
  session_id: string
  warehouse_id: number
  status: "COMPLETED" | "FAILED" | "EXECUTING"
  action_type: string
  started_at: string
  completed_at: string
  duration_ms: number
  executed: boolean
  message: string
  verification_status: string
  error_message?: string
}

export interface VerificationCheckDetail {
  check_id: string
  description: string
  expected: unknown
  observed: unknown
  status: "PASS" | "FAIL" | "INCONCLUSIVE"
  evidence: string
}

export interface VerificationResultResponse {
  verification_id: string
  execution_id: number
  action_id: string
  session_id: string
  warehouse_id: number
  status: "VERIFIED" | "VERIFICATION_FAILED" | "INCONCLUSIVE" | "VERIFYING"
  verified?: boolean
  action_type: string
  expected_state: Record<string, unknown>
  observed_state: Record<string, unknown>
  evidence: string[]
  checks: VerificationCheckDetail[]
  started_at: string
  completed_at: string
  duration_ms: number
  message: string
  error_message?: string
}

export interface StateComparisonDetail {
  metric: string
  before?: unknown
  after?: unknown
  status: "MATCH" | "MISMATCH" | "NOT_MEASURED"
  evidence?: string
  reason?: string
}

export interface SupervisorReanalysisResponse {
  reanalysis_id: string
  execution_id: number
  verification_id?: number
  action_id: string
  session_id: string
  warehouse_id: number
  status: "SUCCESSFUL_OUTCOME" | "UNSUCCESSFUL_OUTCOME" | "UNCERTAIN_OUTCOME" | "REANALYZING"
  objective_status: "ACHIEVED" | "NOT_ACHIEVED" | "UNCERTAIN"
  action_type: string
  before_state: Record<string, unknown>
  after_state: Record<string, unknown>
  comparisons: StateComparisonDetail[]
  findings: string[]
  conclusion: string
  follow_up_required: boolean
  follow_up_type: "NONE" | "OBSERVATION" | "ANALYSIS" | "RECOMMENDATION"
  follow_up_details?: Record<string, unknown>
  started_at: string
  completed_at: string
  duration_ms: number
  message: string
  error_message?: string
}

export interface RecommendationOutcomeResponse {
  id: number
  recommendation_id: string
  action_id: string
  session_id: number
  warehouse_id: number
  user_id?: number
  action_type: string
  target?: Record<string, unknown>
  approval_id?: number
  execution_id?: number
  verification_id?: number
  reanalysis_id?: number
  approval_status?: string
  execution_status?: string
  verification_status?: string
  reanalysis_status?: string
  objective_status?: string
  final_outcome: string
  fingerprint?: string
  created_at: string
  updated_at: string
}

export interface RecommendationHistoryListResponse {
  items: RecommendationOutcomeResponse[]
  total: number
  limit: number
  offset: number
}

export const automationApi = {
  getActions: (warehouseId: number, sessionId: string) =>
    fetchApi<ActionPlan[]>(`/warehouses/${warehouseId}/automation/sessions/${sessionId}/actions`, {
      method: "GET",
    }),

  approveAction: (warehouseId: number, sessionId: string, actionId: string, reason?: string) =>
    fetchApi<ApprovalResponse>(
      `/warehouses/${warehouseId}/automation/sessions/${sessionId}/actions/${actionId}/approve`,
      {
        method: "POST",
        body: JSON.stringify({ reason }),
      }
    ),

  rejectAction: (warehouseId: number, sessionId: string, actionId: string, reason?: string) =>
    fetchApi<ApprovalResponse>(
      `/warehouses/${warehouseId}/automation/sessions/${sessionId}/actions/${actionId}/reject`,
      {
        method: "POST",
        body: JSON.stringify({ reason }),
      }
    ),

  executeAction: (warehouseId: number, sessionId: string, actionId: string) =>
    fetchApi<ExecutionResultResponse>(
      `/warehouses/${warehouseId}/automation/sessions/${sessionId}/actions/${actionId}/execute`,
      {
        method: "POST",
      }
    ),

  verifyAction: (warehouseId: number, sessionId: string, actionId: string) =>
    fetchApi<VerificationResultResponse>(
      `/warehouses/${warehouseId}/automation/sessions/${sessionId}/actions/${actionId}/verify`,
      {
        method: "POST",
      }
    ),

  getVerificationResult: (warehouseId: number, sessionId: string, actionId: string) =>
    fetchApi<VerificationResultResponse | null>(
      `/warehouses/${warehouseId}/automation/sessions/${sessionId}/actions/${actionId}/verification`,
      {
        method: "GET",
      }
    ),

  reanalyzeAction: (warehouseId: number, sessionId: string, actionId: string) =>
    fetchApi<SupervisorReanalysisResponse>(
      `/warehouses/${warehouseId}/automation/sessions/${sessionId}/actions/${actionId}/reanalyze`,
      {
        method: "POST",
      }
    ),

  getReanalysisResult: (warehouseId: number, sessionId: string, actionId: string) =>
    fetchApi<SupervisorReanalysisResponse | null>(
      `/warehouses/${warehouseId}/automation/sessions/${sessionId}/actions/${actionId}/reanalysis`,
      {
        method: "GET",
      }
    ),

  getRecommendationHistory: (warehouseId: number, sessionId?: string, outcome?: string, limit: number = 50, offset: number = 0) => {
    const params = new URLSearchParams()
    if (sessionId) params.append("session_id", sessionId)
    if (outcome) params.append("outcome", outcome)
    params.append("limit", limit.toString())
    params.append("offset", offset.toString())
    return fetchApi<RecommendationHistoryListResponse>(
      `/warehouses/${warehouseId}/recommendation-history?${params.toString()}`,
      { method: "GET" }
    )
  },

  getCurrentCondition: (
    warehouseId: number,
    actionType: string,
    schema?: string,
    table?: string,
    column?: string,
    recommendationId?: string
  ) => {
    const params = new URLSearchParams()
    params.append("action_type", actionType)
    if (schema) params.append("schema", schema)
    if (table) params.append("table", table)
    if (column) params.append("column", column)
    if (recommendationId) params.append("recommendation_id", recommendationId)
    return fetchApi<CurrentConditionResponse>(
      `/warehouses/${warehouseId}/recommendation-history/conditions?${params.toString()}`,
      { method: "GET" }
    )
  },

  evaluateRecommendationDecision: (
    warehouseId: number,
    candidate: Record<string, unknown>
  ) =>
    fetchApi<RecommendationDecisionResponse>(
      `/warehouses/${warehouseId}/recommendations/decide`,
      {
        method: "POST",
        body: JSON.stringify(candidate),
      }
    ),

  getRecommendationExplanation: (
    warehouseId: number,
    candidate: Record<string, unknown>
  ) =>
    fetchApi<RecommendationExplanationResponse>(
      `/warehouses/${warehouseId}/recommendations/explain`,
      {
        method: "POST",
        body: JSON.stringify(candidate),
      }
    ),

  explainRecommendation: (
    warehouseId: number,
    candidate: Record<string, unknown>
  ) =>
    fetchApi<RecommendationExplanationResponse>(
      `/warehouses/${warehouseId}/recommendations/explain`,
      {
        method: "POST",
        body: JSON.stringify(candidate),
      }
    ),
}

export interface EvidenceItem {
  source: string
  field: string
  value?: unknown
  interpretation: string
}

export interface CurrentConditionResponse {
  recommendation_id?: string
  fingerprint?: string
  warehouse_id: number
  action_type: string
  target?: Record<string, unknown>
  condition_status: "PRESENT" | "RESOLVED" | "UNCERTAIN" | "NOT_MEASURABLE"
  condition_type: string
  evidence: EvidenceItem[]
  evaluated_at: string
  measurement_available: boolean
  reason: string
  historical_match?: Record<string, unknown>
}

export interface RecommendationDecisionResponse {
  recommendation_id?: string
  fingerprint?: string
  action_type: string
  target?: Record<string, unknown>
  decision: "PROPOSE" | "SUPPRESS" | "REVIEW"
  reason_code: string
  reason: string
  historical_outcome?: string
  current_condition_status?: string
  evidence: EvidenceItem[]
  evaluated_at: string
}

export interface HistoricalContextSummary {
  match_found: boolean
  fingerprint?: string
  historical_outcome?: string
  previous_action_id?: string
  previous_session_id?: number
  summary: string
}

export interface ConditionContextSummary {
  condition_status: string
  condition_type: string
  observed_reason: string
  measurement_available: boolean
  evidence: EvidenceItem[]
}

export interface UncertaintyDetail {
  uncertainty_type: string
  description: string
  status?: string
  reason?: string
}

export interface RecommendationExplanationResponse {
  recommendation_id: string
  fingerprint?: string
  action_type: string
  target?: Record<string, unknown>
  decision: "PROPOSE" | "SUPPRESS" | "REVIEW"
  decision_reason_code: string
  decision_reason: string
  lifecycle_state: string
  summary: string
  historical_context: HistoricalContextSummary
  current_condition: ConditionContextSummary
  decision_evidence: EvidenceItem[]
  lifecycle_evidence: EvidenceItem[]
  uncertainty?: UncertaintyDetail
  generated_at: string
}



