from django.conf import settings
import logging
import requests
from django.db import models
from django import forms
from django.forms import ModelForm, Form, CharField, ChoiceField, Textarea, HiddenInput, BooleanField, ValidationError
from allauth.account.forms import SignupForm, LoginForm
import allauth.account.views
import phonenumbers
from pushbullet import Pushbullet, PushbulletError

from .widgets import CustomRadioSelectWidget
from .models import *

LOGGER = logging.getLogger(__name__)


class SocialAccountAwareLoginForm(LoginForm):
    no_password_yet: bool = False

    def clean(self):
        try:
            return super(SocialAccountAwareLoginForm, self).clean()
        except forms.ValidationError as err:
            if err.message == self.error_messages['email_password_mismatch']:
                email = self.user_credentials().get('email', None)
                if email is not None:
                    user = User.objects.filter(email=email).first()
                    if user is not None and not user.has_usable_password():
                        has_social_accounts = user.socialaccount_set.exists()
                        if has_social_accounts:
                            self.no_password_yet = True
            raise err


class PrinterForm(ModelForm):
    class Meta:
        model = Printer
        fields = ['name', 'action_on_failure', 'tools_off_on_pause', 'bed_off_on_pause',
                  'detective_sensitivity', 'retract_on_pause', 'lift_z_on_pause']
        widgets = {
            'action_on_failure': CustomRadioSelectWidget(choices=Printer.ACTION_ON_FAILURE),
        }


class RecaptchaSignupForm(SignupForm):
    recaptcha_token = CharField(required=True)

    def clean(self):
        super().clean()

        # captcha verification
        data = {
            'response': self.cleaned_data['recaptcha_token'],
            'secret': settings.RECAPTCHA_SECRET_KEY
        }
        response = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)

        if response.status_code == requests.codes.ok:
            if response.json()['success'] and response.json()['action'] == 'signup_form':
                LOGGER.debug('Captcha valid for user={}'.format(self.cleaned_data.get('email')))
            else:
                LOGGER.warn('Captcha invalid for user={}'.format(self.cleaned_data.get('email')))
                raise ValidationError('ReCAPTCHA is invalid.')
        else:
            LOGGER.error('Cannot validate reCAPTCHA for user={}'.format(self.cleaned_data.get('email')))

        return self.cleaned_data
