# EASY Serviços v1.5 — Resposta e desempenho

Esta é uma versão completa da v1.4, com fluxo, checklist, serviços, peças,
fotos, usuários, relatórios e PWA preservados.

## O que mudou

- Listas carregam serviços e peças em lote, evitando consultas por OS.
- Cadastro de OS busca os clientes junto dos veículos.
- Indicadores do painel são calculados em uma consulta.
- Histórico busca os usuários dos eventos em conjunto.
- Arquivos públicos versionados do PWA são reutilizados do cache local.
- Cliques em navegação e envio mostram Carregando ou Salvando imediatamente.
- Um segundo envio do mesmo formulário enquanto ele está em andamento é bloqueado.
- Abas e abertura do fluxo continuam locais; salvar continua exigindo internet.

## Atualizar o projeto existente

1. Extraia este ZIP. Copie a pasta `easy` para seu projeto existente,
   substituindo os arquivos. Preserve seu `.env`, banco, `.venv` e `.git`.
2. Se ainda não instalou a v1.4 com o fluxo, copie também `migrations`.
3. No PowerShell, dentro do projeto:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app db upgrade
.\.venv\Scripts\python.exe -m flask --app app run --debug
```

Se a `.venv` não existir e você continuar com Python 3.10 instalado:

```powershell
py -3.10 -m venv .venv
```

Depois repita os comandos acima. Produção mantém as dependências travadas
em `requirements.lock.txt` e a configuração de Python do projeto.

Para publicar o código que você atualizou no repositório existente:

```powershell
git add easy migrations ATUALIZAR_DESEMPENHO.md
git commit -m "Melhora consultas e resposta dos cliques"
git push
```

Não é necessário trocar variáveis de ambiente nem criar usuários novamente.
O `start.sh` existente aplica as migrações no Render. Esta v1.5 não adiciona
uma nova migração; o banco continua na revisão c410a924ef73 da v1.4.

Após o deploy, abra o sistema com internet, atualize a página e feche/abra o
PWA para ele receber o cache v5. A primeira abertura baixa os novos arquivos.

## Verificação

21 testes automatizados passaram, incluindo regras do fluxo, acesso,
CSRF, conflitos de alteração e preservação dos dados na migração.

Teste local com 30 OS, cada uma com um cliente e um veículo diferente:

| Tela | Consultas antes | Consultas depois |
| --- | ---: | ---: |
| Painel | 18 | 4 |
| Ordens | 28 | 4 |
| Nova OS | 32 | 2 |
| Relatórios | 35 | 6 |
| Exportação Excel | 62 | 4 |

Esses números medem consultas, não a velocidade real da sua produção.
A conexão e a infraestrutura ainda podem causar demora. A versão publicada
não foi acessada nesta verificação; se persistir, envie o endereço do sistema
e diga qual tela/ação está lenta para medir a requisição específica.

JavaScript validado sintaticamente. A interação visual no celular ainda
precisa ser conferida no seu aparelho; não houve teste em navegador real.
