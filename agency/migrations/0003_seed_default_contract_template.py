from django.db import migrations


DEFAULT_TEMPLATE_NAME = "Prestação de serviços de comunicação"
DEFAULT_TEMPLATE_CONTENT = """CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE COMUNICAÇÃO

Pelo presente instrumento, o PORTAL VERDADE CEARÁ, doravante denominado CONTRATADO, e [[cliente_razao_social]], documento [[cliente_documento]], com endereço em [[cliente_endereco]], doravante denominado CONTRATANTE, ajustam a prestação dos serviços descritos abaixo.

1. OBJETO
O presente contrato tem por objeto a criação, produção e/ou divulgação de conteúdo de comunicação referente ao pacote [[contrato_nome]], conforme planejamento e aprovação entre as partes.

2. PACOTE MENSAL
O pacote mensal contratado compreende: [[pacote_mensal]]. Ajustes de formato, pauta e cronograma devem ser combinados entre as partes e registrados pelos canais de atendimento utilizados no projeto.

3. VIGÊNCIA
Este contrato vigora de [[data_inicio]] a [[data_fim]]. Qualquer renovação ou alteração de escopo deverá ser formalizada pelas partes.

4. VALOR E PAGAMENTO
Pelos serviços, o CONTRATANTE pagará o valor mensal de [[valor_mensal]], com vencimento no dia [[dia_vencimento]] de cada mês.

5. RESPONSABILIDADES DO CONTRATANTE
O CONTRATANTE fornecerá informações, arquivos e aprovações necessários em tempo hábil, declarando possuir autorização para uso dos materiais enviados.

6. RESPONSABILIDADES DO CONTRATADO
O CONTRATADO executará os serviços com cuidado profissional, respeitando o escopo, o cronograma acordado e as aprovações do CONTRATANTE.

7. CANCELAMENTO E RESCISÃO
A rescisão, os prazos de aviso e os valores eventualmente devidos seguirão as condições comerciais ajustadas entre as partes e a legislação aplicável.

8. ASSINATURA ELETRÔNICA
As partes reconhecem como válido o aceite eletrônico registrado pelo sistema, acompanhado de data, hora e comprovante criptográfico.

Ao aceitar este documento, as partes declaram que leram e concordam com os termos acima."""


def create_default_template(apps, schema_editor):
    ContractTemplate = apps.get_model("agency", "ContractTemplate")
    ContractTemplate.objects.get_or_create(
        name=DEFAULT_TEMPLATE_NAME,
        defaults={"content": DEFAULT_TEMPLATE_CONTENT, "is_active": True},
    )


def remove_default_template(apps, schema_editor):
    ContractTemplate = apps.get_model("agency", "ContractTemplate")
    ContractTemplate.objects.filter(name=DEFAULT_TEMPLATE_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [("agency", "0002_contracttemplate_contract_template")]
    operations = [migrations.RunPython(create_default_template, remove_default_template)]
