from typing import List, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class DiscoveryExecutionRequest(BaseModel):
    """
    Request payload to trigger a discovery execution.
    """
    warehouse_id: int = Field(..., gt=0, description="The ID of the warehouse to analyze")

class AgentExecutionResponse(BaseModel):
    """
    Schema representing the execution result of a single agent.
    """
    agent_name: str
    status: str
    started_at: datetime
    finished_at: datetime
    duration_ms: Optional[float] = None
    wave: int
    error: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class DiscoverySessionResponse(BaseModel):
    """
    Schema representing the overall execution result of a discovery session.
    """
    session_id: str
    warehouse_id: int
    started_at: datetime
    finished_at: datetime
    status: str
    total_duration_ms: Optional[float] = None
    agent_executions: List[AgentExecutionResponse] = []
    recommendations: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(from_attributes=True)
