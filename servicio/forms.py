from django import forms
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from .models import (Reporte)
from app.models import Equipo



class ReporteAdminForm(forms.ModelForm):
    usuario = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label="Ingeniero Encargado"
    )

    equipo = forms.ModelChoiceField(
        queryset=Equipo.objects.all(),
        required=False,
        label="Equipo"
    )
    
    class Meta:
        model = Reporte
        fields = '__all__'
        
        widgets = {
            
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'fecha_cierre': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            # Preserve existing classes and add 'input-box'
            existing = field.widget.attrs.get('class', '')
            classes = existing.split() if existing else []
            if 'input-box' not in classes:
                classes.append('input-box')
            field.widget.attrs['class'] = ' '.join(classes)