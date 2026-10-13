# EASY Serviços — fluxo de atendimento

## O que mudou

Entrada → Aprovação → Em serviço → Pronto → Entregue → Faturado → Recebido.

O painel e a lista de OS mostram o fluxo. No celular, toque na linha para expandir a sequência vertical. No computador, os fluxos abrem na horizontal. Só as bolinhas recebem cores: verde para concluído, azul para atual e cinza para pendente. Fundo branco, textos pretos e títulos em negrito.

O prazo permanece separado. Uma OS entregue aparece no painel enquanto houver pendência de faturamento/recebimento; os três KPIs continuam contando apenas veículos ainda em atendimento. As OS recebidas continuam disponíveis em Ordens, histórico do veículo e relatórios.

## Atualizar a produção

1. Faça uma cópia da pasta atual do projeto e um backup do banco.
2. Extraia este ZIP em outra pasta.
3. Copie **easy** e **migrations** para a pasta do repositório que já está publicado, substituindo os arquivos correspondentes. São necessárias as duas pastas: esta versão acrescenta cinco colunas de datas ao banco.
4. Preserve seu `.env`, as variáveis do Render e os demais arquivos de produção já configurados. O ZIP não contém credenciais.
5. No PowerShell, dentro da pasta do seu repositório:

```powershell
git add easy migrations
git commit -m "Implementa fluxo de atendimento com datas e financeiro"
git push origin main
```

6. Aguarde o deploy. O comando de inicialização existente `bash start.sh` executa `bootstrap.py`, que aplica a migração automaticamente antes de iniciar o servidor. Nos logs, a revisão final deve ser **c410a924ef73**. A migração mantém OS, clientes, veículos, usuários e senhas existentes.
7. Quando o Render estiver Live, recarregue o site. Feche e reabra o PWA no celular. O cache público foi atualizado para v4.

Não rode `db.create_all()` em produção nem recrie tabelas. Não é necessário redefinir usuários ou senhas. As novas datas históricas começam vazias: o sistema não inventa datas ou confirma aprovações/pagamentos antigos.

## Como operar

Abra a OS. Em **Fluxo do atendimento**, expanda **Registrar aprovação / faturamento / recebimento**, escolha a ação, informe a data e uma referência opcional e salve.

- Aprovação: registre a confirmação do cliente.
- Em serviço: altere o status na seção **Status e entrega**. A primeira data de início fica registrada.
- Pronto: conclua os serviços e os checklists, depois altere para **Pronto para entrega**. Uma alteração posterior que reabra o serviço remove a data atual de pronto, preservando o histórico.
- Entregue: informe a data real da entrega e atualize o status. As regras dos checklists continuam valendo.
- Faturado: registre após a entrega, com data igual ou posterior à entrega. A referência pode conter o número da nota.
- Recebido: confirme após o faturamento, com data igual ou posterior ao faturamento. Esta confirmação representa o recebimento integral da OS; não há controle de parcelas ou pagamentos parciais nesta versão.

A aprovação não é um bloqueio novo para as OS existentes. Se uma etapa passada não tiver data registrada, o fluxo indica isso. A bolinha azul representa a etapa em andamento ou a próxima etapa aguardada; as datas aparecem quando registradas.

Faturamento e recebimento ficam separados do status operacional. Uma OS entregue pode receber esses registros sem ser reaberta. Para reabrir/cancelar uma OS já faturada, um administrador precisa corrigir os registros financeiros primeiro.

## Correções e histórico

Um administrador pode remover um registro de aprovação, faturamento ou recebimento pelo mesmo seletor. É obrigatório informar o motivo. Para corrigir faturamento, remova o recebimento antes, se houver. Depois registre a etapa com a data correta.

Cada ação registra data, usuário e observação no Histórico. O controle de versão evita que duas pessoas sobrescrevam a OS com um formulário antigo. As mudanças são salvas online; o PWA não sincroniza alterações offline.

## Relatórios

O Excel mantém as colunas anteriores e acrescenta aprovação, início, pronto, faturamento, recebimento e etapa do fluxo. A impressão/PDF inclui a lista de etapas e suas datas.

## Validação

19 testes funcionais passaram, incluindo migração de banco anterior com OS e usuário existentes, ciclo completo, cronologia, permissões, CSRF, concorrência, relatórios e preservação das regras do checklist. A migração foi executada em SQLite de teste. Não houve acesso ao Supabase ou Render do cliente.

A tentativa de instalar o navegador de validação neste ambiente falhou porque o download retornou um arquivo inválido. A prévia visual foi aprovada na conversa; a versão Flask foi verificada funcionalmente, mas não passou por validação visual em navegador móvel real.
