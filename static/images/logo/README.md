# Logo Personalizado

Este directorio contiene el logo personalizado de SoyNadia.

## Ubicación del logo

Coloca tu archivo de logo aquí. Formatos recomendados:
- `logo.png` - Logo principal (formato PNG con transparencia)
- `logo.svg` - Logo vectorial (recomendado para mejor calidad)
- `logo-white.png` - Versión blanca del logo (para fondos oscuros)
- `favicon.ico` - Favicon del sitio

## Uso en templates

Para usar el logo en los templates de Django, utiliza:

```django
{% load static %}
<img src="{% static 'images/logo/logo.png' %}" alt="SoyNadia Logo">
```

## Tamaños recomendados

- **Logo principal**: 200x50px o 300x75px
- **Favicon**: 32x32px o 16x16px
- **Logo SVG**: Sin restricciones de tamaño (escalable)
