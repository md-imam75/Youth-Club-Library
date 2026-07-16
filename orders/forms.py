"""
orders/forms.py
"""

from django import forms
from .models import Order



class CheckoutForm(forms.ModelForm):
    delivery_option = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'id': 'id_delivery_option'})
    )
    payment_method = forms.ChoiceField(
        choices=Order.PAYMENT_METHOD_CHOICES,
        widget=forms.Select(attrs={'id': 'id_payment_method'})
    )
    transaction_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'id': 'id_transaction_id',
            'placeholder': 'Enter bKash Transaction ID'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import DeliveryOption
        choices = []
        for opt in DeliveryOption.objects.filter(is_active=True):
            label = f'{opt.label} — ৳{opt.cost:.0f}' if opt.cost > 0 else opt.label
            choices.append((opt.code, label))
        self.fields['delivery_option'].choices = choices
    delivery_address = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Full delivery address (street, thana, district)'
        })
    )

    class Meta:
        model = Order
        fields = ['delivery_option', 'delivery_address', 'payment_method', 'transaction_id']

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get('payment_method')
        txn_id = cleaned.get('transaction_id', '').strip()
        delivery_key = cleaned.get('delivery_option')
        # Delivery address required for home delivery options
        if delivery_key in ('inside_ctg', 'outside_ctg'):
            if not cleaned.get('delivery_address', '').strip():
                raise forms.ValidationError('Delivery address is required for home delivery.')
        if method == 'bKash' and not txn_id:
            raise forms.ValidationError('Transaction ID is required for bKash payments.')
        return cleaned


from .models import DeliveryOption

class DeliveryOptionForm(forms.ModelForm):
    class Meta:
        model = DeliveryOption
        fields = ['label', 'code', 'cost', 'is_active']
        widgets = {
            'label': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. Free Delivery — Kazir Dewri'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. free_kazir_dewri'
            }),
            'cost': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. 0.00',
                'step': '0.01'
            }),
        }
