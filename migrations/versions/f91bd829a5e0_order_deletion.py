"""Allow deleting an OS from the app while retaining its audit history."""
from alembic import op
import sqlalchemy as sa
revision='f91bd829a5e0'
down_revision='e821c4a73db2'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('ecs_orders',sa.Column('deleted_at',sa.DateTime(),nullable=True))
    op.create_index('ix_ecs_orders_deleted_at','ecs_orders',['deleted_at'])

def downgrade():
    if op.get_bind().execute(sa.text('SELECT COUNT(*) FROM ecs_orders WHERE deleted_at IS NOT NULL')).scalar():
        raise RuntimeError('Existem OS excluídas. Resolva-as antes de voltar a uma versão que voltaria a exibi-las.')
    op.drop_index('ix_ecs_orders_deleted_at',table_name='ecs_orders')
    with op.batch_alter_table('ecs_orders') as batch:
        batch.drop_column('deleted_at')
