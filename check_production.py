"""Valida a configuração de produção sem imprimir senhas ou conectar ao banco."""
import os
import sys
from urllib.parse import urlsplit
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

def validate_environment():
    load_dotenv()
    errors=[]
    if os.getenv('APP_ENV')!='production':
        errors.append('APP_ENV precisa ser production.')
    key=os.getenv('SECRET_KEY','')
    if len(key)<32 or key.startswith(('SUBSTITUA','COLE_','CHANGE_')):
        errors.append('Defina SECRET_KEY com pelo menos 32 caracteres aleatórios.')
    try:
        url=make_url(os.getenv('DATABASE_URL',''))
        if url.get_backend_name()!='postgresql' or not url.host or not url.username or not url.password:
            errors.append('DATABASE_URL precisa conter a conexão completa PostgreSQL do Supabase.')
    except Exception:
        errors.append('DATABASE_URL ausente ou inválida.')
    password=os.getenv('ADMIN_PASSWORD','')
    if password and not 12<=len(password)<=128:
        errors.append('ADMIN_PASSWORD precisa ter 12–128 caracteres.')
    cloud=os.getenv('CLOUDINARY_URL','')
    if cloud:
        try:
            parsed=urlsplit(cloud)
            if parsed.scheme!='cloudinary' or not parsed.hostname or not parsed.username or not parsed.password:
                errors.append('CLOUDINARY_URL incompleta. Copie a URL do painel Cloudinary.')
        except ValueError:
            errors.append('CLOUDINARY_URL inválida.')
    return errors

if __name__=='__main__':
    errors=validate_environment()
    if errors:
        for error in errors:print('Configuração: '+error,file=sys.stderr)
        sys.exit(1)
    print('Configuração de produção validada. A conexão será verificada nas migrações.')
