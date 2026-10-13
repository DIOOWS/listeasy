"""Keep vehicle data inside each order, preserving all existing records."""
from alembic import op
import sqlalchemy as sa

revision='d71fa921c408'
down_revision='c410a924ef73'
branch_labels=None
depends_on=None

def upgrade():
    for name,length in [('vehicle_plate',10),('vehicle_model',120),('vehicle_fleet',40)]:
        op.add_column('ecs_orders',sa.Column(name,sa.String(length),nullable=True))
    # Portable PostgreSQL/SQLite; leaves vehicle/client/user records untouched.
    for target,source in [('vehicle_plate','plate'),('vehicle_model','model'),('vehicle_fleet','fleet')]:
        op.execute(sa.text(f'UPDATE ecs_orders SET {target} = (SELECT {source} FROM ecs_vehicles WHERE ecs_vehicles.id = ecs_orders.vehicle_id)'))

def downgrade():
    with op.batch_alter_table('ecs_orders') as batch:
        for name in ['vehicle_fleet','vehicle_model','vehicle_plate']:
            batch.drop_column(name)
