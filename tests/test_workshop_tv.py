from datetime import timedelta

from easy import today
from easy.models import Order, db
from test_app import app, client, create_order, version


def test_tv_follows_workshop_changes(client, app):
    assert app.test_client().get('/modo-tv/dados').status_code == 302
    ident = create_order(client, app)
    with app.app_context():
        order = db.session.get(Order, ident)
        order.entry_date = today() - timedelta(days=3)
        order.due_date = today() - timedelta(days=1)
        db.session.commit()
    assert 'Modo TV' in client.get('/').text
    assert 'workshop_tv.js' in client.get('/modo-tv').text
    response = client.get('/modo-tv/dados')
    assert response.headers['Cache-Control'] == 'no-store'
    data = response.get_json()
    assert (data['open'], data['late']) == (1, 1)
    assert all(value in data['html'] for value in ['ABC1D23', 'Ducato', 'Diogo', 'Atrasada'])
    assert client.post(f'/ordens/{ident}/status', data={
        'status': 'Entregue', 'version': version(app, ident)
    }).status_code == 302
    data = client.get('/modo-tv/dados').get_json()
    assert (data['open'], data['late']) == (0, 0)
    assert 'ABC1D23' not in data['html']


def test_tv_expansion_is_read_only_and_admin_sees_actual_deadline(client, app):
    ident = create_order(client, app)
    with app.app_context():
        order = db.session.get(Order, ident)
        order.due_date = today() + timedelta(days=1)
        order.notes = 'Observação <reservada>'
        db.session.commit()
    url = f'/modo-tv/os/{ident}'
    assert app.test_client().get(url).status_code == 302
    assert client.post(url).status_code == 405
    details = client.get(url)
    assert details.status_code == 200
    assert details.headers['Cache-Control'] == 'no-store'
    assert 'Observação &lt;reservada&gt;' in details.text
    assert (today() + timedelta(days=1)).strftime('%d/%m/%Y') in details.text
    assert '<form' not in details.text
    cards = client.get('/modo-tv/dados').get_json()
    assert cards['late'] == 0
    assert f'data-url="{url}"' in cards['html']
    assert (today() + timedelta(days=1)).strftime('%d/%m/%Y') in cards['html']
    assert "Observação &lt;reservada&gt;" in cards["html"]
    assert "data-close-order" in cards["html"]


def test_team_uses_read_only_tv_with_workshop_deadline(client, app):
    ident = create_order(client, app)
    real_due = today() + timedelta(days=1)
    workshop_due = today() - timedelta(days=1)
    with app.app_context():
        order = db.session.get(Order, ident)
        order.due_date = real_due
        db.session.commit()

    edit_url = f'/ordens/{ident}/editar'
    assert 'Prazo da oficina (opcional)' in client.get(edit_url).text
    assert client.post(edit_url, data={
        'client_id': 1, 'due_date': real_due.isoformat(),
        'workshop_due_date': workshop_due.isoformat(), 'version': version(app, ident)
    }).status_code == 302
    assert client.get('/modo-tv/dados').get_json()['late'] == 0

    team = app.test_client()
    assert team.post('/login?next=/ordens/nova', data={
        'username': 'team', 'password': 'strong-password-123'
    }).location == '/modo-tv'
    assert team.get('/').location == '/modo-tv'
    assert team.get('/login').location == '/modo-tv'
    panel = team.get('/modo-tv').text
    assert 'Sair' in panel and 'Voltar' not in panel
    for path in ('/ordens', f'/ordens/{ident}/editar', '/clientes', '/relatorios/exportar'):
        assert team.get(path).status_code == 403
    for path in (f'/ordens/{ident}/editar', f'/ordens/{ident}/status'):
        assert team.post(path).status_code == 403
    cards = team.get('/modo-tv/dados').get_json()
    assert cards['late'] == 1 and 'status-red overdue' in cards['html']
    assert 'Prazo de entrega' in cards['html']
    assert 'Prazo da oficina' not in cards['html']
    details = team.get(f'/modo-tv/os/{ident}').text
    assert workshop_due.strftime('%d/%m/%Y') in details
    assert real_due.strftime('%d/%m/%Y') not in details
    assert 'Programar prazo' not in details
    assert 'Programar prazo' not in client.get(f'/modo-tv/os/{ident}').text
    assert workshop_due.isoformat() in client.get(edit_url).text
    assert client.post(edit_url, data={
        'client_id': 1, 'due_date': real_due.isoformat(), 'workshop_due_date': '',
        'version': version(app, ident),
    }).status_code == 302
    assert real_due.strftime('%d/%m/%Y') in team.get(f'/modo-tv/os/{ident}').text
    assert team.post('/logout').location == '/login'
    assert team.get('/modo-tv').status_code == 302
