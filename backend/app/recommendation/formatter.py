from typing import Any, Dict, List

class RecommendationFormatter:
    """
    Presentation layer for converting machine-readable recommendation 
    outputs into human-readable structures for the frontend.
    """

    # Mapping from recommendation_type to Human-Readable content
    _TYPE_MAPPING = {
        "missing_primary_key": {
            "title": "Missing Primary Key",
            "problem": "A table is missing a primary key, which makes it impossible to uniquely identify rows.",
            "why_it_matters": "Without a primary key, updating or deleting specific rows is unreliable and query performance may suffer.",
            "recommended_action": "Add a primary key constraint to the table.",
        },
        "weak_table_name": {
            "title": "Weak Table Name",
            "problem": "A table has a generic or poorly descriptive name (e.g., 'temp', 'test', 'data').",
            "why_it_matters": "Poorly named tables reduce maintainability and increase confusion for analysts querying the data.",
            "recommended_action": "Rename the table to clearly reflect the business entity it represents.",
        },
        "weak_column_name": {
            "title": "Weak Column Name",
            "problem": "A column has a generic or poorly descriptive name.",
            "why_it_matters": "Generic column names make it difficult to understand the data's purpose without external documentation.",
            "recommended_action": "Rename the column to be more descriptive.",
        },
        "large_table_indexing": {
            "title": "Large Table Needs Indexing",
            "problem": "A large table was detected which may not have adequate indexing.",
            "why_it_matters": "Querying large tables without proper indexes leads to full table scans, heavily degrading database performance.",
            "recommended_action": "Review query patterns and add appropriate indexes to frequently filtered or joined columns.",
        },
        "empty_table": {
            "title": "Empty Table Detected",
            "problem": "A table contains zero rows and has not been recently created.",
            "why_it_matters": "Stale or unused empty tables clutter the schema and create cognitive overhead.",
            "recommended_action": "Drop or archive the table if it is no longer required.",
        },
        "wide_table": {
            "title": "Excessively Wide Table",
            "problem": "A table has a very high number of columns.",
            "why_it_matters": "Wide tables are difficult to maintain, can exceed database row size limits, and often indicate poor normalization.",
            "recommended_action": "Consider normalizing the table by splitting it into smaller, related entities.",
        },
        "sensitive_column": {
            "title": "Sensitive Data Detected",
            "problem": "A column appears to store sensitive or personally identifiable information (PII).",
            "why_it_matters": "Unprotected sensitive data is a major security and compliance risk (e.g., GDPR, HIPAA).",
            "recommended_action": "Review access controls for this column and consider applying data masking or encryption.",
        },
        "excessive_table_nullability": {
            "title": "Excessive Table Nullability",
            "problem": "A high percentage of columns in the table allow NULL values.",
            "why_it_matters": "Excessive nullability can lead to inconsistent application logic and indicates the schema might not accurately reflect business rules.",
            "recommended_action": "Review nullable columns and enforce NOT NULL constraints where appropriate.",
        },
        "missing_uniqueness_constraints": {
            "title": "Missing Uniqueness Constraints",
            "problem": "Data that appears to be unique lacks a formal uniqueness constraint.",
            "why_it_matters": "Without constraints, duplicate data can be accidentally inserted, compromising data integrity.",
            "recommended_action": "Define a unique constraint or primary key after confirming the table's business semantics.",
        },
        "invalid_or_unknown_datatype": {
            "title": "Invalid or Unknown Datatype",
            "problem": "A column uses a generic or unknown data type (e.g., storing dates as strings).",
            "why_it_matters": "Incorrect data types prevent the database from optimizing storage and validating data formats.",
            "recommended_action": "Alter the column to use an explicitly valid and appropriate data type.",
        },
        "inconsistent_datatypes": {
            "title": "Inconsistent Data Types",
            "problem": "Similar columns or foreign key relationships use inconsistent data types.",
            "why_it_matters": "Inconsistent types can prevent index usage during joins and lead to subtle bugs.",
            "recommended_action": "Standardize the data type across the affected structures.",
        },
    }

    def format(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Accepts the raw structured recommendation dictionary and builds a 
        human-readable 'presentation' representation alongside it.
        """
        if not raw_data:
            return raw_data

        summary = raw_data.get("summary", {})
        recommendations = raw_data.get("recommendations", [])

        presentation = {
            "overview": self._format_summary(summary),
            "priority_actions": self._format_actions(recommendations)
        }

        # Return a composite dictionary containing the original data + presentation
        return {
            "summary": summary,
            "recommendations": recommendations,
            "priority": raw_data.get("priority", {}),
            "presentation": presentation
        }

    def _format_summary(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts key summary statistics for the frontend to render nicely.
        """
        return {
            "total": summary.get("recommendation_count", 0),
            "high": summary.get("high", 0),
            "medium": summary.get("medium", 0),
            "low": summary.get("low", 0),
        }

    def _format_actions(self, recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Formats each recommendation into a user-friendly priority action.
        """
        actions = []
        for rec in recommendations:
            rec_type = rec.get("recommendation_type", "").lower()
            
            # Lookup mapping or fallback gracefully
            mapping = self._TYPE_MAPPING.get(rec_type, {
                "title": "Database Recommendation",
                "problem": rec.get("description", "A potential improvement was identified."),
                "why_it_matters": "Addressing this may improve database health, performance, or security.",
                "recommended_action": "Review the affected database object.",
            })

            # Create the presentation model
            action = {
                "title": mapping["title"],
                "problem": mapping["problem"],
                "why_it_matters": mapping["why_it_matters"],
                "recommended_action": mapping["recommended_action"],
                
                # Passthrough essential metadata for the UI to display directly
                "priority": rec.get("priority", "LOW"),
                "impact": rec.get("impact", "LOW"),
                "effort": rec.get("effort", "LOW"),
                "confidence": round(rec.get("confidence", 0) * 100, 1), # e.g. 1.0 -> 100.0
                
                # Context formatting
                "source": ", ".join([s.replace("_", " ").title() + " Agent" for s in rec.get("source_agents", [])]),
                "location": {
                    "schema": rec.get("schema"),
                    "table": rec.get("table"),
                    "column": rec.get("column")
                },
                "raw_description": rec.get("description") # useful for extra context
            }
            actions.append(action)

        return actions
