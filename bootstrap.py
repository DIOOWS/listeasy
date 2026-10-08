"""Aplica migrações e cria somente o primeiro administrador, sem redefinir senhas."""
import os
import re
from flask_migrate import upgrade
from app import app
from easy.models import db, User

with app.app_context():
    upgrade()
    if not db.session.scalar(db.select(User.id).where(User.role=='admin',User.active.is_(True)).limit(1)):
        username=os.getenv('ADMIN_USERNAME','').strip().lower()
        name=os.getenv('ADMIN_NAME','').strip()
        password=os.getenv('ADMIN_PASSWORD','')
        if not re.fullmatch(r'[a-z0-9_.-]{3,80}',username) or not name or len(name)>120 or not 12<=len(password)<=128:
            raise RuntimeError('Primeiro acesso: defina ADMIN_USERNAME, ADMIN_NAME e ADMIN_PASSWORD (12–128 caracteres).')
        if db.session.scalar(db.select(User.id).where(User.username==username)):
            raise RuntimeError('O usuário inicial já existe. Recupere o administrador com flask reset-password.')
        user=User(username=username,name=name,role='admin');user.set_password(password)
        db.session.add(user);db.session.commit();print('Administrador inicial criado.')
    print('Banco atualizado. Inicialização concluída.')
