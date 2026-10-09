import csv
import io
import re
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps
from urllib.parse import urlsplit, unquote
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session, send_file, current_app
from flask_login import current_user, login_user, logout_user, login_required
from sqlalchemy import or_, func
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, limiter, today
from .models import User, Client, Vehicle, Order, Item, Check, Event, Photo, STATUSES, ENTRY_CHECKS, EXIT_CHECKS, utcnow
from .forms import LoginForm, ClientForm, VehicleForm, OrderForm, ItemForm, StatusForm, PhotoForm, UserForm, FlowForm

web=Blueprint('web',__name__)
DUMMY_HASH=generate_password_hash('dummy-password-never-a-login')

def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args,**kwargs):
        if current_user.role!='admin':abort(403)
        return fn(*args,**kwargs)
    return wrapped

def event(order,message,invalidate_ready=True):
    if invalidate_ready and order.status=='Pronto para entrega':
        order.status='Em serviço'
        order.ready_date=None
        db.session.add(Event(order=order,user_id=current_user.id,description='OS retornou a Em serviço após alteração da ficha.'))
    db.session.add(Event(order=order,user_id=current_user.id,description=message))
    order.updated_at=utcnow()

def mutable(order):
    if order.closed:
        abort(409,description='OS encerrada. Reabra a OS antes de alterar os dados.')
    submitted=request.form.get('version')
    if submitted is None or submitted!=str(order.version):
        abort(409,description='A OS foi alterada. Atualize a página e tente novamente.')

def order_choices(form,order=None):
    condition=Vehicle.active.is_(True)
    if order:condition=or_(condition,Vehicle.id==order.vehicle_id)
    vehicles=db.session.scalars(db.select(Vehicle).where(condition).order_by(Vehicle.plate)).all()
    form.vehicle_id.choices=[(v.id,f'{v.plate} · {v.model} · {v.client.name}') for v in vehicles]

def validate_order(form,order=None):
    if form.due_date.data<form.entry_date.data:
        form.due_date.errors.append('A entrega prevista deve ser igual ou posterior à entrada.');return False
    if order and any(value and value<form.entry_date.data for value in [order.approved_date, order.started_date, order.ready_date, order.delivered_date, order.invoiced_date, order.received_date]):
        form.entry_date.errors.append('A entrada não pode ser posterior às etapas já registradas.');return False
    vehicle=db.session.get(Vehicle,form.vehicle_id.data)
    if order and vehicle.id!=order.vehicle_id:
        form.vehicle_id.errors.append('O veículo de uma OS já criada não pode ser trocado.');return False
    if not order and (not vehicle.active or not vehicle.client.active):
        form.vehicle_id.errors.append('O veículo e seu cliente precisam estar ativos.');return False
    number=(form.number.data or '').strip().upper()
    existing=db.session.scalar(db.select(Order).where(Order.number==number)) if number else None
    if existing and (not order or existing.id!=order.id):
        form.number.errors.append('Este número de OS já está em uso.');return False
    if form.discount.data>(order.subtotal() if order else 0):
        form.discount.errors.append('O desconto não pode superar o valor dos serviços e peças.');return False
    return True

@web.route('/login',methods=['GET','POST'])
@limiter.limit('10 per minute')
def login():
    if current_user.is_authenticated:return redirect(url_for('web.dashboard'))
    form=LoginForm()
    if form.validate_on_submit():
        username=form.username.data.strip().lower()
        user=db.session.scalar(db.select(User).where(User.username==username).with_for_update())
        valid=user.check_password(form.password.data) if user else check_password_hash(DUMMY_HASH,form.password.data)
        if user and user.active and valid and (not user.locked_until or user.locked_until<=utcnow()):
            user.failures=0;user.locked_until=None;db.session.commit()
            session.clear();login_user(user,remember=False);session.permanent=True
            target=request.args.get('next','')
            parsed=urlsplit(target)
            return redirect(target if target.startswith('/') and not target.startswith('//') and not parsed.netloc and not parsed.scheme and '\\' not in target else url_for('web.dashboard'))
        if user and (not user.locked_until or user.locked_until<=utcnow()):
            user.failures+=1
            if user.failures>=5:user.locked_until=utcnow()+timedelta(minutes=15);user.failures=0
            db.session.commit()
        else:db.session.rollback()
        flash('Usuário ou senha inválidos, ou acesso temporariamente bloqueado.','error')
    return render_template('login.html',form=form)

