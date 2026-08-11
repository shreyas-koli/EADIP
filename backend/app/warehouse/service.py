"""
Warehouse service layer.

Pure business logic for managing data-warehouse connections.
This module is **route-agnostic** — it accepts a database session,
operates on ORM models, and returns domain objects.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.warehouse import Warehouse
from app.models.user import User
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate
from app.core.security import encrypt_credential


# ── Query helpers ────────────────────────────────────────────────


def get_all_warehouses(db: Session, user: User) -> list[Warehouse]:
    """
    Return every active warehouse connection accessible to the user.

    Parameters
    ──────────
    db   : Active SQLAlchemy session.
    user : The authenticated user requesting the list.

    Returns
    ───────
    list[Warehouse]
        All rows where ``is_active`` is ``True``, filtered by ownership, ordered by name.
    """
    stmt = (
        select(Warehouse)
        .where(Warehouse.is_active == True)  # noqa: E712
    )
    if user.role != "admin":
        stmt = stmt.where(Warehouse.owner_id == user.id)
    
    stmt = stmt.order_by(Warehouse.name)
    return list(db.execute(stmt).scalars().all())


def get_warehouse_by_id(db: Session, warehouse_id: int, user: User) -> Warehouse | None:
    """
    Look up a warehouse by its primary key, enforcing ownership.

    Parameters
    ──────────
    db           : Active SQLAlchemy session.
    warehouse_id : The integer primary key.
    user         : The authenticated user requesting the warehouse.

    Returns
    ───────
    Warehouse | None
        The matching row, or ``None`` if not found or unauthorized.
    """
    stmt = select(Warehouse).where(Warehouse.id == warehouse_id)
    if user.role != "admin":
        stmt = stmt.where(Warehouse.owner_id == user.id)
        
    return db.execute(stmt).scalars().first()


# ── Create ───────────────────────────────────────────────────────


def create_warehouse(db: Session, warehouse_data: WarehouseCreate, user: User) -> Warehouse:
    """
    Register a new data-warehouse connection.

    Workflow
    ────────
    1. Verify the name is not already taken.
    2. Persist the new row (password stored as ciphertext, owner assigned).
    3. Return the created warehouse with database-generated fields.

    Parameters
    ──────────
    db             : Active SQLAlchemy session.
    warehouse_data : Validated creation payload.
    user           : The authenticated user creating the warehouse.

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
        owner_id=user.id,
        name=warehouse_data.name,
        description=warehouse_data.description,
        db_type=warehouse_data.db_type,
        host=warehouse_data.host,
        port=warehouse_data.port,
        database_name=warehouse_data.database_name,
        username=warehouse_data.username,
        encrypted_password=encrypt_credential(warehouse_data.password),
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
    user: User,
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
    user           : The authenticated user requesting the update.

    Returns
    ───────
    Warehouse | None
        The updated warehouse, or ``None`` if the id does not exist or unauthorized.
    """
    warehouse = get_warehouse_by_id(db, warehouse_id, user)
    if warehouse is None:
        return None

    # ── Apply only supplied fields ───────────────────────────────
    update_fields = warehouse_data.model_dump(exclude_unset=True)

    # Map schema field "password" → model field "encrypted_password"
    if "password" in update_fields:
        update_fields["encrypted_password"] = encrypt_credential(update_fields.pop("password"))

    for field, value in update_fields.items():
        setattr(warehouse, field, value)

    db.commit()
    db.refresh(warehouse)

    return warehouse


# ── Delete (soft) ────────────────────────────────────────────────


def delete_warehouse(db: Session, warehouse_id: int, user: User) -> Warehouse | None:
    """
    Soft-delete a warehouse by setting ``is_active = False``.

    The row remains in the database for auditing purposes but
    will no longer appear in active listings.

    Parameters
    ──────────
    db           : Active SQLAlchemy session.
    warehouse_id : Primary key of the warehouse to deactivate.
    user         : The authenticated user requesting the deletion.

    Returns
    ───────
    Warehouse | None
        The deactivated warehouse, or ``None`` if the id does
        not exist or unauthorized.
    """
    warehouse = get_warehouse_by_id(db, warehouse_id, user)
    if warehouse is None:
        return None

    warehouse.is_active = False

    db.commit()
    db.refresh(warehouse)

    return warehouse
