# Guia do Portal Verdade Ceará

## Primeiro acesso e personalização

Em **Personalização**, cadastre nome, razão social, CPF/CNPJ, endereço, cidade, telefone e e-mail. Defina cor, tema padrão e densidade da interface. A logo pode ser PNG, JPEG ou WebP de até 5 MB. O favicon original permanece independente da logo institucional.

A opção de tema no cabeçalho fica salva apenas naquele navegador e prevalece sobre o padrão da empresa. A densidade compacta é o padrão; a confortável aumenta campos e espaçamentos.

## Equipe e acesso

Em **Equipe & permissões**, cadastre nome, função e contatos. Um integrante pode ser apenas um responsável cadastrado ou ter um usuário e senha para acessar o Portal.

| Perfil | Permissões |
|---|---|
| Gestão | Operação, contratos, modelos, equipe, personalização e financeiro |
| Financeiro | Clientes, materiais, tarefas, lançamentos e relatórios |
| Produção | Clientes, materiais e tarefas, sem valores de contratos ou financeiro |

Somente gestão altera a equipe. Contas administrativas e o próprio acesso são protegidos de alterações por esse formulário. Desativar um integrante desativa também seu acesso vinculado e preserva o histórico. Contas sem perfil de equipe e sem privilégios administrativos têm acesso de produção.

## Clientes, contratos e materiais

1. Cadastre o cliente com contato e situação comercial.
2. Escolha ou edite um modelo em Contratos > Modelos.
3. Gere o contrato com vigência, valor, vencimento e quantidades de materiais por mês.
4. Confira o PDF e os termos; utilize o link individual para assinatura quando o contrato estiver em situação de envio.
5. Registre os materiais com data, formato e responsável. A movimentação para Publicado registra a data de publicação.

Os termos são uma cópia do modelo no momento da geração. Alterar o modelo não reescreve contratos já gerados. Contratos assinados têm os termos protegidos.

Variáveis da empresa: `[[empresa_nome]]`, `[[empresa_razao_social]]`, `[[empresa_documento]]`, `[[empresa_endereco]]`, `[[empresa_email]]`, `[[empresa_telefone]]`, `[[empresa_cidade]]`. Preencha os dados em Personalização antes de gerar documentos definitivos. As variáveis de cliente, pacote, datas e valor continuam disponíveis no editor.

## Tarefas e Kanban

Crie uma tarefa com descrição, prioridade, prazo, responsável e, quando necessário, cliente e material. Use o detalhe para adicionar checklist e comentários. Etapas: A fazer, Em andamento, Em revisão e Concluída.

A coluna Atrasadas é calculada pelo prazo e não é uma etapa manual. Uma tarefa vencida permanece nela até ser concluída ou ter seu prazo revisto. Cada tarefa aparece em apenas uma coluna. Reabrir uma tarefa remove a data de conclusão anterior.

No computador, arraste o cartão. Em qualquer dispositivo, escolha a etapa e use Mover. Alterações concorrentes são recusadas para evitar sobrescrever o trabalho de outra pessoa; atualize o quadro e tente novamente.

Os filtros permitem buscar tarefa/cliente, escolher responsável, ver Minhas tarefas e filtrar prioridade. A lista facilita a conferência; o calendário mostra as tarefas com prazo no mês selecionado. Tarefas sem prazo continuam disponíveis no Kanban e na lista.

## Financeiro

- **Resumo:** entradas e saídas previstas, valores pagos, pendências, despesas por categoria e evolução do saldo.
- **Lançamentos:** registros de entrada/saída, categoria, valor, vencimento, pagamento, cliente, contrato, forma e favorecido.
- **Fluxo de caixa:** movimentos agrupados pela data em que foram pagos, com saldo acumulado dentro do mês.

Competência usa a data de vencimento; realizado usa a data de pagamento. Por isso um valor vencido no mês anterior e pago agora aparece no realizado atual. O saldo acumulado não inclui saldo bancário anterior e não é uma conciliação bancária.

**Dar baixa hoje** registra pagamento com a data atual. Para datas anteriores, edite o lançamento e informe a data correta. Repetir a baixa não duplica valores; lançamentos cancelados não podem ser pagos pela ação rápida.

Em Gerar mensalidades, a gestão pode criar pendências de contratos assinados e vigentes no mês. A geração usa o valor mensal integral, ajusta dia 31 ao último dia de meses curtos e preserva competências já geradas. Revise proporcionalidade e lançamentos manuais antes de cobrar: não há cobrança bancária automática nem conciliação de lançamentos digitados manualmente.

PDF e CSV respeitam os filtros de competência, cliente, tipo e situação. O PDF usa o papel timbrado da empresa. O CSV abre em planilhas e neutraliza valores textuais que poderiam ser interpretados como fórmulas.

## Referência visual e limites da adaptação

O painel de hospedagens do NAVIE (`navie-vibe`, referência `3b4b082`) orientou a navegação de 70 px expansível, temas, superfícies translúcidas, cartões compactos, abas, equipe, organização e análise financeira. A implementação foi adaptada aos clientes e serviços do Portal, sem importar dados do NAVIE. Operações de quartos, reservas, estoque hoteleiro, comissões de marketplace e credenciais de pagamentos não fazem parte do Portal.
