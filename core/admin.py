from django.contrib import admin
from .models import Guest, Room, Reservation, Staff, Housekeeping, Maintenance, ServiceRequest
admin.site.register(Guest)
admin.site.register(Room)
admin.site.register(Reservation)
admin.site.register(Staff)
admin.site.register(Housekeeping)
admin.site.register(Maintenance)
admin.site.register(ServiceRequest)
