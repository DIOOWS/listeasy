from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal, ROUND_HALF_UP
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()
STATUSES = ['Aguardando avaliação', 'Aguardando aprovação', 'Aprovado', 'Aguardando peças', 'Em serviço', 'Pronto para entrega', 'Entregue', 'Faturado', 'Recebido', 'Cancelada']
STATUS_MOVEMENTS = {
    'Aprovado': 'approved', 'Em serviço': 'started', 'Pronto para entrega': 'ready',
    'Entregue': 'delivered', 'Faturado': 'invoiced', 'Recebido': 'received',
}
WORKSHOP_ZONE = ZoneInfo('America/Sao_Paulo')
ENTRY_CHECKS = ['Quilometragem registrada', 'Pneus e rodas', 'Lataria e avarias', 'Luzes e sinalização', 'Acessórios e documentos', 'Estado interno do veículo']
EXIT_CHECKS = ['Serviços executados e conferidos', 'Funcionamento testado', 'Veículo liberado pelo responsável']

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(UserMixin, db.Model):
    __tablename__ = 'ecs_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='equipe')
    active = db.Column(db.Boolean, nullable=False, default=True)
    failures = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime)
    session_version = db.Column(db.Integer, nullable=False, default=1)
    __table_args__ = (db.CheckConstraint("role IN ('admin','equipe')", name='ecs_user_role'),)
    @property
    def is_active(self):
        return self.active
    def get_id(self):
        return f'{self.id}:{self.session_version}'
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Client(db.Model):
    __tablename__ = 'ecs_clients'
    logo_key = db.Column(db.String(64))
    logo_data = db.deferred(db.Column(db.LargeBinary))
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    document = db.Column(db.String(30), default='')
    phone = db.Column(db.String(40), default='')
    email = db.Column(db.String(150), default='')
    address = db.Column(db.String(300), default='')
    notes = db.Column(db.Text, default='')
    active = db.Column(db.Boolean, nullable=False, default=True)
    deleted_at = db.Column(db.DateTime, index=True)

class Vehicle(db.Model):
    __tablename__ = 'ecs_vehicles'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('ecs_clients.id'), nullable=False)
    plate = db.Column(db.String(10), nullable=False, unique=True)
    fleet = db.Column(db.String(40), default='')
    model = db.Column(db.String(120), nullable=False)
    year = db.Column(db.String(20), default='')
    notes = db.Column(db.Text, default='')
    active = db.Column(db.Boolean, nullable=False, default=True)
    client = db.relationship('Client')

