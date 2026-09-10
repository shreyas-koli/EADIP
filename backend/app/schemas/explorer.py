"""
Pydantic v2 schemas for the Warehouse Explorer (Database Structure + Row Data).
"""

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class SchemaResponse(BaseModel):
    name: str = Field(..., description="Schema name")
    
    model_config = ConfigDict(from_attributes=True)


class TableResponse(BaseModel):
    name: str = Field(..., description="Table name")
    schema_name: str = Field(..., description="Schema name")
    estimated_row_count: int = Field(0, description="Estimated number of rows (from pg_class.reltuples)")
    
    model_config = ConfigDict(from_attributes=True)


class ColumnResponse(BaseModel):
    name: str = Field(..., description="Column name")
    data_type: str = Field(..., description="Data type of the column")
    nullable: bool = Field(True, description="Whether the column can be NULL")
    position: int = Field(..., description="Ordinal position of the column")
    is_primary_key: bool = Field(False, description="Whether this column is part of the primary key")
    foreign_key: Optional[dict] = Field(None, description="Foreign key information if any (referred_table, referred_schema)")
    
    model_config = ConfigDict(from_attributes=True)


class RowDataResponse(BaseModel):
    """Paginated row-data response for the table data viewer."""
    columns: list[str] = Field(..., description="Ordered list of column names")
    rows: list[list[Any]] = Field(..., description="Row data as a list of value arrays")
    limit: int = Field(..., description="Page size used")
    offset: int = Field(..., description="Offset used")
    returned_rows: int = Field(..., description="Number of rows in this response")
    total_rows: int = Field(..., description="Estimated total rows in the table (from pg_class.reltuples)")
    is_estimated_total: bool = Field(True, description="Whether total_rows is an estimate")


class QueryRequest(BaseModel):
    """Request body for the SQL Console execution endpoint."""
    sql: str = Field(
        ...,
        min_length=1,
        max_length=50_000,
        description="A single read-only SQL statement to execute against the warehouse.",
    )


class QueryResponse(BaseModel):
    """Response for a SQL Console query."""
    columns: list[str] = Field(..., description="Ordered list of column names")
    rows: list[list[Any]] = Field(..., description="Row data as a list of value arrays")
    returned_rows: int = Field(..., description="Number of rows included in this response")
    execution_time_ms: float = Field(..., description="Server-side query execution time in milliseconds")
    truncated: bool = Field(False, description="True if results were capped at the server-side row limit")