@web.post('/logout')
@login_required
def logout():
    logout_user();session.clear();return redirect(url_for('web.login'))

@web.get('/')
@login_required
def dashboard():
    active=~Order.status.in_(['Entregue','Cancelada'])
    counts={'open':db.session.scalar(db.select(func.count(Order.id)).where(active)),
        'today':db.session.scalar(db.select(func.count(Order.id)).where(active,Order.due_date==today())),
        'late':db.session.scalar(db.select(func.count(Order.id)).where(active,Order.due_date<today()))}
    pending_finance=(Order.status=='Entregue') & Order.received_date.is_(None)
    orders=db.session.scalars(db.select(Order).where(or_(active,pending_finance)).options(db.joinedload(Order.vehicle),db.joinedload(Order.client)).order_by(active.desc(),Order.due_date,Order.id).limit(12)).all()
    finance_count=db.session.scalar(db.select(func.count(Order.id)).where(pending_finance))
    return render_template('dashboard.html',orders=orders,counts=counts,finance_count=finance_count)

@web.get('/clientes')
@login_required
def clients():
    q=request.args.get('q','').strip()[:150]
    query=db.select(Client)
    if q:query=query.where(Client.name.ilike('%'+q+'%'))
    page=db.paginate(query.order_by(Client.name),per_page=30,error_out=False)
    return render_template('clients.html',page=page,q=q)

@web.route('/clientes/novo',methods=['GET','POST'])
@web.route('/clientes/<int:ident>/editar',methods=['GET','POST'])
@login_required
def client_form(ident=None):
    obj=db.get_or_404(Client,ident) if ident else Client()
    form=ClientForm(obj=obj if ident else None)
    if form.validate_on_submit():
        form.populate_obj(obj);obj.name=obj.name.strip();db.session.add(obj);db.session.commit()
        flash('Cliente salvo.','success');return redirect(url_for('web.clients'))
    return render_template('form.html',form=form,title='Editar cliente' if ident else 'Novo cliente',back=url_for('web.clients'))

@web.get('/veiculos')
@login_required
def vehicles():
    q=request.args.get('q','').strip()[:150]
    query=db.select(Vehicle).join(Client).options(db.joinedload(Vehicle.client))
    if q:query=query.where(or_(Vehicle.plate.ilike('%'+q+'%'),Vehicle.fleet.ilike('%'+q+'%'),Vehicle.model.ilike('%'+q+'%'),Client.name.ilike('%'+q+'%')))
    page=db.paginate(query.order_by(Vehicle.plate),per_page=30,error_out=False)
    return render_template('vehicles.html',page=page,q=q)

@web.route('/veiculos/novo',methods=['GET','POST'])
@web.route('/veiculos/<int:ident>/editar',methods=['GET','POST'])
@login_required
def vehicle_form(ident=None):
    obj=db.get_or_404(Vehicle,ident) if ident else Vehicle()
    form=VehicleForm(obj=obj if ident else None)
    clients=db.session.scalars(db.select(Client).where(or_(Client.active.is_(True),Client.id==obj.client_id)).order_by(Client.name)).all()
    form.client_id.choices=[(c.id,c.name) for c in clients]
    if form.validate_on_submit():
        plate=re.sub(r'[^A-Z0-9]','',form.plate.data.upper())
        if not re.fullmatch(r'[A-Z]{3}[0-9][A-Z0-9][0-9]{2}',plate):
            form.plate.errors.append('Informe uma placa brasileira válida, antiga ou Mercosul.')
        elif db.session.scalar(db.select(Vehicle).where(Vehicle.plate==plate,Vehicle.id!=(ident or 0))):
            form.plate.errors.append('Esta placa já foi cadastrada.')
        else:
            form.populate_obj(obj);obj.plate=plate;db.session.add(obj);db.session.commit()
            flash('Veículo salvo.','success');return redirect(url_for('web.vehicles'))
    return render_template('form.html',form=form,title='Editar veículo' if ident else 'Novo veículo',back=url_for('web.vehicles'),empty=not clients,empty_message='Cadastre um cliente ativo antes do veículo.')

