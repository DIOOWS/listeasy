from datetime import timedelta
from io import BytesIO

from flask_migrate import upgrade
from openpyxl import load_workbook
from sqlalchemy import text

from easy import create_app, today
from easy.models import db, Order, User
from test_app import app, client, create_order, version, add_item


def milestone(client, app, ident, action, day=None, reference='', submitted=None):
    return client.post(f'/ordens/{ident}/fluxo', data={
        'action': action, 'action_date': (day or today()).isoformat(),
        'reference': reference, 'version': submitted or version(app, ident),
    })


def deliver(client, app, ident):
    add_item(client, app, ident, done=True)
    with app.app_context():
        for check in db.session.get(Order, ident).checks:
            check.result = 'ok'
        db.session.commit()
    for status in ['Em serviço', 'Pronto para entrega', 'Entregue']:
        response = client.post(f'/ordens/{ident}/status', data={
            'version': version(app, ident), 'status': status,
            'delivered_date': today().isoformat(),
        })
        assert response.status_code == 302
        with app.app_context():
            assert db.session.get(Order, ident).status == status


def test_flow_full_cycle_dates_history_and_finance_queue(client, app):
    ident = create_order(client, app)
    milestone(client, app, ident, 'approve', reference='Cliente confirmou por telefone')
    deliver(client, app, ident)
    with app.app_context():
        order = db.session.get(Order, ident)
        assert order.approved_date == order.started_date == order.ready_date == today()
        assert order.flow_steps[5]['state'] == 'current'
        number = order.number
        assert any(e.user.username == 'admin' and 'Aprovação registrado' in e.description for e in order.events)
    home = client.get('/').text
    assert number in home and 'pendência financeira' in home
    milestone(client, app, ident, 'invoice', reference='NF 123')
    with app.app_context():
        assert db.session.get(Order, ident).flow_steps[6]['state'] == 'current'
    milestone(client, app, ident, 'receive', reference='PIX confirmado')
    with app.app_context():
        order = db.session.get(Order, ident)
        assert order.invoiced_date == order.received_date == today()
        assert all(step['state'] == 'done' for step in order.flow_steps)
        assert len([e for e in order.events if 'Referência:' in e.description]) == 3
    assert number not in client.get('/').text
    assert number in client.get('/ordens').text
    assert number not in client.get('/ordens?finance=1').text
    sheet = load_workbook(BytesIO(client.get('/relatorios/exportar').data)).active
    assert sheet['L2'].value == 150
    assert sheet['M1'].value == 'Aprovação' and sheet['R2'].value == 'Recebido'
    assert sheet['Q2'].value.date() == today()
    assert 'Etapas do atendimento' in client.get(f'/ordens/{ident}/imprimir').text


def test_flow_blocks_invalid_sequence_dates_and_stale_updates(client, app):
    ident = create_order(client, app)
    for action in ['invoice', 'receive']:
        milestone(client, app, ident, action)
    for day in [today() - timedelta(days=1), today() + timedelta(days=1)]:
        milestone(client, app, ident, 'approve', day=day)
    with app.app_context():
        order = db.session.get(Order, ident)
        assert not order.approved_date and not order.invoiced_date and not order.received_date
    old = version(app, ident)
    milestone(client, app, ident, 'approve')
    assert milestone(client, app, ident, 'approve', submitted=old).status_code == 409
    milestone(client, app, ident, 'approve')
    with app.app_context():
        assert len([e for e in db.session.get(Order, ident).events if 'Aprovação registrado' in e.description]) == 1
    assert client.post(f'/ordens/{ident}/fluxo', data={'action':'unknown','version':version(app, ident),'action_date':today().isoformat()}).status_code == 400


def test_flow_chronology_and_entry_edit(client, app):
    ident = create_order(client, app)
    with app.app_context():
        order = db.session.get(Order, ident)
        order.entry_date = today() - timedelta(days=3)
        order.status = 'Entregue'
        order.started_date = today() - timedelta(days=2)
        order.ready_date = order.delivered_date = today() - timedelta(days=1)
        db.session.commit()
    milestone(client, app, ident, 'approve')  # after service: rejected
    milestone(client, app, ident, 'invoice', day=today() - timedelta(days=2))
    with app.app_context():
        order = db.session.get(Order, ident)
        assert order.approved_date is None and order.invoiced_date is None
    milestone(client, app, ident, 'approve', day=today() - timedelta(days=3))
    milestone(client, app, ident, 'invoice')
    milestone(client, app, ident, 'receive', day=today() - timedelta(days=1))
    with app.app_context():
        assert db.session.get(Order, ident).received_date is None


