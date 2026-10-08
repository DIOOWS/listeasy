from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()
STATUSES = ['Aguardando avaliação', 'Aguardando aprovação', 'Aguardando peças', 'Em serviço', 'Pronto para entrega', 'Entregue', 'Cancelada']
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
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    document = db.Column(db.String(30), default='')
    phone = db.Column(db.String(40), default='')
    email = db.Column(db.String(150), default='')
    address = db.Column(db.String(300), default='')
    notes = db.Column(db.Text, default='')
    active = db.Column(db.Boolean, nullable=False, default=True)

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
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(50), unique=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('ecs_vehicles.id'), nullable=False, index=True)
    client_id = db.Column(db.Integer, db.ForeignKey('ecs_clients.id'), nullable=False)
    entry_date = db.Column(db.Date, nullable=False, index=True)
    due_date = db.Column(db.Date, nullable=False, index=True)
    delivered_date = db.Column(db.Date)
    mileage = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(40), nullable=False, default=STATUSES[0], index=True)
    responsible = db.Column(db.String(120), nullable=False)
    problem = db.Column(db.Text, nullable=False)
    diagnosis = db.Column(db.Text, default='')
    notes = db.Column(db.Text, default='')
    discount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal('0'))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    version = db.Column(db.Integer, nullable=False, default=1)
    __mapper_args__ = {'version_id_col': version}
    __table_args__ = (db.CheckConstraint('mileage >= 0 AND discount >= 0', name='ecs_order_nonnegative'), db.CheckConstraint('due_date >= entry_date', name='ecs_order_dates'))
    vehicle = db.relationship('Vehicle')
    client = db.relationship('Client')
    items = db.relationship('Item', back_populates='order', cascade='all, delete-orphan', order_by='Item.id')
    checks = db.relationship('Check', back_populates='order', cascade='all, delete-orphan', order_by='Check.id')
    events = db.relationship('Event', back_populates='order', cascade='all, delete-orphan', order_by='Event.created_at.desc()')
    photos = db.relationship('Photo', back_populates='order', cascade='all, delete-orphan', order_by='Photo.id')
    def subtotal(self, kind=None):
        return sum((x.total for x in self.items if kind is None or x.kind == kind), Decimal('0')).quantize(Decimal('0.01'))
    @property
    def total(self):
        return (self.subtotal() - self.discount).quantize(Decimal('0.01'))
    @property
    def closed(self):
        return self.status in ['Entregue', 'Cancelada']
    @property
    def service_progress(self):
        services = [x for x in self.items if x.kind == 'servico']
        return round(100 * sum(x.done for x in services) / len(services)) if services else 0

class Item(db.Model):
    __tablename__ = 'ecs_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('ecs_orders.id'), nullable=False, index=True)
    kind = db.Column(db.String(15), nullable=False)
    description = db.Column(db.String(200), nullable=False)
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
