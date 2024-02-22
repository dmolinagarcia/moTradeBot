from django import forms

import pytz

class strategyCommentsForm(forms.Form) :
    comments = forms.CharField(widget=forms.Textarea)
    
class userTimezoneForm(forms.Form):
    timezone = forms.ChoiceField(choices=[(x, x) for x in pytz.common_timezones])