"""
URL configuration for gih project.
# ...existing code...

# Serve media files (room_images) in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path

from core.views import (
    # Original views
    home, guests, reservations, rooms, housekeeping, maintenance, services, 
    guest_login, guest_logout, guest_register, housekeeper_login, staff_register, menu, 
    loyalty_page, newsletter,
    start_payment, payment_success, payment_cancel, add_room, admin_login, admin_dashboard, room_edit, room_delete,
    admin_reports,
    # User profile views (unified for all user types)
    user_profile, change_password,
    # (guest-specific views removed; using unified user_profile/change_password)
    # New CRUD views
    guest_list, guest_create, guest_detail, guest_update, guest_delete,
    reservation_list, reservation_create, reservation_detail, reservation_update, reservation_delete,
    housekeeping_list, housekeeping_create, housekeeping_detail, housekeeping_update, housekeeping_delete,
    maintenance_list, maintenance_create, maintenance_detail, maintenance_update, maintenance_delete,
    maintenance_comments_api,
    service_list, service_create, service_detail, service_update, service_delete,
    # Staff CRUD views
    staff_list, staff_create, staff_detail, staff_update, staff_delete,
    # API endpoints
    api_room_rate, api_room_booked_dates, api_guest_points_info,
)

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),
    
    # Original paths
    path('register/', guest_register, name='guest_register'),
    path('home/', home, name='home_redirect'),
    path('', home, name='home'),
    path('newsletter/', newsletter, name='newsletter'),
    path('guests/', guests, name='guests'),
    path('reservations/', reservations, name='reservations'),
    path('rooms/', rooms, name='rooms'),
    path('loyalty/', loyalty_page, name='loyalty'),
    path('rooms/<int:pk>/edit/', room_edit, name='room_edit'),
    path('rooms/<int:pk>/delete/', room_delete, name='room_delete'),
    path('housekeeping/', housekeeping, name='housekeeping'),
    path('maintenance/', maintenance, name='maintenance'),
    path('services/', services, name='services'),
    path('login/', guest_login, name='guest_login'),
    path('logout/', guest_logout, name='guest_logout'),
    path('profile/', user_profile, name='user_profile'),
    path('profile/change-password/', change_password, name='change_password'),
    # legacy guest-specific routes removed
    path('housekeeper_login/', housekeeper_login, name='housekeeper_login'),
    path('staff_register/', staff_register, name='staff_register'),
    path('menu/', menu, name='menu'),
    path('start-payment/', start_payment, name='start_payment'),
    path('payment/success/', payment_success, name='payment_success'),
    path('payment/cancel/', payment_cancel, name='payment_cancel'),
    path('admin-frontend/add-room/', add_room, name='add_room'),
    path('admin-frontend/login/', admin_login, name='admin_login'),
    path('admin-frontend/dashboard/', admin_dashboard, name='admin_dashboard'),
    path('admin-frontend/reports/', admin_reports, name='admin_reports'),
    
    # Guest CRUD paths
    path('management/guests/', guest_list, name='guest_list'),
    path('management/guests/create/', guest_create, name='guest_create'),
    path('management/guests/<int:pk>/', guest_detail, name='guest_detail'),
    path('management/guests/<int:pk>/edit/', guest_update, name='guest_update'),
    path('management/guests/<int:pk>/delete/', guest_delete, name='guest_delete'),
    
    # Staff CRUD paths
    path('management/staff/', staff_list, name='staff_list'),
    path('management/staff/create/', staff_create, name='staff_create'),
    path('management/staff/<int:pk>/', staff_detail, name='staff_detail'),
    path('management/staff/<int:pk>/edit/', staff_update, name='staff_update'),
    path('management/staff/<int:pk>/delete/', staff_delete, name='staff_delete'),
    
    # Reservation CRUD paths
    path('management/reservations/', reservation_list, name='reservation_list'),
    path('management/reservations/create/', reservation_create, name='reservation_create'),
    path('management/reservations/<int:pk>/', reservation_detail, name='reservation_detail'),
    path('management/reservations/<int:pk>/edit/', reservation_update, name='reservation_update'),
    path('management/reservations/<int:pk>/delete/', reservation_delete, name='reservation_delete'),
    
    # Housekeeping CRUD paths
    path('management/housekeeping/', housekeeping_list, name='housekeeping_list'),
    path('management/housekeeping/create/', housekeeping_create, name='housekeeping_create'),
    path('management/housekeeping/<int:pk>/', housekeeping_detail, name='housekeeping_detail'),
    path('management/housekeeping/<int:pk>/edit/', housekeeping_update, name='housekeeping_update'),
    path('management/housekeeping/<int:pk>/delete/', housekeeping_delete, name='housekeeping_delete'),
    
    # Maintenance CRUD paths
    path('management/maintenance/', maintenance_list, name='maintenance_list'),
    path('management/maintenance/create/', maintenance_create, name='maintenance_create'),
    path('management/maintenance/<int:pk>/', maintenance_detail, name='maintenance_detail'),
    path('management/maintenance/<int:pk>/comments/', maintenance_comments_api, name='maintenance_comments_api'),
    path('management/maintenance/<int:pk>/edit/', maintenance_update, name='maintenance_update'),
    path('management/maintenance/<int:pk>/delete/', maintenance_delete, name='maintenance_delete'),
    
    # Service Request CRUD paths
    path('management/services/', service_list, name='service_list'),
    path('management/services/create/', service_create, name='service_create'),
    path('management/services/<int:pk>/', service_detail, name='service_detail'),
    path('management/services/<int:pk>/edit/', service_update, name='service_update'),
    path('management/services/<int:pk>/delete/', service_delete, name='service_delete'),
    
    # API endpoints
    path('api/room-rate/<int:room_id>/', api_room_rate, name='api_room_rate'),
    path('api/room-booked-dates/<int:room_id>/', api_room_booked_dates, name='api_room_booked_dates'),
    path('api/guest-points/<int:guest_id>/', api_guest_points_info, name='api_guest_points'),
]

# Serve media files (room_images) in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom error handlers
handler403 = 'core.views.error_403'
handler404 = 'core.views.error_404'
handler500 = 'core.views.error_500'
