# EASY Serviços — Flask + Supabase + Render + PWA

Versão 1.0. A logo Easy Assistência 24h enviada foi aplicada ao cabeçalho, à impressão, ao favicon e aos ícones do PWA, preservando as proporções. Projeto independente para controlar os veículos dos clientes e os serviços executados. Interface simples, responsiva e instalável no celular.

## O que esta versão faz

- Login por **usuário**, com botão para mostrar senha. Perfis Administrador e Equipe.
- Clientes, veículos, placa, frota, modelo e histórico de OS por veículo.
- OS com numeração automática ou manual, entrada, previsão de entrega, quilometragem, responsável, problema, diagnóstico e observações.
- Checklist de entrada com OK, avaria, não se aplica e pendente. Avarias exigem descrição.
- Serviços e peças com quantidade, preço unitário, total e indicação de conclusão/utilização. Total da OS = serviços + peças − desconto.
- Checklist de saída e data real da entrega. Liberação exige serviços concluídos, checklist de entrada preenchido e checklist de saída aprovado.
- Histórico com usuário, horário e ações realizadas na OS.
- Indicadores de veículos em atendimento, entregas de hoje e atrasados.
- Relatórios com busca, status e período por data de entrada. Excel com abas OS, serviços/peças e checklist; impressão da OS com opção Salvar como PDF pelo navegador.
- Fotos privadas opcionais via Cloudinary, abertas somente após login no aplicativo.
- PWA com ícones, instalação, interface para celular e captura pela câmera.

OS entregues ou canceladas ficam bloqueadas para edição. Um administrador pode reabri-las. Alterar uma OS pronta devolve o atendimento a “Em serviço”, para uma nova conferência.

Os relatórios incluem todas as OS do filtro, inclusive canceladas quando nenhum status é selecionado. Os valores representam orçamento/custo registrado na OS; não comprovam recebimento de pagamento.

## Uso da operadora no local

1. O administrador cria o usuário dela em **Usuários**, perfil **Equipe**.
2. Ela abre o endereço HTTPS no celular e faz login.
3. Android/Chrome: menu ⋮ → Instalar aplicativo / Adicionar à tela inicial. iPhone/Safari: Compartilhar → Adicionar à Tela de Início. Há instruções em “Instalar app”.
4. Ela abre a OS e salva o checklist de entrada. Na aba Fotos, escolhe a etapa, tira a foto e toca em Anexar foto.
5. Cada envio precisa apresentar a confirmação antes de sair da tela.

**Esta versão exige internet para consultar e salvar.** O PWA não guarda OS, fotos ou credenciais no cache. Sem conexão, aparece uma tela de orientação; se o aparelho detectar que está offline antes de enviar, o formulário permanece aberto. Não há fila de alterações nem sincronização offline. Instalação real e captura da câmera precisam ser verificadas no aparelho após o deploy HTTPS.

## Rodar no Windows (PowerShell)

Extraia o ZIP e entre na pasta que contém `app.py`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copie a chave gerada para `SECRET_KEY` dentro do `.env`. Mantenha `APP_ENV=development` e o SQLite para testar localmente. Defina também:

```dotenv
ADMIN_USERNAME=diogo
ADMIN_NAME=Diogo
ADMIN_PASSWORD=DEFINA_AQUI_UMA_SENHA_FORTE_COM_PELO_MENOS_12_CARACTERES
```

O exemplo de senha acima é apenas uma indicação: substitua por uma senha sua. Não há senha padrão cadastrada.

```powershell
.\.venv\Scripts\python.exe bootstrap.py
.\.venv\Scripts\python.exe -m flask --app app run
```

Abra http://127.0.0.1:5000. Login: o usuário e a senha que você definiu. Os dados locais ficam em `instance/easy-servicos.db`; não envie esse banco ao GitHub.

Linux/macOS: use `python3 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.lock.txt`, `cp .env.example .env` e `.venv/bin/python bootstrap.py`.

## Supabase para produção

1. Crie um projeto para este sistema. O aplicativo usa o PostgreSQL do Supabase diretamente, pelo servidor Flask; não usa chaves anon ou service_role no navegador.
2. No painel, abra **Connect → Session pooler** e copie a conexão PostgreSQL. O session pooler é a alternativa para redes IPv4, normalmente na porta 5432. Fonte: https://supabase.com/docs/guides/database/connecting-to-postgres
3. Substitua a senha do banco na conexão e adicione `?sslmode=require` se não houver parâmetros. Se já houver `?`, acrescente `&sslmode=require`. O código também exige SSL em produção.
4. A senha dentro da URL precisa estar codificada se contiver `@`, `#`, `/`, `:` ou outros caracteres reservados. Faça essa edição localmente; não envie credenciais em prints ou ao repositório.

Exemplo de formato, com dados ilustrativos:

```text
postgresql://postgres.PROJECT_REF:SENHA_CODIFICADA@POOLER_HOST:5432/postgres?sslmode=require
```