@web.get('/veiculos/<int:ident>')
@login_required
def vehicle_history(ident):
    vehicle=db.get_or_404(Vehicle,ident)
    page=db.paginate(db.select(Order).where(Order.vehicle_id==ident).order_by(Order.entry_date.desc(),Order.id.desc()),per_page=30,error_out=False)
    return render_template('orders.html',page=page,title=f'Histórico · {vehicle.plate}',q='',status='',vehicle=vehicle)

def filtered_orders():
    query=db.select(Order).join(Vehicle).join(Client,Order.client_id==Client.id).options(db.joinedload(Order.vehicle),db.joinedload(Order.client))
    q=request.args.get('q','').strip()[:150];status=request.args.get('status','')
    if q:query=query.where(or_(Order.number.ilike('%'+q+'%'),Vehicle.plate.ilike('%'+q+'%'),Vehicle.fleet.ilike('%'+q+'%'),Client.name.ilike('%'+q+'%')))
    if status in STATUSES:query=query.where(Order.status==status)
    if request.args.get('open')=='1':query=query.where(~Order.status.in_(['Entregue','Cancelada']))
    if request.args.get('finance')=='1':query=query.where(Order.status=='Entregue',Order.received_date.is_(None))
    if request.args.get('due')=='today':query=query.where(Order.due_date==today(),~Order.status.in_(['Entregue','Cancelada']))
    if request.args.get('due')=='late':query=query.where(Order.due_date<today(),~Order.status.in_(['Entregue','Cancelada']))
    for key,operator in [('start',lambda d:Order.entry_date>=d),('end',lambda d:Order.entry_date<=d)]:
        raw=request.args.get(key)
        if raw:
            try:query=query.where(operator(date.fromisoformat(raw)))
            except ValueError:abort(400,description='Data de filtro inválida.')
    return query.order_by(Order.entry_date.desc(),Order.id.desc())

@web.get('/ordens')
@login_required
def orders():
    page=db.paginate(filtered_orders(),per_page=25,error_out=False)
    return render_template('orders.html',page=page,title='Ordens de serviço',q=request.args.get('q',''),status=request.args.get('status',''),vehicle=None)

@web.route('/ordens/nova',methods=['GET','POST'])
@login_required
def order_new():
    form=OrderForm(entry_date=today(),due_date=today(),responsible=current_user.name)
    order_choices(form)
    if form.validate_on_submit() and validate_order(form):
        order=Order();form.populate_obj(order);order.number=(form.number.data or '').strip().upper() or None
        vehicle=db.session.get(Vehicle,form.vehicle_id.data);order.client_id=vehicle.client_id
        db.session.add(order);db.session.flush()
        if not order.number:order.number=f'OS-{order.created_at.year}-{order.id:06d}'
        for stage,labels in [('entrada',ENTRY_CHECKS),('saida',EXIT_CHECKS)]:
            for label in labels:db.session.add(Check(order=order,stage=stage,label=label))
        event(order,'OS criada.');db.session.commit()
        flash('OS criada. Agora adicione os serviços e as peças.','success')
        return redirect(url_for('web.order_detail',ident=order.id))
    return render_template('form.html',form=form,title='Nova ordem de serviço',back=url_for('web.orders'),empty=not form.vehicle_id.choices,empty_message='Cadastre um cliente e um veículo ativo antes de abrir uma OS.')

