from contextlib import contextmanager
from decimal import Decimal

from sqlalchemy import event

from easy import today
from easy.models import db, User, Client, Vehicle, Order, Item, Check, Event
from test_app import app, client


@contextmanager
def queries(app):
    statements=[]
    with app.app_context():
        engine=db.engine
    def record(connection,cursor,statement,parameters,context,many):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)
    event.listen(engine,'before_cursor_execute',record)
    try:
        yield statements
    finally:
        event.remove(engine,'before_cursor_execute',record)


def seed_orders(app,count):
    with app.app_context():
        for i in range(count):
            customer=Client(name=f'Cliente {i}')
            vehicle=Vehicle(client=customer,plate=f'ABC{i:04d}',model='Veículo')
            order=Order(number=f'PERF-{i}',vehicle=vehicle,client=customer,
                entry_date=today(),due_date=today(),responsible='Equipe',problem='Serviço')
            order.items.append(Item(kind='servico',description='Revisão',quantity=1,unit_price=Decimal('10.10')))
            order.checks.append(Check(stage='entrada',label='Pneus'))
            order.events.append(Event(user_id=1,description='Criada'))
            db.session.add(order)
        db.session.commit()


def test_list_query_count_does_not_grow_per_order(client,app):
    seed_orders(app,30)
    # Includes session user, pagination and related items. Each list must have
    # a fixed number of queries instead of one item/client query per OS.
    for path,budget in [('/',4),('/ordens',4),('/veiculos/1',5),('/ordens/nova',2),('/relatorios',6),('/relatorios/exportar',4)]:
        with queries(app) as statements:
            response=client.get(path)
        assert response.status_code==200,path
        assert len(statements)<=budget,(path,len(statements))
    page=client.get('/')
    assert 'R$ 10,10' in page.text
    assert '30' in page.text


def test_detail_history_users_loaded_together(client,app):
    seed_orders(app,1)
    with app.app_context():
        password=db.session.get(User,1).password_hash
        for i in range(20):
            user=User(username=f'actor-{i}',name=f'Pessoa {i}',password_hash=password)
            db.session.add(Event(order_id=1,user=user,description=f'Evento {i}'))
        db.session.commit()
    with queries(app) as statements:
        response=client.get('/ordens/1')
    assert response.status_code==200
    assert 'Pessoa 19' in response.text
    assert len(statements)<=6,len(statements)
