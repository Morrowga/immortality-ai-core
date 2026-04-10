"""add memory encryption

Revision ID: 003_memory_encryption
Revises: 002_souls_billing
Create Date: 2026-04-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = '003_memory_encryption'
down_revision: Union[str, None] = '002_souls_billing'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENCRYPTED_COLUMNS = [
    'transcript_text',
    'transcript_original',
    'what_happened',
    'context',
    'how_i_felt',
    'why_it_mattered',
    'what_i_learned',
    'instinct_formed',
    'cultural_expression_notes',
    'what_happened_original',
    'how_i_felt_original',
    'why_it_mattered_original',
    'what_i_learned_original',
    'instinct_formed_original',
]


def upgrade() -> None:
    # No column type changes needed — Fernet output is still TEXT
    # Encrypt all existing memory rows
    import os
    from cryptography.fernet import Fernet

    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY not set — cannot migrate existing data")

    fernet = Fernet(key.encode())
    conn = op.get_bind()

    rows = conn.execute(text("SELECT id FROM memories")).fetchall()

    for row in rows:
        memory_id = row[0]
        current = conn.execute(
            text("SELECT " + ", ".join(ENCRYPTED_COLUMNS) + " FROM memories WHERE id = :id"),
            {"id": memory_id}
        ).fetchone()

        updates = {}
        for i, col in enumerate(ENCRYPTED_COLUMNS):
            val = current[i]
            if val and not val.startswith("gAAAAA"):  # skip already encrypted
                updates[col] = fernet.encrypt(val.encode()).decode()

        if updates:
            set_clause = ", ".join(f"{col} = :{col}" for col in updates)
            updates["id"] = memory_id
            conn.execute(
                text(f"UPDATE memories SET {set_clause} WHERE id = :id"),
                updates
            )


def downgrade() -> None:
    # Decrypt all rows back to plaintext
    import os
    from cryptography.fernet import Fernet

    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY not set — cannot downgrade")

    fernet = Fernet(key.encode())
    conn = op.get_bind()

    rows = conn.execute(text("SELECT id FROM memories")).fetchall()

    for row in rows:
        memory_id = row[0]
        current = conn.execute(
            text("SELECT " + ", ".join(ENCRYPTED_COLUMNS) + " FROM memories WHERE id = :id"),
            {"id": memory_id}
        ).fetchone()

        updates = {}
        for i, col in enumerate(ENCRYPTED_COLUMNS):
            val = current[i]
            if val and val.startswith("gAAAAA"):  # only decrypt encrypted values
                updates[col] = fernet.decrypt(val.encode()).decode()

        if updates:
            set_clause = ", ".join(f"{col} = :{col}" for col in updates)
            updates["id"] = memory_id
            conn.execute(
                text(f"UPDATE memories SET {set_clause} WHERE id = :id"),
                updates
            )