@web.route('/ordens/<int:ident>/editar',methods=['GET','POST'])
@login_required
def order_edit(ident):
    order=db.get_or_404(Order,ident)
    if order.closed:abort(409,description='Reabra a OS antes de editar.')
    form=OrderForm(obj=order);order_choices(form,order)
    if request.method=='GET':form.version.data=str(order.version)
    if form.validate_on_submit():
        mutable(order)
        if validate_order(form,order):
            number=(form.number.data or order.number).strip().upper();form.populate_obj(order);order.number=number;order.version=int(request.form['version'])
            event(order,'Dados da OS atualizados.');db.session.commit();flash('OS atualizada.','success')
            return redirect(url_for('web.order_detail',ident=ident))
    return render_template('form.html',form=form,title=f'Editar {order.number}',back=url_for('web.order_detail',ident=ident))

@web.get('/ordens/<int:ident>')
@login_required
def order_detail(ident):
    order=db.get_or_404(Order,ident)
    status_form=StatusForm(status=order.status,version=str(order.version),delivered_date=order.delivered_date or today());status_form.status.choices=[(x,x) for x in STATUSES]
    flow_form=FlowForm(version=str(order.version),action_date=today())
    if current_user.role=='admin':
        flow_form.action.choices += [('clear_approval','Corrigir: remover aprovação'),('clear_invoice','Corrigir: remover faturamento'),('clear_received','Corrigir: remover recebimento')]
    return render_template('order.html',order=order,status_form=status_form,flow_form=flow_form,item_form=ItemForm(version=str(order.version)),photo_form=PhotoForm(version=str(order.version)),photos_enabled=bool(current_app.config['CLOUDINARY_URL']))

@web.post('/ordens/<int:ident>/fluxo')
@login_required
def order_flow(ident):
    order=db.get_or_404(Order,ident)
    form=FlowForm()
    if current_user.role=='admin':
        form.action.choices += [('clear_approval','Remover aprovação'),('clear_invoice','Remover faturamento'),('clear_received','Remover recebimento')]
    if not form.validate_on_submit():abort(400,description='Etapa ou data inválida.')
    if form.version.data!=str(order.version):abort(409,description='A OS foi alterada. Atualize a página e tente novamente.')
    action=form.action.data;value=form.action_date.data;reference=(form.reference.data or '').strip()
    def fail(message):
        flash(message,'error');return redirect(url_for('web.order_detail',ident=ident))
    if order.status=='Cancelada':return fail('Uma OS cancelada não pode receber novas etapas. Reabra a OS primeiro.')
    if value<order.entry_date or value>today():return fail('A data deve estar entre a entrada e hoje.')
    fields={'approve':('approved_date','Aprovação'),'invoice':('invoiced_date','Faturamento'),'receive':('received_date','Recebimento')}
    if action.startswith('clear_'):
        if current_user.role!='admin':abort(403)
        if not reference:return fail('Informe o motivo da correção na observação.')
        field,label={'clear_approval':('approved_date','Aprovação'),'clear_invoice':('invoiced_date','Faturamento'),'clear_received':('received_date','Recebimento')}[action]
        if action=='clear_invoice' and order.received_date:return fail('Remova o recebimento antes de corrigir o faturamento.')
        previous=getattr(order,field)
        if not previous:return fail('Esta etapa ainda não foi registrada.')
        setattr(order,field,None)
        message=f'{label} removido para correção (data anterior {previous:%d/%m/%Y}). Motivo: {reference}'
    else:
        field,label=fields[action]
        if getattr(order,field):return fail('Esta etapa já está registrada. Um administrador pode corrigir o registro.')
        if action=='approve':
            if any(d and value>d for d in [order.started_date,order.ready_date,order.delivered_date]):return fail('A aprovação não pode ser posterior ao início do serviço ou à entrega já registrada.')
        elif action=='invoice':
            if order.status!='Entregue' or not order.delivered_date:return fail('Registre a entrega antes do faturamento.')
            if value<order.delivered_date:return fail('O faturamento não pode ser anterior à entrega.')
        elif action=='receive':
            if order.status!='Entregue' or not order.invoiced_date:return fail('Registre o faturamento antes do recebimento.')
            if value<order.invoiced_date:return fail('O recebimento não pode ser anterior ao faturamento.')
        setattr(order,field,value)
        message=f'{label} registrado em {value:%d/%m/%Y}.'+(f' Referência: {reference}' if reference else '')
    event(order,message,invalidate_ready=False);db.session.commit()
    flash('Fluxo atualizado.','success');return redirect(url_for('web.order_detail',ident=ident))

