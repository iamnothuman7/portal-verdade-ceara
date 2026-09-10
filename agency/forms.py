from django import forms


class ContractSignatureForm(forms.Form):
    signer_name = forms.CharField(label="Nome completo", max_length=160)
    signer_tax_id = forms.CharField(label="CPF", max_length=24)
    signer_email = forms.EmailField(label="E-mail")
    consent = forms.BooleanField(
        label="Li o contrato e concordo com todos os termos. Confirmo que os dados acima são verdadeiros e que este aceite representa minha assinatura eletrônica."
    )
