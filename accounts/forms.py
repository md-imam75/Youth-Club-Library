"""
accounts/forms.py
"""

from django import forms
from .models import CustomUser, UserMembership, MembershipPlan


class CustomSignupForm(forms.Form):
    """
    Extra fields added to allauth's signup form.
    Registered via ACCOUNT_SIGNUP_FORM_CLASS in settings.
    allauth 0.57 calls signup(request, user) after user creation.
    """
    first_name = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Last Name'})
    )
    phone = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Phone (e.g. 01XXXXXXXXX)'})
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'placeholder': 'Your delivery address', 'rows': 2})
    )

    def signup(self, request, user):
        """Called by allauth after the user object is saved."""
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.phone = self.cleaned_data.get('phone', '')
        user.address = self.cleaned_data.get('address', '')
        user.save()


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'phone', 'address', 'profile_image', 'bio']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'phone': forms.TextInput(attrs={'class': 'form-input'}),
            'address': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'bio': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }


class MembershipApplicationForm(forms.ModelForm):
    class Meta:
        model = UserMembership
        fields = ['plan', 'payment_method', 'transaction_id']
        widgets = {
            'plan': forms.HiddenInput(),
            'payment_method': forms.Select(attrs={'id': 'id_payment_method'}),
            'transaction_id': forms.TextInput(attrs={
                'id': 'id_transaction_id',
                'placeholder': 'Enter bKash transaction ID'
            }),
        }

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get('payment_method')
        txn_id = cleaned.get('transaction_id', '').strip()
        if method == 'bKash' and not txn_id:
            raise forms.ValidationError('Transaction ID is required for bKash payments.')
        return cleaned


class MembershipPlanForm(forms.ModelForm):
    """Form for admin to create/edit membership plans."""
    # characteristics stored as JSON list — edit as textarea, one feature per line
    features_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'rows': 5,
            'placeholder': 'One feature per line, e.g.:\nBorrow up to 3 books\nFree delivery\nPriority access',
        }),
        label='Plan Features (one per line)',
        required=False,
    )

    class Meta:
        model = MembershipPlan
        fields = ['name', 'price', 'duration_days', 'is_active', 'is_popular', 'sort_order']
        widgets = {
            'name':         forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Monthly, Quarterly'}),
            'price':        forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': '0.00'}),
            'duration_days':forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '30'}),
            'sort_order':   forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '0 = first'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-fill features_text from existing characteristics
        if self.instance and self.instance.pk and self.instance.characteristics:
            chars = self.instance.characteristics
            if isinstance(chars, list):
                self.fields['features_text'].initial = '\n'.join(chars)

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Convert textarea lines back to JSON list
        raw = self.cleaned_data.get('features_text', '')
        instance.characteristics = [
            line.strip() for line in raw.splitlines() if line.strip()
        ]
        if commit:
            instance.save()
        return instance
