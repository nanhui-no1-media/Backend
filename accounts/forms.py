from django import forms
from django.contrib.auth.models import User

from .models import Profile


class LoginForm(forms.Form):
    password = forms.CharField(required=True)
    username = forms.CharField(required=False)
    email = forms.EmailField(required=False)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("username") and not cleaned.get("email"):
            raise forms.ValidationError("Username or email is required")
        return cleaned

    def get_username(self):
        username = self.cleaned_data.get("username")
        if username:
            return username
        email = self.cleaned_data["email"]
        try:
            return User.objects.get(email=email).username
        except User.DoesNotExist:
            return None


class PasswordResetForm(forms.Form):
    email = forms.EmailField(required=True)


class PasswordResetConfirmForm(forms.Form):
    uid = forms.CharField(required=True)
    token = forms.CharField(required=True)
    new_password = forms.CharField(required=True)


class ProfileForm(forms.Form):
    nickname = forms.CharField(max_length=50, required=False)
    birthday = forms.DateField(required=False)
    gender = forms.ChoiceField(choices=[("", "")] + Profile.GENDER_CHOICES, required=False)
    bio = forms.CharField(max_length=500, required=False)


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(required=True)
    new_password = forms.CharField(required=True, min_length=8)
