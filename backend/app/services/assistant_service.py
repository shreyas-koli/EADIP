from sqlalchemy.engine import Engine
from fastapi import HTTPException
from app.core.config import settings
from app.warehouse.explorer import ExplorerService
from app.schemas.assistant import AssistantRequest, AssistantResponse
from app.ai.factory import ProviderFactory
from app.ai.provider import UnsupportedAIProviderError

def _build_context_prompt(engine: Engine, schema_name: str | None, table_name: str | None) -> str:
    """Build a string describing the database schema for the LLM context."""
    context_lines = []
    
    try:
        # Get all schemas
        schemas = ExplorerService.get_schemas(engine)
        schema_names = [s["name"] for s in schemas]
        context_lines.append(f"Available schemas: {', '.join(schema_names)}")
        
        # Determine which schemas to describe in detail
        schemas_to_describe = [schema_name] if schema_name else schema_names
        
        for s_name in schemas_to_describe:
            tables = ExplorerService.get_tables(engine, s_name)
            if not tables:
                continue
                
            table_names = [t["name"] for t in tables]
            context_lines.append(f"\nSchema '{s_name}' contains {len(tables)} tables: {', '.join(table_names)}")
            
            # If a specific table is requested, describe its columns
            if schema_name and table_name:
                # Describe only the specific table
                for t in tables:
                    if t["name"] == table_name:
                        columns = ExplorerService.get_columns(engine, s_name, table_name)
                        col_details = []
                        for c in columns:
                            pk = " (PK)" if c.get("is_primary_key") else ""
                            fk = f" (FK -> {c['foreign_key']['referred_table']})" if c.get("foreign_key") else ""
                            col_details.append(f"  - {c['name']}: {c['data_type']}{pk}{fk}")
                        
                        context_lines.append(f"\nDetails for table '{s_name}.{table_name}':")
                        context_lines.extend(col_details)
            elif schema_name: # Only fetch all columns if they specifically selected a schema but no table, to avoid token explosion
                for t in tables:
                    # In a real app, we might limit this, but for now we fetch all
                    columns = ExplorerService.get_columns(engine, s_name, t["name"])
                    col_names = [c["name"] for c in columns]
                    context_lines.append(f"  - {t['name']} ({', '.join(col_names)})")

    except Exception as e:
        context_lines.append(f"Error retrieving schema context: {str(e)}")
        
    return "\n".join(context_lines)


def process_assistant_chat(engine: Engine, request: AssistantRequest) -> AssistantResponse:
    # Determine the provider to use: explicit request overrides server default.
    provider_name = request.provider or settings.DEFAULT_AI_PROVIDER

    # Bound Chat History (max 10 recent messages)
    recent_messages = request.messages[-10:] if len(request.messages) > 10 else request.messages
    # Prevent oversized individual messages
    for msg in recent_messages:
        if len(msg.content) > 2000:
            msg.content = msg.content[:2000] + "... (truncated)"
            
    # Construct context
    schema_context = _build_context_prompt(engine, request.schema_name, request.table_name)
    
    system_prompt = f"""You are a helpful AI assistant integrated into a Data Warehouse Explorer.
Your goal is to help users understand their data and write SQL queries.

Warehouse Schema Context:
{schema_context}

Instructions:
- Answer questions about the database schema based on the context above.
- If the user asks for data, generate a read-only PostgreSQL SQL query.
- IMPORTANT: You MUST ONLY generate `SELECT` queries. Never generate `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, etc.
- Always output SQL queries inside markdown ```sql blocks.
- Do NOT execute the queries. The user will run them manually.
- Be concise and helpful.
"""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in recent_messages:
        messages.append({"role": msg.role, "content": msg.content})
        
    # Delegate to the explicitly selected (or default) provider — no fallback.
    try:
        provider = ProviderFactory.get_provider(provider_name)
        reply = provider.generate_sql(messages)
        return AssistantResponse(response=reply, provider_used=provider_name)
    except UnsupportedAIProviderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"AI provider error: {str(e)}")


