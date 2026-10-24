import math
from django.core.exceptions import ValidationError


def validate_reading_value(value, sensor):
    if not math.isfinite(value):
        raise ValidationError('Debe ser un número finito.')
    if sensor:
        unit = sensor.unidad.strip().lower()
        if unit == '%' and not 0 <= value <= 100:
            raise ValidationError('Un porcentaje debe estar entre 0 y 100.')
        if unit in ('cm', 'm', 'mm') and value < 0:
            raise ValidationError('La distancia no puede ser negativa.')