As migrações criam apenas tabelas com prefixo `ecs_`. Habilitam RLS e revogam acesso das funções `anon` e `authenticated` nessas tabelas; o aplicativo acessa pelo servidor com a conexão de proprietário do banco. Não é necessário colar SQL manualmente. A tabela de migrações também usa prefixo próprio.

## GitHub

Crie um repositório novo e vazio em https://github.com/new, por exemplo `easy-servicos`. Na pasta com `app.py`, se ela ainda não for um repositório:

```powershell
git init
git add .
git commit -m "Cria EASY Servicos Flask PWA"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/easy-servicos.git
git push -u origin main
```

Se já houver um repositório, use o remoto existente. `.env`, banco local e ambiente virtual estão excluídos pelo `.gitignore`.

## Publicar no Render

Você pode usar **New → Blueprint** com o `render.yaml`, ou criar um **Web Service** Python conectado ao GitHub.

Configuração manual:

- Build Command: `pip install -r requirements.lock.txt`
- Start Command: `python bootstrap.py && gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 90 --access-logfile - --error-logfile -`
- Health Check Path: `/health`
- Python: `3.12.12`

O Render documenta o deploy Flask com Gunicorn em https://render.com/docs/deploy-flask.

Variáveis no Render:

| Variável | Valor |
| --- | --- |
| `APP_ENV` | `production` |
| `SECRET_KEY` | Chave aleatória de pelo menos 32 caracteres; o Blueprint gera uma |
| `DATABASE_URL` | Conexão PostgreSQL Session pooler do Supabase |
| `ADMIN_USERNAME` | Login inicial, por exemplo `diogo` |
| `ADMIN_NAME` | Nome exibido |
| `ADMIN_PASSWORD` | Senha inicial forte, 12–128 caracteres |
| `CLOUDINARY_URL` | Opcional, para anexar fotos |
| `REDIS_URL` | Opcional, para compartilhar o limite de requisições entre processos |

O comando de inicialização aplica as migrações e cria o primeiro administrador somente quando ainda não há administrador ativo. Não altera a senha em cada deploy e não insere dados de demonstração. Depois do primeiro acesso, remova `ADMIN_PASSWORD` das variáveis do Render; os usuários continuam no banco.

Mantenha **um worker** enquanto `REDIS_URL` não estiver configurada. O bloqueio por tentativas de senha fica no banco; o limite geral de requisições usa memória quando Redis não é informado. O Render pode suspender o serviço conforme o plano contratado; confira as condições no painel.

O sistema ainda precisa ser publicado na sua conta. Este pacote não contém acesso ao Render, Supabase ou GitHub e não cria serviços remotos sozinho.

## Fotos (opcional)

Crie/configure seu produto Cloudinary e copie a URL do ambiente para `CLOUDINARY_URL` no Render:

```text
cloudinary://API_KEY:API_SECRET@CLOUD_NAME
```

O SDK faz uploads HTTPS autenticados: https://cloudinary.com/documentation/django_image_and_video_upload

As fotos são enviadas com tipo `authenticated`, não são gravadas no disco temporário do Render e são entregues pelo Flask apenas a usuários logados. Formatos JPEG/PNG/WebP, limite de requisição 8 MB e resolução de até 25 megapixels. O envio via câmera depende do suporte do navegador; imagens HEIC precisam ser convertidas para JPEG. Sem Cloudinary, todo o restante do sistema funciona e o envio de fotos fica desabilitado.

## Administração e recuperação

O login é **username**, não e-mail. O perfil Equipe pode consultar e editar os atendimentos, clientes e veículos; somente o Administrador gerencia usuários e reabre OS encerradas. Não há portal de clientes nem restrição por cliente nesta versão.

Para criar um administrador pelo terminal:

```text
python -m flask --app app create-admin
```

Para trocar a senha e revogar as sessões antigas:

```text
python -m flask --app app reset-password
```

No Windows, substitua `python` por `.\.venv\Scripts\python.exe`; no Render, use um terminal autorizado com as variáveis do serviço.

## Verificação

```text
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Os testes usam banco SQLite isolado e dados fictícios. Verificam abertura e entrega, valores decimais, checklist obrigatório, conflitos de edição, bloqueio de login, CSRF, perfis, Excel, vínculo histórico do cliente, fotos privadas com serviços externos simulados e arquivos PWA.

Também foram verificadas as migrações em um banco local novo e a geração SQL para PostgreSQL. A conexão real com Supabase, upload real no Cloudinary, instalação/câmera no celular e execução no Render dependem das contas e devem ser conferidas após a publicação. A checagem visual em navegador real não foi executada neste ambiente.

## Rotina e próximas versões

- Mantenha backup do PostgreSQL e das fotos conforme as opções do seu plano. Excel ajuda na consulta, mas não substitui backup completo.
- Novas mudanças de estrutura devem virar migrações versionadas. Não rode `db.create_all()` em produção.
- Ao alterar os arquivos públicos do PWA, incremente o nome `CACHE` em `easy/static/sw.js`.
- Offline com sincronização, assinatura digital, estoque, aprovação pelo cliente e financeiro de recebimentos são evoluções futuras; não estão implementados.
#   l i s t e a s y  
 