from decimal import Decimal
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import StringField, PasswordField, TextAreaField, SelectField, DateField, IntegerField, DecimalField, BooleanField, HiddenField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional, Regexp

class LoginForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired(), Length(max=80)])
    password = PasswordField('Senha', validators=[DataRequired(), Length(max=128)])

class ClientForm(FlaskForm):
    name = StringField('Nome / razão social', validators=[DataRequired(), Length(max=150)])
    document = StringField('CPF / CNPJ', validators=[Optional(), Length(max=30)])
    phone = StringField('Telefone / WhatsApp', validators=[Optional(), Length(max=40)])
    email = StringField('E-mail', validators=[Optional(), Length(max=150)])
    address = StringField('Endereço completo', validators=[Optional(), Length(max=300)])
    notes = TextAreaField('Observações', validators=[Optional(), Length(max=5000)])
    active = BooleanField('Cadastro ativo', default=True)

class VehicleForm(FlaskForm):
    client_id = SelectField('Cliente', coerce=int, validators=[InputRequired()])
    plate = StringField('Placa', validators=[DataRequired(), Length(max=10)])
    fleet = StringField('Número da frota', validators=[Optional(), Length(max=40)])
    model = StringField('Marca / modelo', validators=[DataRequired(), Length(max=120)])
    year = StringField('Ano', validators=[Optional(), Length(max=20)])
    notes = TextAreaField('Observações', validators=[Optional(), Length(max=5000)])
    active = BooleanField('Cadastro ativo', default=True)

class OrderForm(FlaskForm):
    number = StringField('Número da OS (vazio = automático)', validators=[Optional(), Length(max=50)])
    vehicle_id = SelectField('Veículo', coerce=int, validators=[InputRequired()])
    entry_date = DateField('Data de entrada', validators=[InputRequired()])
    due_date = DateField('Previsão de entrega', validators=[InputRequired()])
    mileage = IntegerField('Quilometragem', validators=[InputRequired(), NumberRange(min=0, max=2147483647)], default=0)
    responsible = StringField('Responsável pelo atendimento', validators=[DataRequired(), Length(max=120)])
    problem = TextAreaField('Problema relatado / solicitação', validators=[DataRequired(), Length(max=10000)])
    diagnosis = TextAreaField('Diagnóstico', validators=[Optional(), Length(max=10000)])
    notes = TextAreaField('Observações', validators=[Optional(), Length(max=10000)])
    discount = DecimalField('Desconto (R$)', places=2, validators=[InputRequired(), NumberRange(min=0, max=Decimal('9999999999.99'))], default=0)
    version = HiddenField()

class ItemForm(FlaskForm):
    kind = SelectField('Tipo', choices=[('servico','Serviço'),('peca','Peça / material')])
    description = StringField('Descrição', validators=[DataRequired(), Length(max=200)])
    quantity = DecimalField('Quantidade', places=2, validators=[InputRequired(), NumberRange(min=Decimal('0.01'), max=Decimal('99999999.99'))], default=1)
    unit_price = DecimalField('Valor unitário (R$)', places=2, validators=[InputRequired(), NumberRange(min=0, max=Decimal('9999999999.99'))], default=0)
    responsible = StringField('Profissional / responsável', validators=[Optional(), Length(max=120)])
    done = BooleanField('Serviço concluído / peça utilizada')
    version = HiddenField()

class StatusForm(FlaskForm):
    status = SelectField('Novo status')
    delivered_date = DateField('Data real da entrega', validators=[Optional()])
    version = HiddenField()

class PhotoForm(FlaskForm):
    file = FileField('Foto (JPEG, PNG ou WebP, até 8 MB)', validators=[FileRequired()])
    stage = SelectField('Etapa', choices=[('entrada','Entrada'),('servico','Serviço'),('saida','Entrega')])
    caption = StringField('Descrição', validators=[Optional(), Length(max=200)])
    version = HiddenField()

class FlowForm(FlaskForm):
    action = SelectField('Atualização do fluxo', choices=[
        ('approve', 'Registrar aprovação'),
        ('invoice', 'Registrar faturamento'),
        ('receive', 'Confirmar recebimento integral'),
    ])
    action_date = DateField('Data da etapa', validators=[InputRequired()])
    reference = StringField('Referência / observação (opcional)', validators=[Optional(), Length(max=300)])
    version = HiddenField()

class UserForm(FlaskForm):
    username = StringField('Usuário (login)', validators=[DataRequired(), Length(min=3,max=80), Regexp(r'^[a-zA-Z0-9_.-]+$', message='Use letras, números, ponto, hífen ou sublinhado.')])
    name = StringField('Nome', validators=[DataRequired(), Length(max=120)])
    password = PasswordField('Senha (mínimo 12 caracteres; vazio mantém a atual)', validators=[Optional(), Length(min=12,max=128)])
    role = SelectField('Perfil', choices=[('equipe','Equipe'),('admin','Administrador')])
    active = BooleanField('Usuário ativo', default=True)
