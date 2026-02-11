from django import template

register = template.Library()


@register.filter
def multiply(value, arg):
    """Multiplies the value by the argument."""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def apply_discount(value, discount_percentage):
    """Applies a discount percentage to a value."""
    try:
        value = float(value)
        discount = float(discount_percentage)
        return value * (1 - discount / 100)
    except (ValueError, TypeError):
        return value