@web.post('/ordens/<int:ident>/status')
@login_required
def order_status(ident):
    order=db.get_or_404(Order,ident)
    form=StatusForm();form.status.choices=[(x,x) for x in STATUSES]
    if not form.validate_on_submit():abort(400,description='Status ou data inválidos.')
    if request.form.get('version')!=str(order.version):abort(409,description='A OS foi alterada. Atualize a página.')
    target=form.status.data
    if order.closed and current_user.role!='admin':abort(403)
    if target==order.status:return redirect(url_for('web.order_detail',ident=ident))
    if target in ['Em serviço','Pronto para entrega'] and order.entry_date>today():
        flash('A entrada precisa ter ocorrido antes de iniciar ou concluir o atendimento.','error');return redirect(url_for('web.order_detail',ident=ident))
    if order.invoiced_date or order.received_date:
        flash('Corrija os registros financeiros antes de reabrir ou cancelar esta OS.','error');return redirect(url_for('web.order_detail',ident=ident))
    if target in ['Pronto para entrega','Entregue']:
        services=[x for x in order.items if x.kind=='servico']
        if not services or not all(x.done for x in services):
            flash('Adicione e conclua todos os serviços antes de liberar o veículo.','error');return redirect(url_for('web.order_detail',ident=ident))
        if any(x.result=='pendente' for x in order.checks if x.stage=='entrada'):
            flash('Finalize o checklist de entrada antes de liberar o veículo.','error');return redirect(url_for('web.order_detail',ident=ident))
        if any(x.result!='ok' for x in order.checks if x.stage=='saida'):
            flash('Todos os itens do checklist de entrega devem estar OK.','error');return redirect(url_for('web.order_detail',ident=ident))
    if target=='Entregue':
        delivery=form.delivered_date.data
        if not delivery or delivery<order.entry_date or delivery>today():
            flash('A entrega deve ser entre a entrada e a data de hoje.','error');return redirect(url_for('web.order_detail',ident=ident))
        if any(d and delivery<d for d in [order.approved_date,order.started_date,order.ready_date]):
            flash('A entrega não pode ser anterior às etapas já registradas.','error');return redirect(url_for('web.order_detail',ident=ident))
        order.delivered_date=delivery
    else:order.delivered_date=None
    if target=='Em serviço' and not order.started_date:order.started_date=today()
    if target=='Pronto para entrega':order.ready_date=today()
    elif target!='Entregue':order.ready_date=None
    previous=order.status;order.status=target
    event(order,f'Status: {previous} → {target}'+(f'. Entrega em {order.delivered_date:%d/%m/%Y}.' if order.delivered_date else '.'),invalidate_ready=False)
    db.session.commit();flash('Status atualizado.','success');return redirect(url_for('web.order_detail',ident=ident))

