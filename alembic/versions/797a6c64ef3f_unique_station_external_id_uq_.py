from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "797a6c64ef3f"
down_revision = "96298b54cb53"
branch_labels = None
depends_on = None

def upgrade():
    # 1) если был обычный индекс по external_id — уберём его,
    #    т.к. ниже создадим уникальное ограничение
    try:
        op.drop_index("ix_stations_external_id", table_name="stations")
    except Exception:
        # если индекса нет — просто идём дальше
        pass

    # 2) на всякий случай очистим ненумерические значения (если вдруг попали)
    op.execute("""
        UPDATE stations
        SET external_id = NULL
        WHERE external_id IS NOT NULL AND external_id !~ '^[0-9]+$';
    """)

    # 3) сменим тип на INTEGER с явным USING
    op.alter_column(
        "stations",
        "external_id",
        type_=sa.Integer(),
        postgresql_using="NULLIF(regexp_replace(external_id, '[^0-9]', '', 'g'), '')::integer",
        existing_nullable=True,
    )

    # 4) добавим уникальность на stations.external_id
    op.create_unique_constraint(
        "uq_stations_external_id",
        "stations",
        ["external_id"],
    )

    # 5) уникальность на measurements (station_id, parameter, measured_at)
    op.create_unique_constraint(
        "uq_meas_s_p_ts",
        "measurements",
        ["station_id", "parameter", "measured_at"],
    )


def downgrade():
    # откатим уникальные ограничения
    try:
        op.drop_constraint("uq_meas_s_p_ts", "measurements", type_="unique")
    except Exception:
        pass
    try:
        op.drop_constraint("uq_stations_external_id", "stations", type_="unique")
    except Exception:
        pass

    # вернём тип к TEXT (или VARCHAR), если раньше таким был
    op.alter_column(
        "stations",
        "external_id",
        type_=sa.String(length=20),
        postgresql_using="external_id::text",
        existing_nullable=True,
    )

    # восстановление индекса (опционально)
    op.create_index(
        "ix_stations_external_id",
        "stations",
        ["external_id"],
        unique=False,
    )
