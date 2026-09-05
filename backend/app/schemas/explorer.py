"""
Pydantic v2 schemas for the Warehouse Explorer (Database Structure).
"""

from typing import Optional
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
