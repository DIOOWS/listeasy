"""Protect app tables from Supabase browser-facing API roles.

Revision ID: 8b01a67fc912
Revises: 2f44ce3f6db2
"""
from alembic import op
revision='8b01a67fc912'
down_revision='2f44ce3f6db2'
branch_labels=None
depends_on=None
TABLES=['ecs_clients','ecs_users','ecs_vehicles','ecs_orders','ecs_checks','ecs_items','ecs_events','ecs_photos','ecs_alembic_version']

def upgrade():
    if op.get_context().dialect.name!='postgresql':return
    for table in TABLES:
        op.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
        for role in ['anon','authenticated']:
            # These roles exist on Supabase but may be absent on generic PostgreSQL.
            op.execute(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN REVOKE ALL ON TABLE public.{table} FROM {role}; END IF; END $$;")

def downgrade():
    # Preserve protections on downgrade; the prior revision drops the tables.
    pass
