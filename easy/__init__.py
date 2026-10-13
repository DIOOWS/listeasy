import os
from datetime import timedelta, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
import click
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, flash
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from werkzeug.middleware.proxy_fix import ProxyFix
from .models import db, User, Order, Client, Vehicle, STATUSES

login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=['300 per minute'], storage_uri='memory://')
migrate = Migrate()

def today():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).date()

def create_app(config=None):
    load_dotenv()
    app = Flask(__name__)
    production = os.getenv('APP_ENV') == 'production'
    database = os.getenv('DATABASE_URL', 'sqlite:///easy-servicos.db')
    if database.startswith('postgres://'):
        database = database.replace('postgres://', 'postgresql://', 1)
    if database.startswith('postgresql://'):
        database=database.replace('postgresql://','postgresql+psycopg2://',1)
    app.config.update(SECRET_KEY=os.getenv('SECRET_KEY'), SQLALCHEMY_DATABASE_URI=database,
        SQLALCHEMY_TRACK_MODIFICATIONS=False, SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=production, SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=8*1024*1024,
        WTF_CSRF_TIME_LIMIT=8*60*60, APP_ENV='production' if production else 'development',
        CLOUDINARY_URL=os.getenv('CLOUDINARY_URL'), RATELIMIT_STORAGE_URI=(os.getenv('REDIS_URL') or 'memory://'))
    if config:
        app.config.update(config)
    if not app.config['SECRET_KEY'] or len(app.config['SECRET_KEY']) < 32 or app.config['SECRET_KEY'].startswith('SUBSTITUA'):
        raise RuntimeError('Defina SECRET_KEY com pelo menos 32 caracteres aleatórios.')
    if app.config['APP_ENV']=='production':
        if not app.config['SQLALCHEMY_DATABASE_URI'].startswith(('postgresql://','postgresql+psycopg2://')):
            raise RuntimeError('Produção exige DATABASE_URL do PostgreSQL/Supabase.')
        app.config['SESSION_COOKIE_SECURE']=True
        app.config['SQLALCHEMY_ENGINE_OPTIONS']={'pool_pre_ping':True,'pool_size':3,'max_overflow':2,'pool_recycle':300,'connect_args':{'sslmode':'require','connect_timeout':10}}
        app.wsgi_app=ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view='web.login'
    login_manager.login_message='Entre para acessar o sistema.'
    csrf.init_app(app)
    limiter.init_app(app)
    migrate.init_app(app,db,compare_type=True,version_table='ecs_alembic_version')
    from .routes import web
    app.register_blueprint(web)
    @app.context_processor
    def common():
        return {'today':today(), 'statuses':STATUSES, 'app_name':'EASY • Serviços'}
    @app.template_filter('brl')
    def brl(value):
        return 'R$ '+f'{Decimal(value or 0):,.2f}'.replace(',','_').replace('.',',').replace('_','.')
    @app.template_filter('datebr')
    def datebr(value):
        return value.strftime('%d/%m/%Y') if value else '—'
    @app.template_filter('localtime')
    def localtime(value):
        return value.replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M')
    @app.after_request
    def secure_headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        if app.config['APP_ENV']=='production':
            response.headers['Strict-Transport-Security']='max-age=31536000'
        if not __import__('flask').request.path.startswith('/static/'):
            response.headers['Cache-Control']='no-store'
        return response
    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template('error.html',code=400,message='Sessão do formulário expirou. Atualize a página e tente novamente.'),400
    for code, message in [(403,'Você não tem acesso a esta ação.'),(404,'Registro não encontrado.'),(413,'A foto excede o limite de 8 MB.'),(429,'Muitas tentativas. Aguarde um minuto e tente novamente.')]:
        app.register_error_handler(code,lambda error,c=code,m=message:(render_template('error.html',code=c,message=m),c))
    @app.errorhandler(StaleDataError)
    def conflict(error):
        db.session.rollback()
        return render_template('error.html',code=409,message='Esta OS foi alterada por outra pessoa. Reabra a ficha e tente novamente.'),409
    @app.errorhandler(IntegrityError)
    def integrity(error):
        db.session.rollback()
        return render_template('error.html',code=409,message='Não foi possível salvar: verifique registros duplicados e dados relacionados.'),409
    @app.errorhandler(409)
    def conflict_response(error):
        db.session.rollback()
        return render_template('error.html',code=409,message=error.description),409
    @app.errorhandler(400)
    def bad_request(error):
        return render_template('error.html',code=400,message=error.description),400
    @app.errorhandler(502)
    def photo_error(error):
        return render_template('error.html',code=502,message='Não foi possível carregar a foto. Tente novamente.'),502
    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template('error.html',code=500,message='Não foi possível concluir a ação. Tente novamente.'),500
    @app.get('/health')
    @limiter.exempt
    def health():
        try:
            db.session.execute(text('SELECT 1'))
            db.session.execute(db.select(User.id).limit(1))
            return {'status':'ok'}
        except Exception:
            db.session.rollback()
            return {'status':'unavailable'},503
    @app.cli.command('create-admin')
    @click.option('--username',prompt=True)
    @click.option('--name',prompt=True)
    @click.option('--password',prompt=True,hide_input=True,confirmation_prompt=True)
    def create_admin(username,name,password):
        import re
        username=username.strip().lower()
        if not re.fullmatch(r'[a-z0-9_.-]{3,80}',username) or not name.strip() or len(name)>120 or not 12<=len(password)<=128:
            raise click.ClickException('Usuário inválido ou senha fora do intervalo 12–128 caracteres.')
        if db.session.scalar(db.select(User).where(User.username==username)):
            raise click.ClickException('Usuário já existe. Use reset-password para trocar a senha.')
        user=User(username=username,name=name.strip(),role='admin')
        user.set_password(password);db.session.add(user);db.session.commit()
        click.echo('Administrador criado.')
    @app.cli.command('reset-password')
    @click.option('--username',prompt=True)
    @click.option('--password',prompt=True,hide_input=True,confirmation_prompt=True)
    def reset_password(username,password):
        user=db.session.scalar(db.select(User).where(User.username==username.strip().lower()))
        if not user or not 12<=len(password)<=128:
            raise click.ClickException('Usuário não encontrado ou senha inválida.')
        user.set_password(password);user.failures=0;user.locked_until=None;user.session_version+=1
        db.session.commit();click.echo('Senha atualizada. Sessões anteriores revogadas.')
    return app

@login_manager.user_loader
def load_user(value):
    try:
        ident,version=value.split(':');user=db.session.get(User,int(ident))
        return user if user and user.active and user.session_version==int(version) else None
    except (ValueError,AttributeError):
        return None
