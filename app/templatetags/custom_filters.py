from django import template

register = template.Library()

@register.filter
def get(dictionary, key):
    """
    Permite acceder a un valor de un diccionario por su clave.
    Ejemplo de uso en plantilla: `{{ diccionario|get:clave }}`
    """
    return dictionary.get(key)
