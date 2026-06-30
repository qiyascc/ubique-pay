from django import forms


class PhoneForm(forms.Form):
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "+994 50 123 45 67", "autofocus": True}),
    )


class CodeForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        widget=forms.TextInput(attrs={"placeholder": "123456", "inputmode": "numeric", "autofocus": True}),
    )


class CardForm(forms.Form):
    brand = forms.ChoiceField(choices=[("Visa", "Visa"), ("Mastercard", "Mastercard")])
    last4 = forms.CharField(max_length=4, min_length=4,
                            widget=forms.TextInput(attrs={"placeholder": "1436"}))
    # In production this is a token from the card-tokenization SDK, never the PAN.
    provider_token = forms.CharField(
        max_length=255, required=False,
        widget=forms.TextInput(attrs={"placeholder": "tok_… (from card vault)"}),
    )


class SendForm(forms.Form):
    source_card = forms.ChoiceField(label="Pay from")
    send_amount = forms.DecimalField(min_value=0, decimal_places=2, max_digits=12)
    send_currency = forms.ChoiceField(choices=[(c, c) for c in ("USD", "EUR", "AZN", "TRY")])
    receive_currency = forms.ChoiceField(choices=[(c, c) for c in ("AZN", "TRY", "EUR", "USD")])
    recipient_card_last4 = forms.CharField(max_length=4, min_length=4, label="Recipient card (last 4)")
    recipient_reference = forms.CharField(max_length=128, required=False, label="Recipient name")

    def __init__(self, *args, card_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source_card"].choices = card_choices
