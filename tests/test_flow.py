from datetime import timedelta
from io import BytesIO
from flask_migrate import upgrade
from openpyxl import load_workbook
from sqlalchemy import text
from easy import create_app,today
from easy.models import db,Order,User
from test_app import app,client,create_order,version,add_item


def milestone(client,app,ident,action,day=None,reference='',submitted=None):
    return client.post(f'/ordens/{ident}/fluxo',data={'action':action,'action_date':(day or today()).isoformat(),'reference':reference,'version':submitted or version(app,ident)})


def test_full_cycle_selected_phase_history_and_export(client,app):
    ident=create_order(client,app)
    add_item(client,app,ident,price='150')
    for status in ['Aprovado','Em serviço','Pronto para entrega','Entregue','Faturado','Recebido']:
        response=client.post(f'/ordens/{ident}/status',data={'status':status,'version':version(app,ident)})
        assert response.status_code==302
        with app.app_context():assert db.session.get(Order,ident).status==status
    with app.app_context():
        order=db.session.get(Order,ident)
        assert order.approved_date==order.started_date==order.ready_date==order.delivered_date==order.invoiced_date==order.received_date==today()
        assert order.flow_steps[6]['state']=='current'
        assert all(step['state']=='done' for step in order.flow_steps[:6])
        assert len(order.events)>=8
    book=load_workbook(BytesIO(client.get('/relatorios/exportar').data))
    assert book.active['L2'].value==150 and book.active['R2'].value=='Recebido'


def test_out_of_order_finance_repeat_and_conflicts(client,app):
    ident=create_order(client,app)
    assert milestone(client,app,ident,'receive').status_code==302
    with app.app_context():
        order=db.session.get(Order,ident)
        assert order.status=='Recebido' and order.received_date
        assert order.invoiced_date is None and order.delivered_date is None
        assert order.flow_steps[5]['state']=='pending'
    assert milestone(client,app,ident,'invoice').status_code==302
    old=version(app,ident)
    assert milestone(client,app,ident,'approve').status_code==302
    assert milestone(client,app,ident,'receive',submitted=old).status_code==409
    assert milestone(client,app,ident,'approve').status_code==302
    with app.app_context():
        order=db.session.get(Order,ident)
        assert order.status=='Aprovado' and order.flow_label=='Aprovado'
        assert order.received_date and order.invoiced_date and order.delivered_date is None
    assert milestone(client,app,ident,'unknown').status_code==400


def test_admin_can_move_back_and_edit_after_delivery(client,app):
    ident=create_order(client,app)
    for status in ['Entregue','Cancelada','Em serviço','Faturado','Pronto para entrega']:
        assert client.post(f'/ordens/{ident}/status',data={'status':status,'version':version(app,ident)}).status_code==302
    assert add_item(client,app,ident,description='Serviço livre').status_code==302
    with app.app_context():
        order=db.session.get(Order,ident)
        assert order.status=='Pronto para entrega' and order.delivered_date and order.invoiced_date
        assert not order.items[0].done


def test_corrections_do_not_require_other_corrections(client,app):
    ident=create_order(client,app)
    milestone(client,app,ident,'invoice');milestone(client,app,ident,'receive')
    assert milestone(client,app,ident,'clear_invoice').status_code==302
    with app.app_context():
        order=db.session.get(Order,ident)
        assert order.invoiced_date is None and order.received_date
    team=app.test_client();team.post('/login',data={'username':'team','password':'strong-password-123'})
    assert milestone(team,app,ident,'clear_received').status_code==403
    assert milestone(client,app,ident,'clear_received').status_code==302
    with app.app_context():assert db.session.get(Order,ident).received_date is None


def test_service_changes_never_move_flow(client,app):
    ident=create_order(client,app)
    client.post(f'/ordens/{ident}/status',data={'status':'Pronto para entrega','version':version(app,ident)})
    with app.app_context():stamp=db.session.get(Order,ident).ready_at
    add_item(client,app,ident,description='Novo serviço')
    with app.app_context():
        order=db.session.get(Order,ident);item_id=order.items[0].id
        assert order.status=='Pronto para entrega' and order.ready_at==stamp
    client.post(f'/ordens/{ident}/itens/{item_id}/acao',data={'action':'remove','version':version(app,ident)})
    with app.app_context():
        order=db.session.get(Order,ident)
        assert not order.items and order.status=='Pronto para entrega' and order.ready_at==stamp


def test_cancelled_actions_and_csrf(client,app):
    ident=create_order(client,app)
    assert app.test_client().post(f'/ordens/{ident}/fluxo').status_code==302
    client.post(f'/ordens/{ident}/status',data={'status':'Cancelada','version':version(app,ident)})
    assert milestone(client,app,ident,'approve').status_code==302
    with app.app_context():assert db.session.get(Order,ident).status=='Aprovado'
    app.config['WTF_CSRF_ENABLED']=True
    assert milestone(client,app,ident,'receive').status_code==400


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
        assert order.vehicle_plate=='ABC1D23' and order.vehicle_model=='Existing vehicle'
        assert order.delivered_date.isoformat() == '2026-01-03'
        assert order.approved_date is None and order.started_date is None and order.ready_date is None
        assert order.entered_at is None and order.delivered_at is None
        assert order.invoiced_date is None and order.received_date is None
        assert order.flow_steps[2]['state'] == 'pending' and order.flow_steps[2]['date'] is None
        assert order.flow_steps[1]['state'] == 'pending'
        assert db.session.get(User,user.id).check_password('strong-password-123')
        assert db.session.execute(text('SELECT version_num FROM ecs_alembic_version')).scalar() == 'af824c1d7e30'