@web.post('/ordens/<int:ident>/checklist')
@login_required
def checklist(ident):
    order=db.get_or_404(Order,ident);mutable(order)
    stage=request.form.get('stage')
    if stage not in ['entrada','saida']:abort(400)
    for check in order.checks:
        if check.stage!=stage:continue
        result=request.form.get(f'result_{check.id}','pendente');notes=request.form.get(f'notes_{check.id}','').strip()
        if result not in (['pendente','ok','avaria','na'] if stage=='entrada' else ['pendente','ok']) or len(notes)>500:abort(400)
        if result=='avaria' and not notes:
            flash('Descreva as avarias nos itens marcados com atenção.','error');db.session.rollback();return redirect(url_for('web.order_detail',ident=ident))
        check.result=result;check.notes=notes
    event(order,f'Checklist de {"entrada" if stage=="entrada" else "entrega"} atualizado.');db.session.commit()
    flash('Checklist salvo.','success');return redirect(url_for('web.order_detail',ident=ident))

@web.post('/ordens/<int:ident>/itens')
@login_required
def item_add(ident):
    order=db.get_or_404(Order,ident);mutable(order);form=ItemForm()
    if not form.validate_on_submit():
        flash('Confira descrição, quantidade e valor do item.','error');return redirect(url_for('web.order_detail',ident=ident))
    item=Item(order=order);form.populate_obj(item)
    event(order,f'Adicionado {"serviço" if item.kind=="servico" else "peça"}: {item.description}.');db.session.add(item);db.session.commit()
    flash('Item adicionado.','success');return redirect(url_for('web.order_detail',ident=ident))

@web.route('/ordens/<int:ident>/itens/<int:item_id>/editar',methods=['GET','POST'])
@login_required
def item_edit(ident,item_id):
    order=db.get_or_404(Order,ident);item=db.get_or_404(Item,item_id)
    if item.order_id!=ident:abort(404)
    if order.closed:abort(409,description='Reabra a OS antes de editar.')
    form=ItemForm(obj=item)
    if request.method=='GET':form.version.data=str(order.version)
    if form.validate_on_submit():
        mutable(order)
        proposed=(form.quantity.data*form.unit_price.data).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
        if order.subtotal()-item.total+proposed<order.discount:
            form.unit_price.errors.append('O subtotal não pode ficar abaixo do desconto.')
        else:
            form.populate_obj(item);event(order,f'Item atualizado: {item.description}.');db.session.commit()
            flash('Item atualizado.','success');return redirect(url_for('web.order_detail',ident=ident))
    return render_template('form.html',form=form,title='Editar serviço / peça',back=url_for('web.order_detail',ident=ident))

@web.post('/ordens/<int:ident>/itens/<int:item_id>/acao')
@login_required
def item_action(ident,item_id):
    order=db.get_or_404(Order,ident);mutable(order);item=db.get_or_404(Item,item_id)
    if item.order_id!=ident:abort(404)
    action=request.form.get('action')
    if action=='remove':
        if order.subtotal()-item.total<order.discount:
            flash('Reduza o desconto antes de remover este item.','error');return redirect(url_for('web.order_detail',ident=ident))
        event(order,f'Item removido: {item.description}.');db.session.delete(item)
    elif action=='toggle':
        item.done=not item.done;event(order,f'Item {"concluído" if item.done else "reaberto"}: {item.description}.')
    else:abort(400)
    db.session.commit();return redirect(url_for('web.order_detail',ident=ident))

def configure_photos():
    import cloudinary
    parsed=urlsplit(current_app.config['CLOUDINARY_URL'])
    if parsed.scheme!='cloudinary' or not parsed.hostname or not parsed.username or not parsed.password:
        raise RuntimeError('CLOUDINARY_URL inválida.')
    cloudinary.config(cloud_name=parsed.hostname,api_key=unquote(parsed.username),api_secret=unquote(parsed.password),secure=True)

