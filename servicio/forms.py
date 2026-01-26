from django import forms
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from .models import (Reporte)


class ReporteAdminForm(forms.ModelForm):
    usuario = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label="Ingeniero Encargado"
    )
    
    class Meta:
        model = Reporte
        fields = '__all__'
        
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'fecha_cierre': forms.DateInput(attrs={'type': 'date'}),
        }