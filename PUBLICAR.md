# Publicar EASY Serviços no Render + Supabase

Pacote de produção v1.2. Inclui a logo, o PWA e a correção do erro 500 no login. Não contém senhas, dados de clientes, o banco local nem contas remotas já criadas.

## 1. Extrair e conferir

Extraia o ZIP. Entre na pasta `easy-servicos`, que contém `app.py`, `render.yaml` e `start.sh`. Essa deve ser a raiz do repositório.

Se copiar arquivos sobre a instalação que você já usa, preserve `.env`, `.venv` e `instance`. Não copie essas três pastas/arquivos para o GitHub. A produção usará um banco diferente: os usuários e dados de teste locais não são transferidos automaticamente.

## 2. Criar o Supabase

1. Acesse https://supabase.com/dashboard e crie um projeto para o EASY Serviços.
2. Guarde a senha do banco e aguarde o projeto ficar disponível.
3. Abra **Connect → Session pooler**, normalmente na porta 5432. Copie a URL PostgreSQL.
4. Substitua o marcador da senha na URL pela senha do banco, codificando os caracteres reservados da senha se necessário.
5. Use essa URL como `DATABASE_URL` no Render. Ela não é a URL HTTPS do projeto e não é a chave anon.

Formato ilustrativo:

```text
postgresql://postgres.PROJECT_REF:SENHA_CODIFICADA@POOLER_HOST:5432/postgres?sslmode=require
```

O aplicativo seleciona o driver psycopg2 e exige SSL em produção. As migrações criam o banco automaticamente no primeiro início; não precisa colar SQL no painel.

Referência: https://supabase.com/docs/guides/database/connecting-to-postgres

## 3. Subir ao GitHub

Crie um repositório vazio em https://github.com/new, com o nome `easy-servicos`. Não adicione README pelo site, pois o pacote já contém um.

Abra o PowerShell na pasta que contém `app.py`. Para uma pasta que ainda não seja repositório:

```powershell
git init
git add .
git status
git commit -m "Prepara EASY Servicos Flask PWA para producao"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/easy-servicos.git
git push -u origin main
```

Substitua `SEU_USUARIO` pelo seu usuário no GitHub. No `git status`, confira que `.env`, `.venv` e `instance` não aparecem. Se o repositório já existe, use o remoto existente e apenas faça commit/push das alterações.

## 4. Criar o serviço no Render

Acesse https://dashboard.render.com e conecte seu repositório. Duas opções:

- **New → Blueprint:** o Render lê o `render.yaml`; preencha as variáveis solicitadas.
- **New → Web Service:** configure os campos abaixo manualmente.

| Campo | Valor |
| --- | --- |
| Branch | `main` |
| Root Directory | Vazio, se `app.py` estiver na raiz do GitHub |
| Runtime | Python |
| Build Command | `pip install -r requirements.lock.txt` |
| Start Command | `bash start.sh` |
| Health Check Path | `/health` |

O script valida a configuração, aplica as migrações, cria o administrador inicial se necessário e inicia o Gunicorn. Não use `flask run` no Render.

Referência: https://render.com/docs/deploy-flask

## 5. Variáveis no Render

Abra **Environment** e preencha:

| Variável | O que colocar |
| --- | --- |
| `PYTHON_VERSION` | `3.12.12` |
| `APP_ENV` | `production` |
| `SECRET_KEY` | Uma chave aleatória nova, pelo menos 32 caracteres; Blueprint gera automaticamente |
| `DATABASE_URL` | A conexão PostgreSQL do Session pooler do Supabase |
| `ADMIN_USERNAME` | `diogo` ou outro login em letras minúsculas |
| `ADMIN_NAME` | `Diogo` ou o nome do administrador |
| `ADMIN_PASSWORD` | Sua senha inicial, entre 12 e 128 caracteres |
| `CLOUDINARY_URL` | Opcional; necessário para anexar fotos |
| `REDIS_URL` | Opcional; pode ficar ausente com o worker único configurado |

Para gerar a chave pelo PowerShell da instalação local:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Cole o resultado em `SECRET_KEY` no Render. Não copie a chave para o GitHub. O arquivo `.env.production.example` é só um modelo de referência; não é necessário enviá-lo preenchido.

O login de produção será criado no Supabase usando as variáveis acima. O usuário criado antes no SQLite do seu computador não existe automaticamente no banco de produção.

## 6. Fotos da operadora

Para permitir fotos, configure um produto Cloudinary em https://cloudinary.com. Copie a URL do ambiente para `CLOUDINARY_URL` no Render:

```text
cloudinary://API_KEY:API_SECRET@CLOUD_NAME
```

Sem essa variável, o sistema funciona, mas o envio de fotos fica desabilitado. Os arquivos são enviados como privados e consultados pelo sistema após login; não ficam no disco temporário do Render.

## 7. Primeiro deploy e uso no celular

1. Aguarde o deploy concluir. O log deve terminar com “Banco atualizado. Inicialização concluída.” e o início do Gunicorn.
2. Abra o endereço HTTPS `.onrender.com` fornecido pelo Render.
3. Faça login com o administrador definido nas variáveis. Cadastre um cliente, um veículo e uma OS para conferir o fluxo.
4. Em **Usuários**, crie a conta da operadora com o perfil **Equipe**.
5. No celular dela, abra o endereço do sistema. Android/Chrome: menu → Instalar aplicativo. iPhone/Safari: Compartilhar → Adicionar à Tela de Início.
6. Confira a abertura da OS, o salvamento do checklist e, se configurado, o envio de uma foto.
7. Depois do primeiro login bem-sucedido, remova `ADMIN_PASSWORD` do Environment no Render. A senha cadastrada continua no banco; os próximos deploys não redefinem a conta.

Nesta versão é preciso internet para consultar e salvar. Não existe preenchimento offline com sincronização.

## 8. Se o deploy falhar

- **Primeiro acesso: defina ADMIN...:** verifique os três campos do administrador, inclusive o tamanho da senha.
- **DATABASE_URL inválida / erro de conexão:** confira a URL PostgreSQL, host, usuário, senha e Session pooler. Use a senha do banco, não a senha do login do sistema.
- **Usuário ou senha inválidos:** confira o `ADMIN_USERNAME` definido no primeiro deploy. Alterar `ADMIN_PASSWORD` depois de criar o usuário não troca a senha existente. Use `python -m flask --app app reset-password` em um terminal autorizado do serviço se precisar recuperar o acesso.
- **Fotos desabilitadas:** falta configurar `CLOUDINARY_URL` e redeployar.
- **Não consegue acessar GitHub:** confira se a integração GitHub do Render tem permissão para esse repositório.

Para pedir ajuda, copie a parte final do log e o erro; oculte credenciais e URLs de banco que incluam senha.

## Verificações realizadas e pendentes

O pacote foi verificado por testes automatizados de aplicação, login com CSRF real, checklist, valores, perfis, relatórios e configuração de produção. Inicialização local e geração das migrações SQL PostgreSQL foram verificadas. O início com Gunicorn também foi exercitado localmente.

A conexão real com seu Supabase, o deploy na sua conta Render, o upload real no Cloudinary e a instalação/câmera no seu celular só poderão ser conferidos após configurar as contas. A interface não passou por revisão visual em navegador real neste ambiente.
