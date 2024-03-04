from django import forms

import pytz

class strategyCommentsForm(forms.Form) :
    comments = forms.CharField(widget=forms.Textarea)
    
class userTimezoneForm(forms.Form):
    timezone = forms.ChoiceField(choices=[(x, x) for x in pytz.common_timezones])

class configForm (forms.Form):
    configMaxBet = forms.DecimalField(widget=forms.NumberInput,decimal_places=2)
    configProcessEnabled = forms.BooleanField(widget=forms.CheckboxInput,required=False)
