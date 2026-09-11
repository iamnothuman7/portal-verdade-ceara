from django.db import migrations


TEMPLATE_NAME = "Prestação de serviços de comunicação"
MATERIALS_HEADING = "ENVIO DE MATERIAIS E PRAZOS DE POSTAGEM"
VISITS_HEADING = "AGENDAMENTO DE VISITAS E IMPREVISTOS"
TERMINATION_HEADING = "7. RESCISÃO ANTECIPADA E MULTA"
PREVIOUS_TERMINATION = """7. CANCELAMENTO E RESCISÃO
A rescisão, os prazos de aviso e os valores eventualmente devidos seguirão as condições comerciais ajustadas entre as partes e a legislação aplicável."""
TERMINATION_TERMS = """7. RESCISÃO ANTECIPADA E MULTA
7.1. O presente contrato é firmado pelo prazo determinado de [[prazo_contrato]], iniciando-se em [[data_inicio]] e encerrando-se em [[data_fim]].

7.2. Qualquer uma das partes poderá rescindir este contrato antes do prazo estipulado, mediante aviso prévio por escrito com antecedência mínima de 30 (trinta) dias. Durante o período de aviso prévio, os serviços continuarão sendo prestados e a mensalidade correspondente deverá ser paga normalmente.

7.3. Caso o CONTRATANTE solicite a rescisão antecipada do contrato fora das hipóteses de justa causa, ficará obrigado ao pagamento de:
a) Quitação integral do valor da mensalidade do mês vigente e eventuais saldos de serviços já executados;
b) Multa rescisória de 10% (dez por cento) calculada sobre o valor total das parcelas que faltariam para o encerramento do contrato.

7.4. O valor total da multa e dos saldos pendentes deverá ser pago em parcela única em até 5 (cinco) dias úteis a contar da data de formalização do pedido de cancelamento.

7.5. Na apuração dos saldos, serão abatidos os valores já pagos, sem cobrança em duplicidade do mesmo período ou serviço. A aplicação desta cláusula observará a legislação aplicável e os direitos das partes nas hipóteses de justa causa."""
MATERIALS_TERMS = """ENVIO DE MATERIAIS E PRAZOS DE POSTAGEM
O envio dos materiais necessários às divulgações em Stories, às publicações em colaboração (Collabs) e ao uso da logomarca é de inteira responsabilidade do CONTRATANTE (empresa cliente). Os arquivos, informações e autorizações deverão ser encaminhados ao CONTRATADO dentro do prazo acordado no planejamento ou nos canais de atendimento, em formato adequado à publicação.

Quando uma postagem deixar de ocorrer exclusivamente porque o CONTRATANTE não enviou os materiais necessários no prazo combinado, as datas e os dias de divulgação já transcorridos não serão repostos. O recebimento posterior dos arquivos não gera reposição automática dessas datas, salvo novo ajuste expresso entre as partes. Esta condição não afasta a responsabilidade do CONTRATADO por falhas que lhe sejam atribuíveis nem os direitos previstos na legislação aplicável."""
VISITS_TERMS = """AGENDAMENTO DE VISITAS E IMPREVISTOS
As visitas à loja ou ao estabelecimento do CONTRATANTE deverão ser agendadas com antecedência, com data e horário confirmados entre as partes, de acordo com a disponibilidade e o escopo contratado.

Em caso de imprevisto que impeça a visita combinada, o CONTRATADO deverá informar a empresa cliente assim que tomar conhecimento do impedimento e combinar uma nova data. Caso o impedimento seja do CONTRATANTE, este também deverá avisar o CONTRATADO assim que possível. O reagendamento dependerá de confirmação entre as partes e deverá ser registrado pelos canais de atendimento."""


def update_service_terms(apps, schema_editor):
    Template = apps.get_model("agency", "ContractTemplate")
    for template in Template.objects.filter(name=TEMPLATE_NAME):
        original = template.content
        additions = []
        if TERMINATION_HEADING not in template.content:
            if PREVIOUS_TERMINATION in template.content:
                template.content = template.content.replace(PREVIOUS_TERMINATION, TERMINATION_TERMS, 1)
            else:
                additions.append(TERMINATION_TERMS)
        if MATERIALS_HEADING not in template.content:
            additions.append(MATERIALS_TERMS)
        if VISITS_HEADING not in template.content:
            additions.append(VISITS_TERMS)
        if not additions and template.content == original:
            continue
        addition = "\n\n".join(additions)
        closing = "Ao aceitar este documento, as partes declaram que leram e concordam com os termos acima."
        if additions and closing in template.content:
            template.content = template.content.replace(closing, addition + "\n\n" + closing, 1)
        elif additions:
            template.content = template.content.rstrip() + "\n\n" + addition
        # Existing issued/signed Contract.terms snapshots are deliberately untouched.
        template.save(update_fields=["content", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [("agency", "0008_organizationsettings_compact_logo_and_more")]
    operations = [migrations.RunPython(update_service_terms, migrations.RunPython.noop)]
