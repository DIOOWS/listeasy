"""Delete clients from the active UI while retaining order history."""
from alembic import op
import sqlalchemy as sa
revision='fa1027bd68e1'
down_revision='f91bd829a5e0'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('ecs_clients',sa.Column('deleted_at',sa.DateTime(),nullable=True))
    op.create_index('ix_ecs_clients_deleted_at','ecs_clients',['deleted_at'])

def downgrade():
    if op.get_bind().execute(sa.text('SELECT COUNT(*) FROM ecs_clients WHERE deleted_at IS NOT NULL')).scalar():
        raise RuntimeError('Existem clientes excluídos. Resolva-os antes de voltar a uma versão que voltaria a exibi-los.')
    op.drop_index('ix_ecs_clients_deleted_at',table_name='ecs_clients')
    with op.batch_alter_table('ecs_clients') as batch:
        batch.drop_column('deleted_at')
