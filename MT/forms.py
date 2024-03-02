from django import forms

import pytz

class strategyCommentsForm(forms.Form) :
    comments = forms.CharField(widget=forms.Textarea)
    
class userTimezoneForm(forms.Form):
    timezone = forms.ChoiceField(choices=[(x, x) for x in pytz.common_timezones])

class configForm (forms.Form):
    configMaxBet = forms.IntegerField(widget=forms.NumberInput)
    configProcessEnabled = forms.BooleanField(widget=forms.CheckboxInput,required=False)
