"""
Warehouse service layer.

Pure business logic for managing data-warehouse connections.
This module is **route-agnostic** — it accepts a database session,
operates on ORM models, and returns domain objects.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.warehouse import Warehouse
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate


# ── Query helpers ────────────────────────────────────────────────


def get_all_warehouses(db: Session) -> list[Warehouse]:
    """
    Return every active warehouse connection.

    Parameters
    ──────────
    db : Active SQLAlchemy session.

    Returns
    ───────
    list[Warehouse]
        All rows where ``is_active`` is ``True``, ordered by name.
    """
    stmt = (
        select(Warehouse)
        .where(Warehouse.is_active == True)  # noqa: E712
        .order_by(Warehouse.name)
    )
    return list(db.execute(stmt).scalars().all())


def get_warehouse_by_id(db: Session, warehouse_id: int) -> Warehouse | None:
    """
    Look up a warehouse by its primary key.

    Parameters
    ──────────
    db           : Active SQLAlchemy session.
    warehouse_id : The integer primary key.

    Returns
    ───────
    Warehouse | None
        The matching row, or ``None`` if not found.
    """
    stmt = select(Warehouse).where(Warehouse.id == warehouse_id)
    return db.execute(stmt).scalars().first()


# ── Create ───────────────────────────────────────────────────────


def create_warehouse(db: Session, warehouse_data: WarehouseCreate) -> Warehouse:
    """
    Register a new data-warehouse connection.

    Workflow
    ────────
    1. Verify the name is not already taken.
    2. Persist the new row (password stored as-is for now).
    3. Return the created warehouse with database-generated fields.

    Parameters
    ──────────
    db             : Active SQLAlchemy session.
    warehouse_data : Validated creation payload.

    Returns
    ───────
    Warehouse
        The newly created warehouse instance.

    Raises
    ──────
    ValueError
        If a warehouse with the same name already exists.
    """
    # ── Duplicate check ──────────────────────────────────────────
    existing_stmt = select(Warehouse).where(Warehouse.name == warehouse_data.name)
    existing = db.execute(existing_stmt).scalars().first()

    if existing is not None:
        raise ValueError(
            f"Warehouse with name '{warehouse_data.name}' already exists."
        )

    # ── Persist ──────────────────────────────────────────────────
    new_warehouse = Warehouse(
        name=warehouse_data.name,
        description=warehouse_data.description,
        db_type=warehouse_data.db_type,
        host=warehouse_data.host,
        port=warehouse_data.port,
        database_name=warehouse_data.database_name,
        username=warehouse_data.username,
        encrypted_password=warehouse_data.password,  # encryption added later
    )

    db.add(new_warehouse)
    db.commit()
    db.refresh(new_warehouse)

    return new_warehouse


# ── Update ───────────────────────────────────────────────────────


def update_warehouse(
    db: Session,
    warehouse_id: int,
    warehouse_data: WarehouseUpdate,
) -> Warehouse | None:
    """
    Partially update an existing warehouse connection.

    Only the fields explicitly supplied in ``warehouse_data`` are
    modified; all others remain unchanged.

    Parameters
    ──────────
    db             : Active SQLAlchemy session.
    warehouse_id   : Primary key of the warehouse to update.
    warehouse_data : Validated update payload (all fields optional).

    Returns
    ───────
    Warehouse | None
        The updated warehouse, or ``None`` if the id does not exist.
    """
    warehouse = get_warehouse_by_id(db, warehouse_id)
    if warehouse is None:
        return None

    # ── Apply only supplied fields ───────────────────────────────
    update_fields = warehouse_data.model_dump(exclude_unset=True)

    # Map schema field "password" → model field "encrypted_password"
    if "password" in update_fields:
        update_fields["encrypted_password"] = update_fields.pop("password")

    for field, value in update_fields.items():
        setattr(warehouse, field, value)

    db.commit()
    db.refresh(warehouse)

    return warehouse


# ── Delete (soft) ────────────────────────────────────────────────


def delete_warehouse(db: Session, warehouse_id: int) -> Warehouse | None:
    """
    Soft-delete a warehouse by setting ``is_active = False``.

    The row remains in the database for auditing purposes but
    will no longer appear in active listings.

    Parameters
    ──────────
    db           : Active SQLAlchemy session.
    warehouse_id : Primary key of the warehouse to deactivate.

    Returns
    ───────
    Warehouse | None
        The deactivated warehouse, or ``None`` if the id does
        not exist.
    """
    warehouse = get_warehouse_by_id(db, warehouse_id)
    if warehouse is None:
        return None

    warehouse.is_active = False

    db.commit()
    db.refresh(warehouse)

    return warehouse
