"""Allow blank entry/due dates without changing existing dates or amounts."""
from alembic import op
import sqlalchemy as sa

revision='e821c4a73db2'
down_revision='d71fa921c408'
branch_labels=None
depends_on=None

def upgrade():
    with op.batch_alter_table('ecs_orders') as batch:
        batch.alter_column('entry_date',existing_type=sa.Date(),nullable=True)
        batch.alter_column('due_date',existing_type=sa.Date(),nullable=True)

def downgrade():
    count=op.get_bind().execute(sa.text('SELECT COUNT(*) FROM ecs_orders WHERE entry_date IS NULL OR due_date IS NULL')).scalar()
    if count:
        raise RuntimeError('Preencha as datas das OS antes de voltar à versão que exige datas. Nenhuma data será inventada.')
    with op.batch_alter_table('ecs_orders') as batch:
        batch.alter_column('entry_date',existing_type=sa.Date(),nullable=False)
        batch.alter_column('due_date',existing_type=sa.Date(),nullable=False)