def test_flow_admin_corrections_and_closed_order_rules(client, app):
    ident = create_order(client, app)
    deliver(client, app, ident)
    milestone(client, app, ident, 'invoice')
    milestone(client, app, ident, 'receive')
    client.post(f'/ordens/{ident}/status', data={'version':version(app, ident),'status':'Em serviço'})
    milestone(client, app, ident, 'clear_invoice', reference='Corrigir nota')
    milestone(client, app, ident, 'clear_received')  # no reason: rejected
    with app.app_context():
        order = db.session.get(Order, ident)
        assert order.status == 'Entregue' and order.received_date and order.invoiced_date
    team = app.test_client()
    team.post('/login',data={'username':'team','password':'strong-password-123'})
    assert 'value="clear_received"' not in team.get(f'/ordens/{ident}').text
    assert milestone(team, app, ident, 'clear_received', reference='Corrigir').status_code == 400
    milestone(client, app, ident, 'clear_received', reference='Pagamento identificado em outra OS')
    milestone(client, app, ident, 'clear_invoice', reference='Nota anulada')
    client.post(f'/ordens/{ident}/status', data={'version':version(app, ident),'status':'Em serviço'})
    with app.app_context():
        order = db.session.get(Order, ident)
        assert order.status == 'Em serviço' and order.ready_date is None
        assert order.delivered_date is None and order.invoiced_date is None and order.received_date is None
        assert any('Nota anulada' in e.description and e.user.username == 'admin' for e in order.events)


def test_flow_ready_invalidation_and_approval_does_not_reopen(client, app):
    ident = create_order(client, app)
    deliver(client, app, ident)
    client.post(f'/ordens/{ident}/status', data={'version':version(app, ident),'status':'Pronto para entrega'})
    milestone(client, app, ident, 'approve')
    with app.app_context():
        order = db.session.get(Order, ident)
        assert order.status == 'Pronto para entrega' and order.ready_date == today()
    add_item(client, app, ident, description='Novo serviço', done=False)
    with app.app_context():
        order = db.session.get(Order, ident)
        assert order.status == 'Em serviço' and order.ready_date is None
        assert order.flow_steps[3]['state'] == 'pending'


def test_flow_csrf_auth_and_cancelled(client, app):
    ident = create_order(client, app)
    assert app.test_client().post(f'/ordens/{ident}/fluxo').status_code == 302
    client.post(f'/ordens/{ident}/status', data={'version':version(app, ident),'status':'Cancelada'})
    milestone(client, app, ident, 'approve')
    with app.app_context():
        assert db.session.get(Order, ident).approved_date is None
    app.config['WTF_CSRF_ENABLED'] = True
    assert milestone(client, app, ident, 'approve').status_code == 400


def test_migration_keeps_existing_order_and_user(tmp_path):
    application = create_app({'TESTING':True,'SECRET_KEY':'migration-test-'*4,
        'SQLALCHEMY_DATABASE_URI':f'sqlite:///{tmp_path / "legacy.db"}',
        'WTF_CSRF_ENABLED':False,'RATELIMIT_ENABLED':False,'APP_ENV':'development'})
    with application.app_context():
        upgrade(revision='8b01a67fc912')
        user = User(username='kept',name='Existing user',role='admin')
        user.set_password('strong-password-123')
        db.session.add(user)
        db.session.execute(text("INSERT INTO ecs_clients (id,name,active) VALUES (1,'Existing client',1)"))
        db.session.execute(text("INSERT INTO ecs_vehicles (id,client_id,plate,model,active) VALUES (1,1,'ABC1D23','Existing vehicle',1)"))
        db.session.execute(text("""INSERT INTO ecs_orders
            (id,number,vehicle_id,client_id,entry_date,due_date,delivered_date,mileage,status,responsible,problem,discount,created_at,updated_at,version)
            VALUES (1,'LEGACY-1',1,1,'2026-01-01','2026-01-03','2026-01-03',100,'Entregue','Diogo','Existing service',0,'2026-01-01','2026-01-03',1)"""))
        db.session.commit()
        upgrade()
        order = db.session.get(Order,1)
        assert order.number == 'LEGACY-1' and order.status == 'Entregue'
        assert order.delivered_date.isoformat() == '2026-01-03'
        assert order.approved_date is None and order.started_date is None and order.ready_date is None
        assert order.invoiced_date is None and order.received_date is None
        assert order.flow_steps[2]['state'] == 'done' and order.flow_steps[2]['date'] is None
        assert order.flow_steps[1]['state'] == 'pending'
        assert db.session.get(User,user.id).check_password('strong-password-123')
        assert db.session.execute(text('SELECT version_num FROM ecs_alembic_version')).scalar() == 'c410a924ef73'
