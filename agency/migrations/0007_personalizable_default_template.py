from importlib import import_module
from django.db import migrations


def personalize_pristine_template(apps, schema_editor):
    original = import_module('agency.migrations.0003_seed_default_contract_template')
    template_model = apps.get_model('agency', 'ContractTemplate')
    replacement = original.DEFAULT_TEMPLATE_CONTENT.replace(
        'o PORTAL VERDADE CEARÁ, doravante denominado CONTRATADO',
        '[[empresa_razao_social]], documento [[empresa_documento]], com endereço em [[empresa_endereco]], doravante denominado CONTRATADO',
    )
    # Only the untouched seeded template is upgraded; user edits and contract snapshots remain unchanged.
    template_model.objects.filter(name=original.DEFAULT_TEMPLATE_NAME, content=original.DEFAULT_TEMPLATE_CONTENT).update(content=replacement)


class Migration(migrations.Migration):
    dependencies = [('agency', '0006_financialentry_billing_month_and_more')]
    operations = [migrations.RunPython(personalize_pristine_template, migrations.RunPython.noop)]
