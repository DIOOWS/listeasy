from easy.models import db,Order,STATUSES
from test_app import app,client,create_order,version


def test_delete_service_in_every_status_without_moving_flow(client,app):
    ident=create_order(client,app)
    for status in STATUSES:
        assert client.post(f'/ordens/{ident}/status',data={'status':status,'version':version(app,ident)}).status_code==302
        assert client.post(f'/ordens/{ident}/servicos',data={'service_type':'estrutura','used_parts':'Banco','responsible':'Erick','version':version(app,ident)}).status_code==302
        with app.app_context():
            order=db.session.get(Order,ident);item_id=order.items[-1].id;stamp=order.status_changed_at
        page=client.get(f'/ordens/{ident}').text
        assert f'/ordens/{ident}/itens/{item_id}/acao' in page
        assert 'disabled' not in page.split('<fieldset>')[1].split('</fieldset>')[0]
        assert client.post(f'/ordens/{ident}/itens/{item_id}/acao',data={'action':'remove','version':version(app,ident)},follow_redirects=True).status_code==200
        with app.app_context():
            order=db.session.get(Order,ident)
            assert not order.items and order.status==status and order.status_changed_at==stamp


def test_record_received_directly_does_not_complete_previous_phases(client,app):
    ident=create_order(client,app)
    client.post(f'/ordens/{ident}/status',data={'status':'Recebido','version':version(app,ident)})
    with app.app_context():
        order=db.session.get(Order,ident)
        assert order.flow_label=='Recebido'
        assert order.flow_steps[6]['state']=='current'
        assert all(step['state']=='pending' for step in order.flow_steps[1:6])
        assert order.delivered_date is None and order.invoiced_date is None
    client.post(f'/ordens/{ident}/status',data={'status':'Em serviço','version':version(app,ident)})
    with app.app_context():
        order=db.session.get(Order,ident)
        assert order.flow_label=='Em serviço' and order.flow_steps[2]['state']=='current'
        assert order.received_date is not None
