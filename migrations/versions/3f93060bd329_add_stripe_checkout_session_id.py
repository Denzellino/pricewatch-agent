"""add stripe checkout session id

Revision ID: 3f93060bd329
Revises: 4a03bc6e324b
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3f93060bd329"
down_revision: Union[str, Sequence[str], None] = "4a03bc6e324b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    columns = {
        column["name"]
        for column in sa.inspect(connection).get_columns("subscriptions")
    }

    if "stripe_checkout_session_id" not in columns:
        op.add_column(
            "subscriptions",
            sa.Column(
                "stripe_checkout_session_id",
                sa.String(length=255),
                nullable=True,
            ),
        )

    indexes = {
        index["name"]
        for index in sa.inspect(connection).get_indexes("subscriptions")
    }

    if "ix_subscriptions_stripe_checkout_session_id" not in indexes:
        op.create_index(
            "ix_subscriptions_stripe_checkout_session_id",
            "subscriptions",
            ["stripe_checkout_session_id"],
            unique=True,
        )


def downgrade() -> None:
    connection = op.get_bind()

    indexes = {
        index["name"]
        for index in sa.inspect(connection).get_indexes("subscriptions")
    }

    if "ix_subscriptions_stripe_checkout_session_id" in indexes:
        op.drop_index(
            "ix_subscriptions_stripe_checkout_session_id",
            table_name="subscriptions",
        )

    columns = {
        column["name"]
        for column in sa.inspect(connection).get_columns("subscriptions")
    }

    if "stripe_checkout_session_id" in columns:
        op.drop_column(
            "subscriptions",
            "stripe_checkout_session_id",
        )
