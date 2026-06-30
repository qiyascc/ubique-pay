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
    provider_token = forms.CharField(
        max_length=255, required=False,
        widget=forms.TextInput(attrs={"placeholder": "tok_… (from card vault)"}),
    )


class RecipientForm(forms.Form):
    name = forms.CharField(max_length=128, label="Recipient name")
    card_number = forms.CharField(
        label="Recipient card number",
        widget=forms.TextInput(attrs={"placeholder": "4111 1111 1111 1111", "inputmode": "numeric"}),
    )


class SendForm(forms.Form):
    source_card = forms.ChoiceField(label="Pay from")
    saved_recipient = forms.ChoiceField(required=False, label="Recipient")
    recipient_card_number = forms.CharField(required=False, label="…or new card number",
                                            widget=forms.TextInput(attrs={"placeholder": "4111 1111 1111 1111"}))
    recipient_name = forms.CharField(max_length=128, required=False, label="Recipient name")
    send_amount = forms.DecimalField(min_value=0, decimal_places=2, max_digits=12)
    send_currency = forms.ChoiceField(choices=[(c, c) for c in ("USD", "EUR", "AZN", "TRY")])
    receive_currency = forms.ChoiceField(choices=[(c, c) for c in ("AZN", "TRY", "EUR", "USD")])

    def __init__(self, *args, card_choices=(), recipient_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source_card"].choices = card_choices
        self.fields["saved_recipient"].choices = [("", "— New card —")] + list(recipient_choices)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("saved_recipient") and not cleaned.get("recipient_card_number"):
            raise forms.ValidationError("Pick a saved recipient or enter a card number.")
        return cleaned