@web.post('/ordens/<int:ident>/fotos')
@login_required
@limiter.limit('20 per hour')
def photo_add(ident):
    order=db.get_or_404(Order,ident);mutable(order)
    if not current_app.config['CLOUDINARY_URL']:
        flash('Configure o armazenamento de fotos para habilitar os anexos.','error');return redirect(url_for('web.order_detail',ident=ident))
    form=PhotoForm()
    if not form.validate_on_submit():abort(400)
    from PIL import Image, UnidentifiedImageError
    import cloudinary
    import cloudinary.uploader
    file=form.file.data
    try:
        img=Image.open(file.stream)
        if img.format not in ['JPEG','PNG','WEBP'] or img.width*img.height>25000000:raise ValueError()
        img.verify();file.stream.seek(0)
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError):
        flash('Envie uma imagem JPEG, PNG ou WebP válida, com até 25 megapixels.','error');return redirect(url_for('web.order_detail',ident=ident))
    configure_photos()
    try:
        uploaded=cloudinary.uploader.upload(file.stream,folder=f'easy-servicos/os-{ident}',type='authenticated',resource_type='image',allowed_formats=['jpg','jpeg','png','webp'],timeout=30)
    except Exception:
        current_app.logger.warning('Falha no envio da foto para o armazenamento externo.')
        flash('Não foi possível enviar a foto. Tente novamente.','error');return redirect(url_for('web.order_detail',ident=ident))
    db.session.add(Photo(order=order,public_id=uploaded['public_id'],format=uploaded['format'],stage=form.stage.data,caption=form.caption.data))
    event(order,f'Foto de {form.stage.data} anexada.');
    try:db.session.commit()
    except Exception:
        db.session.rollback()
        try:cloudinary.uploader.destroy(uploaded['public_id'],type='authenticated',resource_type='image')
        except Exception:current_app.logger.warning('Falha ao limpar foto órfã.')
        raise
    flash('Foto anexada.','success');return redirect(url_for('web.order_detail',ident=ident))

@web.get('/fotos/<int:ident>')
@login_required
def photo_view(ident):
    photo=db.get_or_404(Photo,ident)
    if not current_app.config['CLOUDINARY_URL']:abort(404)
    import cloudinary
    import cloudinary.utils
    import requests
    configure_photos()
    url=cloudinary.utils.private_download_url(photo.public_id,photo.format,resource_type='image',type='authenticated',expires_at=int(datetime.now().timestamp())+60,attachment=False)
    try:
        response=requests.get(url,timeout=20)
        response.raise_for_status()
        mime=response.headers.get('Content-Type','').split(';')[0]
        if mime not in ['image/jpeg','image/png','image/webp']:abort(502)
        return send_file(io.BytesIO(response.content),mimetype=mime)
    except requests.RequestException:abort(502)

@web.get('/relatorios')
@login_required
def reports():
    page=db.paginate(filtered_orders(),per_page=30,error_out=False)
    # Aggregate all filtered records, not just the current page.
    ids=filtered_orders().with_only_columns(Order.id).order_by(None).subquery()
    item_total=db.session.execute(db.select(Item.kind,func.sum(func.round(Item.quantity*Item.unit_price,2))).where(Item.order_id.in_(db.select(ids.c.id))).group_by(Item.kind)).all()
    totals={kind:Decimal(str(value)).quantize(Decimal('0.01')) for kind,value in item_total};discount=db.session.scalar(db.select(func.sum(Order.discount)).where(Order.id.in_(db.select(ids.c.id)))) or Decimal('0')
    labor=totals.get('servico',Decimal('0'));parts=totals.get('peca',Decimal('0'))
    return render_template('reports.html',page=page,labor=labor,parts=parts,discount=discount,total=labor+parts-discount,q=request.args.get('q',''),status=request.args.get('status',''))

def safe_cell(value):
    if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):return "'"+value
    return value

