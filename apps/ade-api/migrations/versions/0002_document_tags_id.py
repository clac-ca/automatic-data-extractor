"""Add surrogate ID primary key to document tags."""

from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from alembic import op

from ade_api.common.ids import generate_uuid7
from ade_api.db.types import UUIDType


# Revision identifiers, used by Alembic.
revision = "0002_document_tags_id"
down_revision: Optional[str] = "0001_initial_schema"
branch_labels: Optional[str] = None
depends_on: Optional[str] = None


def upgrade() -> None:
    with op.batch_alter_table("document_tags") as batch:
        batch.add_column(sa.Column("id", UUIDType(), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT document_id, tag FROM document_tags")).fetchall()
    for row in rows:
        connection.execute(
            sa.text(
                "UPDATE document_tags "
                "SET id = :id "
                "WHERE document_id = :document_id AND tag = :tag"
            ),
            {"id": str(generate_uuid7()), "document_id": row[0], "tag": row[1]},
        )

    with op.batch_alter_table("document_tags") as batch:
        batch.alter_column("id", nullable=False)
        batch.drop_constraint("document_tags_pkey", type_="primary")
        batch.create_primary_key("document_tags_pkey", ["id"])
        batch.create_unique_constraint(
            "document_tags_document_id_tag_key",
            ["document_id", "tag"],
        )
        batch.create_index(
            "document_tags_tag_document_id_idx",
            ["tag", "document_id"],
            unique=False,
        )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for this revision.")
