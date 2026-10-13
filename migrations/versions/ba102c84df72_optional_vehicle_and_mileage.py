"""Allow creating an OS with only a client, without fictitious vehicle data."""
from alembic import op
import sqlalchemy as sa
revision='ba102c84df72'
down_revision='fa1027bd68e1'
branch_labels=None
depends_on=None

def upgrade():
    with op.batch_alter_table('ecs_orders') as batch:
        batch.alter_column('vehicle_id',existing_type=sa.Integer(),nullable=True)
        batch.alter_column('mileage',existing_type=sa.Integer(),nullable=True)

def downgrade():
    if op.get_bind().execute(sa.text('SELECT COUNT(*) FROM ecs_orders WHERE vehicle_id IS NULL OR mileage IS NULL')).scalar():
        raise RuntimeError('Preencha veículo e quilometragem antes de voltar à versão que os exige.')
    with op.batch_alter_table('ecs_orders') as batch:
        batch.alter_column('vehicle_id',existing_type=sa.Integer(),nullable=False)
        batch.alter_column('mileage',existing_type=sa.Integer(),nullable=False)