@web.get('/relatorios/exportar')
@login_required
def report_export():
    from openpyxl import Workbook
    rows=db.session.scalars(filtered_orders().limit(10001)).all()
    if len(rows)>10000:abort(400,description='Filtre o período para exportar até 10 mil OS.')
    book=Workbook();sheet=book.active;sheet.title='Ordens de serviço'
    sheet.append(['OS','Cliente','Placa','Frota','Entrada','Previsão entrega','Entrega real','Status','Serviços','Peças','Desconto','Total','Aprovação','Início do serviço','Pronto','Faturamento','Recebimento','Etapa do fluxo'])
    items=book.create_sheet('Serviços e peças');items.append(['OS','Tipo','Descrição','Quantidade','Valor unitário','Total','Responsável','Concluído'])
    checks=book.create_sheet('Checklist');checks.append(['OS','Etapa','Item','Resultado','Observações'])
    for order in rows:
        sheet.append([safe_cell(x) for x in [order.number,order.client.name,order.vehicle.plate,order.vehicle.fleet,order.entry_date,order.due_date,order.delivered_date,order.status,order.subtotal('servico'),order.subtotal('peca'),order.discount,order.total,order.approved_date,order.started_date,order.ready_date,order.invoiced_date,order.received_date,order.flow_label]])
        for item in order.items:items.append([safe_cell(x) for x in [order.number,item.kind,item.description,item.quantity,item.unit_price,item.total,item.responsible,'Sim' if item.done else 'Não']])
        for check in order.checks:checks.append([safe_cell(x) for x in [order.number,check.stage,check.label,check.result,check.notes]])
    from openpyxl.styles import Font, PatternFill
    for ws in book:
        ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
        for cell in ws[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='125B75')
        for col in ws.columns:
            width=min(55,max(16,max(len(str(c.value or '')) for c in col)+2));ws.column_dimensions[col[0].column_letter].width=width
            for cell in col[1:]:
                if isinstance(cell.value,date):cell.number_format='dd/mm/yyyy'
        money_cols=[9,10,11,12] if ws==sheet else [5,6] if ws==items else []
        for n in money_cols:
            for col in ws.iter_cols(min_col=n,max_col=n,min_row=2):
                for cell in col:cell.number_format='"R$" #,##0.00'
    output=io.BytesIO();book.save(output);output.seek(0)
    return send_file(output,as_attachment=True,download_name=f'relatorio-servicos-{today()}.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@web.get('/ordens/<int:ident>/imprimir')
@login_required
def order_print(ident):
    return render_template('print.html',order=db.get_or_404(Order,ident))

@web.get('/usuarios')
@admin_required
def users():
    return render_template('users.html',users=db.session.scalars(db.select(User).order_by(User.name)).all())

@web.route('/usuarios/novo',methods=['GET','POST'])
@web.route('/usuarios/<int:ident>/editar',methods=['GET','POST'])
@admin_required
def user_form(ident=None):
    obj=db.get_or_404(User,ident) if ident else User()
    form=UserForm(obj=obj if ident else None)
    if form.validate_on_submit():
        username=form.username.data.strip().lower()
        if not ident and not form.password.data:form.password.errors.append('Defina a senha inicial.')
        elif db.session.scalar(db.select(User).where(User.username==username,User.id!=(ident or 0))):form.username.errors.append('Usuário já existe.')
        elif ident==current_user.id and (not form.active.data or form.role.data!='admin'):
            form.role.errors.append('Você não pode remover seu próprio acesso de administrador.')
        else:
            changed=ident and (obj.role!=form.role.data or obj.active!=form.active.data or bool(form.password.data))
            obj.username=username;obj.name=form.name.data.strip();obj.role=form.role.data;obj.active=form.active.data
            if form.password.data:obj.set_password(form.password.data);obj.failures=0;obj.locked_until=None
            if changed:obj.session_version+=1
            db.session.add(obj);db.session.commit()
            if ident==current_user.id and changed:login_user(obj)
            flash('Usuário salvo.','success');return redirect(url_for('web.users'))
    return render_template('form.html',form=form,title='Editar usuário' if ident else 'Novo usuário',back=url_for('web.users'))


@web.get('/sw.js')
@limiter.exempt
def service_worker():
    response=current_app.send_static_file('sw.js')
    response.headers['Service-Worker-Allowed']='/'
    response.headers['Cache-Control']='no-cache'
    return response

@web.get('/instalar')
@login_required
def install():
    return render_template('install.html')