class Order(db.Model):
    __tablename__ = 'ecs_orders'
    cover_key = db.Column(db.String(64))
    cover_data = db.deferred(db.Column(db.LargeBinary))
    id = db.Column(db.Integer, primary_key=True)
    parent_order_id = db.Column(db.Integer, db.ForeignKey('ecs_orders.id', name='fk_ecs_orders_parent'))
    number = db.Column(db.String(50), unique=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('ecs_vehicles.id'), nullable=True, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey('ecs_clients.id'), nullable=False)
    vehicle_plate = db.Column(db.String(10))
    vehicle_model = db.Column(db.String(120))
    vehicle_fleet = db.Column(db.String(40))
    entry_date = db.Column(db.Date, nullable=True, index=True)
    due_date = db.Column(db.Date, nullable=True, index=True)
    workshop_due_date = db.Column(db.Date, nullable=True)
    delivered_date = db.Column(db.Date)
    approved_date = db.Column(db.Date)
    started_date = db.Column(db.Date)
    ready_date = db.Column(db.Date)
    invoiced_date = db.Column(db.Date)
    received_date = db.Column(db.Date)
    entered_at = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    ready_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    invoiced_at = db.Column(db.DateTime)
    received_at = db.Column(db.DateTime)
    status_changed_at = db.Column(db.DateTime)
    finalized = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false(), index=True)
    mileage = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(40), nullable=False, default=STATUSES[0], index=True)
    responsible = db.Column(db.String(120), nullable=False)
    problem = db.Column(db.Text, nullable=False)
    diagnosis = db.Column(db.Text, default='')
    notes = db.Column(db.Text, default='')
    discount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal('0'))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    deleted_at = db.Column(db.DateTime, index=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {'version_id_col': version}
    __table_args__ = (db.CheckConstraint('mileage >= 0 AND discount >= 0', name='ecs_order_nonnegative'), db.CheckConstraint('due_date >= entry_date', name='ecs_order_dates'), db.UniqueConstraint('parent_order_id', name='uq_ecs_orders_parent'))
    vehicle = db.relationship('Vehicle')
    client = db.relationship('Client')
    items = db.relationship('Item', back_populates='order', cascade='all, delete-orphan', order_by='Item.id')
    checks = db.relationship('Check', back_populates='order', cascade='all, delete-orphan', order_by='Check.id')
    events = db.relationship('Event', back_populates='order', cascade='all, delete-orphan', order_by='Event.created_at.desc()')
    photos = db.relationship('Photo', back_populates='order', cascade='all, delete-orphan', order_by='Photo.id')
    @property
    def plate(self):
        return self.vehicle_plate if self.vehicle_plate is not None else self.vehicle.plate if self.vehicle else ''
    @property
    def model(self):
        return self.vehicle_model if self.vehicle_model is not None else self.vehicle.model if self.vehicle else ''
    @property
    def fleet(self):
        return self.vehicle_fleet if self.vehicle_fleet is not None else self.vehicle.fleet if self.vehicle else ''
    @property
    def status_tone(self):
        return {'Aguardando avaliação':'gray', 'Aguardando aprovação':'brown',
                'Aguardando peças':'orange', 'Em serviço':'blue', 'Aprovado':'amber', 'Faturado':'purple', 'Recebido':'indigo',
                'Pronto para entrega':'green', 'Entregue':'teal', 'Cancelada':'red'}.get(self.status,'gray')
    @property
    def flow_tone(self):
        return self.status_tone
    def subtotal(self, kind=None):
        return sum((x.total for x in self.items if kind is None or x.kind == kind), Decimal('0')).quantize(Decimal('0.01'))
    @property
    def total(self):
        return (self.subtotal() - self.discount).quantize(Decimal('0.01'))
    @property
    def closed(self):
        return bool(self.finalized)
    @property
    def service_progress(self):
        services = [x for x in self.items if x.kind == 'servico']
        return round(100 * sum(x.done for x in services) / len(services)) if services else 0

    @property
    def flow_status_date(self):
        movement = STATUS_MOVEMENTS.get(self.status)
        if movement:
            day = getattr(self, movement + '_date')
            if day:
                return day
        if self.status_changed_at:
            return self.status_changed_at.replace(tzinfo=timezone.utc).astimezone(WORKSHOP_ZONE).date()
        return self.entry_date

    @property
    def flow_steps(self):
        steps = [
            ('entry', 'Entrada', self.entry_date, self.entered_at),
            ('approved', 'Aprovação', self.approved_date, self.approved_at),
            ('started', 'Em serviço', self.started_date, self.started_at),
            ('ready', 'Pronto', self.ready_date, self.ready_at),
            ('delivered', 'Entregue', self.delivered_date, self.delivered_at),
            ('invoiced', 'Faturado', self.invoiced_date, self.invoiced_at),
            ('received', 'Recebido', self.received_date, self.received_at)]
        current = {'Aprovado': 'approved', 'Em serviço': 'started',
                   'Pronto para entrega': 'ready', 'Entregue': 'delivered',
                   'Faturado': 'invoiced', 'Recebido': 'received'}.get(self.status)
        return [dict(key=key, label=label, date=day, timestamp=stamp,
                     state=('current' if key == current else 'done') if day or stamp else 'pending')
                for key, label, day, stamp in steps]

    @property
    def flow_label(self):
        return self.status

class Item(db.Model):
    __tablename__ = 'ecs_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('ecs_orders.id'), nullable=False, index=True)
    kind = db.Column(db.String(15), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    service_type = db.Column(db.String(20))
    used_parts = db.Column(db.Text, default='')
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    responsible = db.Column(db.String(120), default='')
    done = db.Column(db.Boolean, nullable=False, default=False)
    order = db.relationship('Order', back_populates='items')
    __table_args__ = (db.CheckConstraint('quantity > 0 AND unit_price >= 0', name='ecs_item_nonnegative'), db.CheckConstraint("kind IN ('servico','peca')", name='ecs_item_kind'))
    @property
    def total(self):
        return (self.quantity * self.unit_price).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)

class Check(db.Model):
    __tablename__ = 'ecs_checks'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('ecs_orders.id'), nullable=False, index=True)
    stage = db.Column(db.String(10), nullable=False)
    label = db.Column(db.String(150), nullable=False)
    result = db.Column(db.String(20), nullable=False, default='pendente')
    notes = db.Column(db.String(500), default='')
    order = db.relationship('Order', back_populates='checks')
    __table_args__ = (db.CheckConstraint("stage IN ('entrada','saida')", name='ecs_check_stage'), db.CheckConstraint("result IN ('pendente','ok','avaria','na')", name='ecs_check_result'))

class Event(db.Model):
    __tablename__ = 'ecs_events'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('ecs_orders.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('ecs_users.id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    user = db.relationship('User')
    order = db.relationship('Order', back_populates='events')

class Photo(db.Model):
    __tablename__ = 'ecs_photos'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('ecs_orders.id'), nullable=False, index=True)
    public_id = db.Column(db.String(255), nullable=False)
    format = db.Column(db.String(10), nullable=False)
    stage = db.Column(db.String(10), nullable=False)
    caption = db.Column(db.String(200), default='')
    order = db.relationship('Order', back_populates='photos')
