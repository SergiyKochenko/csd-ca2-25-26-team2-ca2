from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django import forms
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from decimal import Decimal, InvalidOperation
from .forms import (
	GuestForm,
	ReservationForm,
	RoomForm,
	HousekeepingForm,
	MaintenanceRequestGuestForm,
	MaintenanceRequestAdminForm,
	MaintenanceRequestStatusForm,
	MaintenanceRequestCommentForm,
	ServiceRequestForm,
	GuestProfileForm,
	GuestPasswordChangeForm,
	StaffProfileForm,
	StaffPasswordChangeForm,
	StaffForm,
	StaffRegistrationForm,
	GuestRegistrationForm,
	PublicReservationRequestForm,
	GuestLoginForm,
	StaffLoginForm,
	ServiceOrderForm,
	ReportFilterForm,
)
from .models import (
	Guest,
	Reservation,
	Room,
	Housekeeping,
	MaintenanceRequest,
	MaintenanceRequestComment,
	ServiceRequest,
	Staff,
)
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_protect
from functools import wraps
from django.core.cache import cache


def check_rate_limit(request, key: str, limit: int = 5, window: int = 300) -> bool:
	"""Simple cache-backed rate limit hook (limit attempts per window)."""
	cache_key = f"rl:{key}"
	try:
		current = cache.get(cache_key)
		if current is None:
			cache.set(cache_key, 1, window)
			return True
		current = cache.incr(cache_key)
		cache.set(cache_key, current, window)
		return current <= limit
	except Exception:
		# If cache is unavailable, do not block the request
		return True

# Admin login form
class AdminLoginForm(forms.Form):
	username = forms.CharField()
	password = forms.CharField(widget=forms.PasswordInput)

def admin_login(request):
	if request.method == 'POST':
		if not check_rate_limit(request, f"admin_login:{request.META.get('REMOTE_ADDR')}"):
			messages.error(request, 'Too many login attempts. Please wait and try again.')
			form = AdminLoginForm(request.POST)
		else:
			form = AdminLoginForm(request.POST)
			if form.is_valid():
				username = form.cleaned_data['username']
				password = form.cleaned_data['password']
				user = authenticate(request, username=username, password=password)
				if user is not None and user.is_staff:
					login(request, user)
					return redirect('admin_dashboard')
				form.add_error(None, 'Invalid credentials')
	else:
		form = AdminLoginForm()
	context = get_user_context(request)
	context['form'] = form
	return render(request, 'admin_login.html', context)

def generate_admin_report(
	start_date,
	end_date,
	include_occupancy=True,
	include_reservations=True,
	include_services=True,
	include_housekeeping=True,
	include_maintenance=True,
):
	"""Aggregate occupancy, reservations, service, housekeeping, and maintenance metrics for the period."""

	data = {}
	reservation_statuses = ['confirmed', 'checked-in', 'checked-out']
	period_days = (end_date - start_date).days + 1
	total_rooms = Room.objects.count()
	total_room_nights = total_rooms * period_days if total_rooms and period_days > 0 else 0

	reservations_qs = Reservation.objects.filter(
		status__in=reservation_statuses,
		check_in__lt=end_date + timedelta(days=1),
		check_out__gt=start_date,
	) if include_reservations or include_occupancy else Reservation.objects.none()

	if include_occupancy:
		booked_room_nights = 0
		for res in reservations_qs:
			overlap_start = max(res.check_in, start_date)
			overlap_end = min(res.check_out, end_date + timedelta(days=1))
			nights = (overlap_end - overlap_start).days
			if nights > 0:
				booked_room_nights += nights

		occupancy_rate = (booked_room_nights / total_room_nights * 100) if total_room_nights else 0

		daily_occupancy = []
		current = start_date
		while current <= end_date:
			occupied = reservations_qs.filter(check_in__lte=current, check_out__gt=current).count()
			daily_rate = (occupied / total_rooms * 100) if total_rooms else 0
			daily_occupancy.append({
				'date': current,
				'occupied_rooms': occupied,
				'occupancy_rate': round(daily_rate, 2),
			})
			current += timedelta(days=1)

		data.update({
			'occupancy_rate': round(occupancy_rate, 2) if occupancy_rate else 0,
			'booked_room_nights': booked_room_nights,
			'total_room_nights': total_room_nights,
			'daily_occupancy': daily_occupancy,
		})

	if include_reservations:
		data['reservation_count'] = reservations_qs.count()
		reservations_summary = []
		for res in reservations_qs.select_related('guest', 'room'):
			reservations_summary.append({
				'id': res.id,
				'guest': f"{res.guest.first_name} {res.guest.last_name}" if res.guest else 'Unknown',
				'room': res.room.number if res.room else 'N/A',
				'status': res.status,
				'check_in': res.check_in,
				'check_out': res.check_out,
			})
		data['reservations'] = reservations_summary

	if include_services:
		service_qs = ServiceRequest.objects.filter(
			timestamp__date__gte=start_date,
			timestamp__date__lte=end_date,
		).select_related('guest', 'reservation__room')
		response_times = []
		service_summary = []
		for req in service_qs:
			if req.fulfilled_time:
				delta = req.fulfilled_time - req.timestamp
				response_times.append(delta.total_seconds() / 60)
			service_summary.append({
				'id': req.id,
				'guest': f"{req.guest.first_name} {req.guest.last_name}" if req.guest else 'Unknown',
				'room': req.reservation.room.number if req.reservation and req.reservation.room else 'N/A',
				'request_type': req.request_type,
				'timestamp': req.timestamp,
				'fulfilled_time': req.fulfilled_time,
				'charge': req.charge,
			})

		avg_response_minutes = sum(response_times) / len(response_times) if response_times else None
		data.update({
			'service_request_count': service_qs.count(),
			'completed_service_count': len(response_times),
			'avg_response_minutes': round(avg_response_minutes, 1) if avg_response_minutes is not None else None,
			'service_requests': service_summary,
		})

	if include_housekeeping:
		housekeeping_qs = Housekeeping.objects.filter(date__gte=start_date, date__lte=end_date).select_related('room', 'staff')
		housekeeping_summary = []
		for hk in housekeeping_qs:
			housekeeping_summary.append({
				'id': hk.id,
				'room': hk.room.number if hk.room else 'N/A',
				'staff': hk.staff.name if hk.staff else 'Unassigned',
				'deep_cleaning': hk.deep_cleaning,
				'status': hk.status,
				'date': hk.date,
				'time_spent': hk.time_spent,
			})
		data.update({
			'housekeeping_count': housekeeping_qs.count(),
			'housekeeping': housekeeping_summary,
		})

	if include_maintenance:
		maintenance_qs = MaintenanceRequest.objects.filter(request_date__gte=start_date, request_date__lte=end_date).select_related('room', 'assigned_to')
		maintenance_summary = []
		for m in maintenance_qs:
			maintenance_summary.append({
				'id': m.id,
				'room': m.room.number if m.room else 'N/A',
				'type': m.get_type_display(),
				'status': m.get_status_display(),
				'date_requested': m.request_date,
				'assigned_to': m.assigned_to.name if m.assigned_to else 'Unassigned',
				'requested_by': m.requested_by_name,
			})
		data.update({
			'maintenance_count': maintenance_qs.count(),
			'maintenance': maintenance_summary,
		})

	return data


def export_admin_report_csv(report_data, start_date, end_date):
	"""Return a CSV download for the current report view."""

	response = HttpResponse(content_type='text/csv')
	response['Content-Disposition'] = f'attachment; filename="admin-report-{start_date}-to-{end_date}.csv"'
	writer = csv.writer(response)

	writer.writerow(['Report Range', start_date, end_date])

	if 'occupancy_rate' in report_data:
		writer.writerow(['Occupancy Rate (%)', report_data.get('occupancy_rate', 0)])
		writer.writerow(['Booked Room Nights', report_data.get('booked_room_nights', 0)])
		writer.writerow(['Total Room Nights', report_data.get('total_room_nights', 0)])

	if 'reservation_count' in report_data:
		writer.writerow(['Reservations', report_data.get('reservation_count', 0)])
		writer.writerow([])
		writer.writerow(['Reservation Details'])
		writer.writerow(['Guest', 'Room', 'Status', 'Check-in', 'Check-out'])
		for res in report_data.get('reservations', []):
			writer.writerow([
				res.get('guest'),
				res.get('room'),
				res.get('status'),
				res.get('check_in'),
				res.get('check_out'),
			])

	if 'service_request_count' in report_data:
		writer.writerow(['Service Requests', report_data.get('service_request_count', 0)])
		writer.writerow(['Completed Services', report_data.get('completed_service_count', 0)])
		writer.writerow(['Avg Service Response (minutes)', report_data.get('avg_response_minutes', 'N/A') or 'N/A'])
		writer.writerow([])
		writer.writerow(['Service Request Details'])
		writer.writerow(['Guest', 'Room', 'Type', 'Requested At', 'Fulfilled At', 'Charge'])
		for req in report_data.get('service_requests', []):
			writer.writerow([
				req.get('guest'),
				req.get('room'),
				req.get('request_type'),
				req.get('timestamp'),
				req.get('fulfilled_time') or '',
				req.get('charge'),
			])

	if 'housekeeping_count' in report_data:
		writer.writerow(['Housekeeping Tasks', report_data.get('housekeeping_count', 0)])
		writer.writerow([])
		writer.writerow(['Housekeeping Details'])
		writer.writerow(['Date', 'Room', 'Staff', 'Status', 'Deep Cleaning', 'Time Spent'])
		for hk in report_data.get('housekeeping', []):
			writer.writerow([
				hk.get('date'),
				hk.get('room'),
				hk.get('staff'),
				hk.get('status'),
				'Yes' if hk.get('deep_cleaning') else 'No',
				hk.get('time_spent') or '',
			])

	if 'maintenance_count' in report_data:
		writer.writerow(['Maintenance Requests', report_data.get('maintenance_count', 0)])
		writer.writerow([])
		writer.writerow(['Maintenance Details'])
		writer.writerow(['Date', 'Room', 'Type', 'Priority', 'Status', 'Assigned To', 'Cost'])
		for m in report_data.get('maintenance', []):
			writer.writerow([
				m.get('date_requested'),
				m.get('room'),
				m.get('type'),
				m.get('priority'),
				m.get('status'),
				m.get('assigned_to'),
				m.get('cost'),
			])

	if report_data.get('daily_occupancy'):
		writer.writerow([])
		writer.writerow(['Date', 'Occupied Rooms', 'Daily Occupancy (%)'])
		for row in report_data.get('daily_occupancy', []):
			writer.writerow([
				row.get('date').isoformat() if row.get('date') else '',
				row.get('occupied_rooms', 0),
				row.get('occupancy_rate', 0),
			])

	return response


# Only staff can access dashboard
@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_dashboard(request):
	context = get_user_context(request)
	return render(request, 'admin_dashboard.html', context)


@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_reports(request):
	context = get_user_context(request)

	default_end = date.today()
	default_start = default_end - timedelta(days=29)

	form = ReportFilterForm(request.GET or None, initial={
		'start_date': default_start,
		'end_date': default_end,
	})

	if form.is_valid():
		start_date = form.cleaned_data['start_date']
		end_date = form.cleaned_data['end_date']
		include_occupancy = form.cleaned_data['include_occupancy']
		include_reservations = form.cleaned_data['include_reservations']
		include_services = form.cleaned_data['include_services']
		include_housekeeping = form.cleaned_data['include_housekeeping']
		include_maintenance = form.cleaned_data['include_maintenance']
	else:
		start_date = default_start
		end_date = default_end
		include_occupancy = True
		include_reservations = True
		include_services = True
		include_housekeeping = True
		include_maintenance = True

	report_data = generate_admin_report(
		start_date,
		end_date,
		include_occupancy=include_occupancy,
		include_reservations=include_reservations,
		include_services=include_services,
		include_housekeeping=include_housekeeping,
		include_maintenance=include_maintenance,
	)

	if request.GET.get('export') == 'csv':
		return export_admin_report_csv(report_data, start_date, end_date)

	context.update({
		'report_form': form,
		'report_data': report_data,
		'report_start': start_date,
		'report_end': end_date,
		'include_occupancy': include_occupancy,
		'include_reservations': include_reservations,
		'include_services': include_services,
		'include_housekeeping': include_housekeeping,
		'include_maintenance': include_maintenance,
	})
	return render(request, 'admin_reports.html', context)

# Admin: Add Room view
@staff_member_required
def add_room(request):
	if request.method == 'POST':
		form = RoomForm(request.POST, request.FILES)
		if form.is_valid():
			form.save()
			from django.contrib import messages
			messages.success(request, 'Room added successfully!')
			return redirect('rooms')
	else:
		form = RoomForm()
	context = get_user_context(request)
	context['form'] = form
	return render(request, 'add_room.html', context)


# Entry point for Stripe payment integration
from django.views.decorators.csrf import csrf_protect
from django.urls import reverse
from django.conf import settings
import stripe
from datetime import datetime, date, timedelta
import csv
@csrf_protect
def start_payment(request):
	if request.method != 'POST':
		return redirect('rooms')

	form = PublicReservationRequestForm(request.POST)
	guest_id = request.session.get('guest_id')

	import logging
	logger = logging.getLogger(__name__)

	# Helper function to return error response
	def return_error(error_msg):
		if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
			return JsonResponse({'error': error_msg}, status=400)
		else:
			messages.error(request, error_msg)
			return redirect('rooms')

	if not form.is_valid():
		errors = '; '.join([f"{k}: {', '.join(v)}" for k, v in form.errors.items()]) if form.errors else 'Invalid input.'
		return return_error(errors)

	room = form.cleaned_data['room']
	check_in = form.cleaned_data['check_in']
	check_out = form.cleaned_data['check_out']
	id_document = form.cleaned_data['id_document']
	payment_method = request.POST.get('payment_method')
	room_id = room.id

	nights = (check_out - check_in).days

	# Calculate rate with optional points redemption
	base_rate = float(room.rate)
	discount_percentage = 0
	points_redeemed = 0
	redeem_requested = request.POST.get('redeem_points') in ['true', 'on', '1']
	guest = None
	guest_points = 0
	can_redeem_points = False
	redeem_selected = False

	if guest_id:
		try:
			guest = Guest.objects.get(id=guest_id)
			guest_points = guest.loyalty_points
			can_redeem_points = guest.can_redeem()
			if redeem_requested and can_redeem_points:
				discount_percentage = 10
				points_redeemed = 35
				redeem_selected = True
		except Guest.DoesNotExist:
			guest = None
			can_redeem_points = False

	check_in_str = check_in.isoformat()
	check_out_str = check_out.isoformat()

	# Apply discount to rate
	discounted_rate = base_rate * (1 - discount_percentage / 100)
	discounted_total = discounted_rate * nights
	base_total = base_rate * nights
	amount_cents = int(discounted_rate * 100 * nights)

	if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_PUBLIC_KEY:
		context = {
			'room_id': room_id,
			'check_in': check_in_str,
			'check_out': check_out_str,
			'id_document': id_document,
			'payment_method': payment_method,
			'room': room,
			'room_rate': discounted_rate,
			'base_rate': base_rate,
			'base_total': base_total,
			'discounted_total': discounted_total,
			'discount_percentage': discount_percentage,
			'points_redeemed': points_redeemed,
			'redeem_selected': redeem_selected,
			'guest_points': guest_points,
			'can_redeem_points': can_redeem_points,
			'nights': nights,
			'amount_eur': amount_cents / 100,
			'error_message': 'Stripe keys are not configured. Add STRIPE_PUBLIC_KEY and STRIPE_SECRET_KEY in .env.',
		}
		context.update(get_user_context(request))
		return render(request, 'payment.html', context)

	stripe.api_key = settings.STRIPE_SECRET_KEY

	metadata = {
		'room_id': str(room.id),
		'room_number': room.number,
		'check_in': check_in_str,
		'check_out': check_out_str,
		'guest_id': str(guest_id or ''),
		'id_document': id_document or '',
		'base_rate': str(base_rate),
		'discount_percentage': str(discount_percentage),
		'discounted_rate': str(discounted_rate),
		'used_points_discount': 'true' if points_redeemed else 'false',
		'points_redeemed': str(points_redeemed),
	}

	client_secret = None
	try:
		payment_intent = stripe.PaymentIntent.create(
			amount=amount_cents,
			currency='eur',
			automatic_payment_methods={'enabled': True},
			metadata=metadata,
		)
		client_secret = payment_intent.client_secret
	except stripe.error.StripeError as e:
		messages.error(request, f"Stripe error: {e.user_message or str(e)}")
	except Exception as e:
		messages.error(request, f"Unable to start payment: {str(e)}")

	context = {
		'room_id': room_id,
		'check_in': check_in_str,
		'check_out': check_out_str,
		'id_document': id_document,
		'payment_method': payment_method,
		'room': room,
		'room_rate': discounted_rate,
		'base_rate': base_rate,
		'base_total': base_total,
		'discounted_total': discounted_total,
		'discount_percentage': discount_percentage,
		'points_redeemed': points_redeemed,
		'redeem_selected': redeem_selected,
		'guest_points': guest_points,
		'can_redeem_points': can_redeem_points,
		'nights': nights,
		'amount_eur': amount_cents / 100,
		'client_secret': client_secret,
		'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
	}
	context.update(get_user_context(request))
	
	return render(request, 'payment.html', context)


def payment_success(request):
	context = get_user_context(request)
	session_id = request.GET.get('session_id')
	payment_intent_id = request.GET.get('payment_intent')
	context['stripe_session'] = None
	context['payment_intent'] = None
	if (session_id or payment_intent_id) and settings.STRIPE_SECRET_KEY:
		try:
			stripe.api_key = settings.STRIPE_SECRET_KEY
			if payment_intent_id:
				payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
				context['payment_intent'] = payment_intent
				
				# Create reservation if payment was successful
				if payment_intent.status == 'succeeded':
					metadata = payment_intent.metadata
					guest_id = metadata.get('guest_id', '')
					room_id = metadata.get('room_id')
					check_in_str = metadata.get('check_in')
					check_out_str = metadata.get('check_out')
					discounted_rate_str = metadata.get('discounted_rate', '0')
					used_points_discount = metadata.get('used_points_discount') == 'true'
					points_redeemed = int(metadata.get('points_redeemed', '0') or 0)
					
					import logging
					logger = logging.getLogger(__name__)
					logger.info(f"Payment success for payment_intent {payment_intent_id}: guest_id={guest_id}, room_id={room_id}, check_in={check_in_str}, check_out={check_out_str}")
					
					# Only create reservation if we have room, dates, AND guest_id is not empty
					if room_id and check_in_str and check_out_str and guest_id:
						try:
							from datetime import datetime
							
							guest = Guest.objects.get(id=int(guest_id))
							room = Room.objects.get(id=int(room_id))
							check_in = datetime.fromisoformat(check_in_str).date()
							check_out = datetime.fromisoformat(check_out_str).date()
							discounted_rate = float(discounted_rate_str)
							
							# Calculate total charges using discounted rate
							nights = (check_out - check_in).days
							total_charges = discounted_rate * nights
							
							# Create reservation if it doesn't already exist
							# Only check for active reservations (not checked-out or cancelled)
							existing = Reservation.objects.filter(
								guest=guest,
								room=room,
								check_in=check_in,
								check_out=check_out,
								status__in=['confirmed', 'checked-in']
							).exists()
							
							if not existing:
								reservation = Reservation.objects.create(
									guest=guest,
									room=room,
									check_in=check_in,
									check_out=check_out,
									status='confirmed',
									total_charges=total_charges,
									used_points_discount=used_points_discount,
									points_redeemed=points_redeemed
								)
								if used_points_discount and points_redeemed > 0:
									if not guest.redeem_points(points_redeemed):
										logger.warning(f"Guest {guest.id} could not redeem points after payment; balance={guest.loyalty_points}")
								logger.info(f"✓ Reservation created: ID {reservation.id} for guest {guest.id} in room {room.id}")
							else:
								logger.warning(f"Reservation already exists for guest {guest.id}, room {room.id}, dates {check_in} to {check_out}")
						except Guest.DoesNotExist as e:
							logger.error(f"Guest not found: guest_id={guest_id}")
						except Room.DoesNotExist as e:
							logger.error(f"Room not found: room_id={room_id}")
						except ValueError as e:
							logger.error(f"Value error converting IDs: {str(e)}")
						except Exception as e:
							import traceback
							logger.error(f"Error creating reservation: {str(e)}")
							logger.error(f"Traceback: {traceback.format_exc()}")
					else:
						logger.warning(f"Missing required fields for reservation: room_id={room_id}, check_in={check_in_str}, check_out={check_out_str}, guest_id={guest_id}")
			elif session_id:
				context['stripe_session'] = stripe.checkout.Session.retrieve(session_id)
		except Exception:
			context['payment_intent'] = None
			context['stripe_session'] = None
	return render(request, 'payment_success.html', context)


def payment_cancel(request):
	context = get_user_context(request)
	return render(request, 'payment_cancel.html', context)
def menu(request):
	context = get_user_context(request)
	return render(request, 'menu.html', context)

def loyalty_page(request):
	context = get_user_context(request)
	guest_points = 0
	can_redeem = False
	redeem_cost = 35
	discount_percent = 10
	earn_rate = 5
	guest_id = request.session.get('guest_id')
	if guest_id:
		try:
			guest = Guest.objects.get(id=guest_id)
			guest_points = guest.loyalty_points
			can_redeem = guest.can_redeem()
		except Guest.DoesNotExist:
			pass

	points_needed = max(redeem_cost - guest_points, 0)

	context.update({
		'points_balance': guest_points,
		'can_redeem_points': can_redeem,
		'earn_rate': earn_rate,
		'redeem_cost': redeem_cost,
		'discount_percent': discount_percent,
		'points_needed': points_needed,
	})
	return render(request, 'loyalty.html', context)
def get_user_context(request):
	guest_name = None
	staff_name = None
	staff_role = None
	guest_id_document = None
	guest_id = request.session.get('guest_id')
	staff_id = request.session.get('staff_id')
	if staff_id:
		try:
			from .models import Staff
			staff_obj = Staff.objects.get(id=staff_id)
			staff_name = staff_obj.name
			staff_role = staff_obj.role.name if staff_obj.role else None
		except Exception:
			pass
	if guest_id:
		try:
			from .models import Guest
			guest_obj = Guest.objects.get(id=guest_id)
			guest_name = f"{guest_obj.first_name} {guest_obj.last_name}"
			guest_id_document = guest_obj.id_document.split('|')[0] if guest_obj.id_document else ''
		except Exception:
			pass
	return {'guest_name': guest_name, 'staff_name': staff_name, 'staff_role': staff_role, 'guest_id_document': guest_id_document}


def resolve_actor(request):
	"""Return current actor context (admin/staff/guest) for role-based checks."""
	is_admin = request.user.is_authenticated and request.user.is_staff
	guest_obj = None
	staff_obj = None
	staff_role = None
	guest_id = request.session.get('guest_id')
	staff_id = request.session.get('staff_id')
	if guest_id:
		try:
			guest_obj = Guest.objects.get(id=guest_id)
		except Guest.DoesNotExist:
			guest_obj = None
	if staff_id:
		try:
			staff_obj = Staff.objects.select_related('role').get(id=staff_id)
			staff_role = staff_obj.role.name if staff_obj.role else None
		except Staff.DoesNotExist:
			staff_obj = None
	return {
		'is_admin': is_admin,
		'guest': guest_obj,
		'staff': staff_obj,
		'staff_role': staff_role,
	}


def require_staff_role(*allowed_roles):
	"""Decorator: allow access if the current Django user is staff OR the session staff has one of allowed_roles.
	If not allowed, render access denied page with 403 status.
	"""
	def decorator(view_func):
		@wraps(view_func)
		def _wrapped(request, *args, **kwargs):
			# Allow Django admin/staff users
			if request.user.is_authenticated and request.user.is_staff:
				return view_func(request, *args, **kwargs)

			# Check custom staff session
			staff_id = request.session.get('staff_id')
			if staff_id:
				try:
					staff_obj = Staff.objects.get(id=staff_id)
					role_name = staff_obj.role.name if staff_obj.role else None
					if role_name and role_name in allowed_roles:
						return view_func(request, *args, **kwargs)
				except Exception:
					pass

			# Not allowed
			context = get_user_context(request)
			context['title'] = 'Access Prohibited'
			context['message'] = 'You do not have permission to view this page.'
			return render(request, 'core/access_denied.html', context, status=403)
		return _wrapped
	return decorator

def require_guest_or_staff(*allowed_staff_roles):
	"""Decorator: allow access if the current user is a guest OR staff with one of allowed_roles.
	If not allowed, render access denied page with 403 status.
	"""
	def decorator(view_func):
		@wraps(view_func)
		def _wrapped(request, *args, **kwargs):
			# Allow Django admin/staff users
			if request.user.is_authenticated and request.user.is_staff:
				return view_func(request, *args, **kwargs)

			# Check custom guest session
			guest_id = request.session.get('guest_id')
			if guest_id:
				# Let the view handle detailed checks to avoid redirect loops
				return view_func(request, *args, **kwargs)

			# Check custom staff session
			staff_id = request.session.get('staff_id')
			if staff_id:
				try:
					from .models import Staff
					staff_obj = Staff.objects.get(id=staff_id)
					role_name = staff_obj.role.name if staff_obj.role else None
					if role_name and role_name in allowed_staff_roles:
						return view_func(request, *args, **kwargs)
				except Exception:
					pass


			# No session — send to guest login for clarity instead of 403
			messages.error(request, 'Please log in to view this page.')
			return redirect('guest_login')
		return _wrapped
	return decorator
from .models import Staff
from django.views.decorators.csrf import csrf_protect
from django.contrib.admin.views.decorators import staff_member_required
@csrf_protect
@staff_member_required
def staff_register(request):
	if request.method == 'POST':
		form = StaffRegistrationForm(request.POST)
		if form.is_valid():
			form.save()
			return render(request, 'staff_register.html', {'success': True, 'form': StaffRegistrationForm()})
	else:
		form = StaffRegistrationForm()
	return render(request, 'staff_register.html', {'form': form})
from django.views.decorators.csrf import csrf_protect
@csrf_protect
def housekeeper_login(request):
	form = StaffLoginForm(request.POST or None)
	if request.method == 'POST':
		if not check_rate_limit(request, f"staff_login:{request.META.get('REMOTE_ADDR')}"):
			messages.error(request, 'Too many login attempts. Please wait and try again.')
			return render(request, 'housekeeper_login.html', {'form': form})
		if form.is_valid():
			email = form.cleaned_data['email']
			password = form.cleaned_data['password']
			import hashlib
			password_hash = hashlib.sha256(password.encode()).hexdigest()
			from .models import Staff
			try:
				staff = Staff.objects.select_related('role').get(email=email)
				if staff.password_hash == password_hash:
					request.session['staff_id'] = staff.id
					role_name = staff.role.name if staff.role else None
					if role_name == 'Maintenance':
						return redirect('maintenance_list')
					elif role_name in ['Housekeeper', 'Reception']:
						return redirect('housekeeping_list')
					else:
						return redirect('home')
				messages.error(request, 'Invalid credentials.')
			except Staff.DoesNotExist:
				messages.error(request, 'Invalid credentials.')
	return render(request, 'housekeeper_login.html', {'form': form})
from django.views.decorators.csrf import csrf_protect
@csrf_protect
def guest_register(request):
	guest_first_name = None
	guest_id = request.session.get('guest_id')
	if guest_id:
		try:
			guest_obj = Guest.objects.get(id=guest_id)
			guest_first_name = guest_obj.first_name
		except Guest.DoesNotExist:
			pass
	if request.method == 'POST':
		form = GuestRegistrationForm(request.POST)
		if form.is_valid():
			import hashlib
			password_hash = hashlib.sha256(form.cleaned_data['password'].encode()).hexdigest()
			guest = Guest.objects.create(
				first_name=form.cleaned_data['first_name'].strip(),
				last_name=form.cleaned_data['last_name'].strip(),
				email=form.cleaned_data['email'].strip(),
				phone=form.cleaned_data['phone'].strip(),
				id_document=form.cleaned_data['id_document'].strip() + '|' + password_hash,
			)
			request.session['guest_id'] = guest.id
			return redirect('home')
	else:
		form = GuestRegistrationForm()
	return render(request, 'guest_register.html', {'guest_first_name': guest_first_name, 'form': form})

from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect

def home(request):
	context = get_user_context(request)
	return render(request, 'home.html', context)


def newsletter(request):
	"""Render the dedicated newsletter signup page (Mailchimp embed)."""
	context = get_user_context(request)
	return render(request, 'newsletter.html', context)

from .models import Guest

from .models import Reservation, Room
from .models import Housekeeping, Maintenance
from .models import ServiceRequest

from django.shortcuts import redirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from .models import Guest
import hashlib

@staff_member_required
def guests(request):
	all_guests = Guest.objects.all()
	context = get_user_context(request)
	context['guests'] = all_guests
	return render(request, 'guests.html', context)

def reservations(request):
	from django.contrib import messages
	all_reservations = Reservation.objects.select_related('guest', 'room').all()
	context = get_user_context(request)
	context['reservations'] = all_reservations
	booking_form = None

	if request.method == 'POST':
		booking_form = PublicReservationRequestForm(request.POST)
		if not request.session.get('guest_id'):
			messages.error(request, 'You must be logged in as a guest to book a room.')
			return redirect('rooms')
		if booking_form.is_valid():
			try:
				guest = Guest.objects.get(id=request.session.get('guest_id'))
			except Guest.DoesNotExist:
				messages.error(request, 'Guest not found. Please log in again.')
				return redirect('guest_login')
			room = booking_form.cleaned_data['room']
			check_in = booking_form.cleaned_data['check_in']
			check_out = booking_form.cleaned_data['check_out']
			id_document = booking_form.cleaned_data['id_document']
			# Update guest's ID document base while preserving stored hash
			if id_document and guest.id_document.split('|')[0] != id_document:
				parts = guest.id_document.split('|')
				password_hash = parts[1] if len(parts) > 1 else ''
				guest.id_document = id_document + ('|' + password_hash if password_hash else '')
				guest.save()
			Reservation.objects.create(
				guest=guest,
				room=room,
				check_in=check_in,
				check_out=check_out,
				status='confirmed'
			)
			messages.success(request, 'Booking confirmed!')
			return redirect('reservations')
		else:
			messages.error(request, 'Please correct the errors in your booking details.')

	if booking_form is None:
		booking_form = PublicReservationRequestForm()
	context['booking_form'] = booking_form
	return render(request, 'reservations.html', context)

def rooms(request):
	rooms_queryset = Room.objects.all()
	rooms_list = list(rooms_queryset)
	# Room availability is now based on date ranges, not a boolean flag
	# Get booked dates for each room to pass to template
	for room in rooms_list:
		room.booked_dates = room.get_booked_dates()
	rates = [room.rate for room in rooms_list if room.rate is not None]
	average_rate = (sum(rates) / len(rates)) if rates else None
	
	# Get total number of bookings across all rooms
	total_bookings = Reservation.objects.count()
	
	context = get_user_context(request)
	context['rooms'] = rooms_list
	context['can_manage_rooms'] = request.user.is_authenticated and request.user.is_staff
	
	# Get guest points if logged in
	guest_id = request.session.get('guest_id')
	guest_points = 0
	can_redeem_points = False
	if guest_id:
		try:
			guest = Guest.objects.get(id=guest_id)
			guest_points = guest.loyalty_points
			can_redeem_points = guest.can_redeem()
		except Guest.DoesNotExist:
			pass

	context['guest_points'] = guest_points
	context['can_redeem_points'] = can_redeem_points
	
	# Calculate stats - all rooms are "available" since booking is now date-based
	context['room_stats'] = {
		'total': len(rooms_list),
		'available': len(rooms_list),
		'booked': total_bookings,
		'average_rate': average_rate,
	}
	# Provide guest list for reception to allow booking on behalf of guests
	if context.get('staff_role') == 'Reception' and not (request.user.is_authenticated and request.user.is_staff):
		try:
			context['guests'] = Guest.objects.all()
		except Exception:
			context['guests'] = []
	return render(request, 'rooms.html', context)


@staff_member_required
def room_edit(request, pk):
	"""Update an existing room"""
	try:
		room = Room.objects.get(pk=pk)
	except Room.DoesNotExist:
		messages.error(request, 'Room not found.')
		return redirect('rooms')

	if request.method == 'POST':
		form = RoomForm(request.POST, request.FILES, instance=room)
		if form.is_valid():
			form.save()
			messages.success(request, f'Room {room.number} updated successfully!')
			return redirect('rooms')
	else:
		form = RoomForm(instance=room)

	context = get_user_context(request)
	context['form'] = form
	context['title'] = f'Edit Room {room.number}'
	return render(request, 'core/form.html', context)


@staff_member_required
def room_delete(request, pk):
	"""Delete a room"""
	try:
		room = Room.objects.get(pk=pk)
	except Room.DoesNotExist:
		messages.error(request, 'Room not found.')
		return redirect('rooms')

	if request.method == 'POST':
		room_number = room.number
		room.delete()
		messages.success(request, f'Room {room_number} deleted successfully.')
		return redirect('rooms')

	context = get_user_context(request)
	context['object'] = room
	return render(request, 'core/confirm_delete.html', context)

@require_guest_or_staff('Housekeeper', 'Reception')
def housekeeping(request):
	tasks = Housekeeping.objects.select_related('room', 'staff').all()
	context = get_user_context(request)
	context['housekeeping'] = tasks
	return render(request, 'housekeeping.html', context)

@require_guest_or_staff('Maintenance', 'Reception')
def maintenance(request):
	"""Backwards-compatible entry point; redirect to the new maintenance board."""
	return redirect('maintenance_list')

@require_guest_or_staff('Reception')
def services(request):
	actor = resolve_actor(request)
	context = get_user_context(request)

	menu_sections = [
		{
			'title': 'Starters',
			'items': [
				{'name': 'Seafood Chowder', 'price': Decimal('8.00'), 'description': 'Creamy chowder with local catch and soda bread.'},
				{'name': 'Goat Cheese Salad', 'price': Decimal('7.00'), 'description': 'Ardsallagh goat cheese, roasted beetroot, candied walnuts.'},
				{'name': 'Smoked Salmon on Brown Bread', 'price': Decimal('9.00'), 'description': 'Connemara smoked salmon, pickled cucumber, dill mayo.'},
			],
		},
		{
			'title': 'Main Courses',
			'items': [
				{'name': 'Roast Irish Lamb', 'price': Decimal('18.00'), 'description': 'Slow-roasted lamb shoulder, root vegetables, red wine jus.'},
				{'name': 'Pan-Seared Atlantic Salmon', 'price': Decimal('17.00'), 'description': 'Lemon beurre blanc, samphire, crushed baby potatoes.'},
				{'name': 'Vegetarian Shepherds Pie', 'price': Decimal('15.00'), 'description': 'Lentils, roasted vegetables, herb mash, vegan gravy.'},
			],
		},
		{
			'title': 'Desserts',
			'items': [
				{'name': 'Baileys Cheesecake', 'price': Decimal('6.00'), 'description': 'Silky cheesecake, chocolate crumb, Baileys cream.'},
				{'name': 'Warm Apple Crumble', 'price': Decimal('6.00'), 'description': 'Bramley apples, oat crumble, vanilla custard.'},
				{'name': 'Chocolate Fondant', 'price': Decimal('7.00'), 'description': 'Molten centre, hazelnut praline, whipped cream.'},
			],
		},
		{
			'title': 'Beverages',
			'items': [
				{'name': 'Irish Coffee', 'price': Decimal('5.00'), 'description': 'Jameson, hot coffee, brown sugar, fresh cream.'},
				{'name': 'Selection of Teas & Coffees', 'price': Decimal('3.00'), 'description': 'Barista coffee or artisan loose-leaf teas.'},
				{'name': 'Craft Beer', 'price': Decimal('5.00'), 'description': 'Rotating local craft selection.'},
			],
		},
	]

	# Build a quick lookup for validation
	menu_lookup = {item['name']: item['price'] for section in menu_sections for item in section['items']}

	active_reservation = None
	if actor['guest']:
		active_reservation = (
			Reservation.objects
			.filter(guest=actor['guest'], status__in=['confirmed', 'checked-in'])
			.select_related('room')
			.order_by('-check_in')
			.first()
		)

	order_form = ServiceOrderForm(request.POST or None, allowed_items=list(menu_lookup.keys())) if actor['guest'] else None

	if request.method == 'POST':
		if not actor['guest']:
			messages.error(request, 'Only guests can place in-room orders.')
			return redirect('services')
		if not active_reservation:
			messages.error(request, 'You need an active reservation to send items to your room.')
			return redirect('services')
		if order_form and order_form.is_valid():
			item_name = order_form.cleaned_data['item_name']
			try:
				charge = Decimal(menu_lookup[item_name])
			except (InvalidOperation, ValueError):
				messages.error(request, 'There was a problem with the selected item price. Please try again.')
				return redirect('services')
			ServiceRequest.objects.create(
				guest=actor['guest'],
				reservation=active_reservation,
				request_type=item_name,
				charge=charge,
			)
			messages.success(request, f"{item_name} was sent to room {active_reservation.room.number}.")
			return redirect('services')
		messages.error(request, 'Please choose a valid menu item.')

	if actor['guest'] and order_form is None:
		order_form = ServiceOrderForm(allowed_items=list(menu_lookup.keys()))

	if actor['guest']:
		service_requests = (
			ServiceRequest.objects
			.filter(guest=actor['guest'])
			.select_related('reservation__room')
			.order_by('-timestamp')
		)
	else:
		service_requests = ServiceRequest.objects.select_related('guest', 'reservation__room').order_by('-timestamp')

	context.update({
		'service_requests': service_requests,
		'menu_sections': menu_sections,
		'active_reservation': active_reservation,
		'is_guest_view': bool(actor['guest']),
		'order_form': order_form,
	})
	return render(request, 'services.html', context)

@csrf_protect
def guest_login(request):
	form = GuestLoginForm(request.POST or None)
	if request.method == 'POST':
		if not check_rate_limit(request, f"guest_login:{request.META.get('REMOTE_ADDR')}"):
			messages.error(request, 'Too many login attempts. Please wait and try again.')
			return render(request, 'guest_login.html', {'form': form})
		if form.is_valid():
			email = form.cleaned_data['email']
			password = form.cleaned_data['password']
			password_hash = hashlib.sha256(password.encode()).hexdigest()
			try:
				guest = Guest.objects.get(email=email)
				stored = guest.id_document.split('|')
				stored_hash = stored[1] if len(stored) > 1 else ''
				if password_hash == stored_hash:
					request.session['guest_id'] = guest.id
					return redirect('home')
				messages.error(request, 'Invalid credentials.')
			except Guest.DoesNotExist:
				messages.error(request, 'Invalid credentials.')
	return render(request, 'guest_login.html', {'form': form})


# ==================== GUEST MANAGEMENT ====================

@require_staff_role('Reception')
def guest_list(request):
	"""List all guests"""
	try:
		guests_list = Guest.objects.all()
		context = get_user_context(request)
		context['guests'] = guests_list
		redeem_ready = guests_list.filter(loyalty_points__gte=35).count()
		preferences_count = guests_list.exclude(preferences__isnull=True).exclude(preferences__exact='').count()
		context['guest_stats'] = {
			'total': guests_list.count(),
			'redeem_ready': redeem_ready,
			'with_preferences': preferences_count,
		}
		# Reception users get a tailored guest directory with quick booking actions
		if context.get('staff_role') == 'Reception' and not (request.user.is_authenticated and request.user.is_staff):
			context['guests'] = guests_list
			return render(request, 'core/guest_list_reception.html', context)
		return render(request, 'core/guest_list.html', context)
	except Exception as e:
		messages.error(request, 'An error occurred while retrieving guests.')
		return redirect('admin_dashboard')


@require_staff_role('Reception')
def guest_create(request):
	"""Create a new guest"""
	if request.method == 'POST':
		form = GuestForm(request.POST)
		if form.is_valid():
			try:
				form.save()
				messages.success(request, 'Guest created successfully! You can now create reservations for this guest.')
				return redirect('guest_list')
			except Exception as e:
				messages.error(request, 'An error occurred while saving the guest. Please try again.')
		else:
			# Form has validation errors - they'll be displayed in template
			pass
	else:
		form = GuestForm()
	context = get_user_context(request)
	context['form'] = form
	context['title'] = 'Create Guest'
	return render(request, 'core/form.html', context)


@require_staff_role('Reception')
def guest_detail(request, pk):
	"""View guest details"""
	try:
		guest = Guest.objects.get(pk=pk)
		context = get_user_context(request)
		context['object'] = guest
		context['title'] = f"{guest.first_name} {guest.last_name}"
		loyalty_points = guest.loyalty_points or 0
		context['points_needed'] = max(35 - loyalty_points, 0)
		return render(request, 'core/guest_detail.html', context)
	except Guest.DoesNotExist:
		messages.error(request, 'Guest not found.')
		return redirect('guest_list')


@require_staff_role('Reception')
def guest_update(request, pk):
	"""Update guest information"""
	try:
		guest = Guest.objects.get(pk=pk)
	except Guest.DoesNotExist:
		messages.error(request, 'Guest not found.')
		return redirect('guest_list')
	
	if request.method == 'POST':
		form = GuestForm(request.POST, instance=guest)
		if form.is_valid():
			try:
				# Handle password update if provided
				password = form.cleaned_data.get('password')
				if password:
					import hashlib
					password_hash = hashlib.sha256(password.encode()).hexdigest()
					# Extract id_document number and append new password hash
					id_doc_parts = guest.id_document.split('|') if guest.id_document else ['']
					guest.id_document = id_doc_parts[0] + '|' + password_hash
				
				# Save the form (excluding password field since it's not in the model)
				guest = form.save(commit=False)
				guest.save()
				messages.success(request, f'{guest.first_name} {guest.last_name} has been updated successfully!')
				return redirect('guest_detail', pk=pk)
			except Exception as e:
				messages.error(request, 'An error occurred while saving the guest. Please try again.')
		else:
			# Form has validation errors - they'll be displayed in template
			pass
	else:
		form = GuestForm(instance=guest)
	context = get_user_context(request)
	context['form'] = form
	context['title'] = f"Update {guest.first_name} {guest.last_name}"
	return render(request, 'core/form.html', context)


@require_staff_role('Reception')
def guest_delete(request, pk):
	"""Delete a guest"""
	try:
		guest = Guest.objects.get(pk=pk)
	except Guest.DoesNotExist:
		messages.error(request, 'Guest not found.')
		return redirect('guest_list')
	
	if request.method == 'POST':
		guest_name = f"{guest.first_name} {guest.last_name}"
		try:
			guest.delete()
			messages.success(request, f'Guest "{guest_name}" has been deleted successfully.')
			return redirect('guest_list')
		except Exception as e:
			messages.error(request, f'Could not delete guest. They may have existing reservations. Please delete those first.')
	
	context = get_user_context(request)
	context['object'] = guest
	return render(request, 'core/confirm_delete.html', context)


# ==================== STAFF MANAGEMENT ====================

@staff_member_required
def staff_list(request):
	"""List all staff members"""
	try:
		staffs = Staff.objects.all()
		context = get_user_context(request)
		context['staffs'] = staffs
		return render(request, 'core/staff_list.html', context)
	except Exception:
		messages.error(request, 'An error occurred while retrieving staff members.')
		return redirect('admin_dashboard')


@staff_member_required
def staff_create(request):
	"""Create a new staff member"""
	if request.method == 'POST':
		form = StaffForm(request.POST)
		if form.is_valid():
			try:
				form.save()
				messages.success(request, 'Staff member created successfully!')
				return redirect('staff_list')
			except Exception:
				messages.error(request, 'An error occurred while saving the staff member. Please try again.')
		else:
			pass
	else:
		form = StaffForm()
	context = get_user_context(request)
	context['form'] = form
	context['title'] = 'Create Staff'
	return render(request, 'core/form.html', context)


@staff_member_required
def staff_detail(request, pk):
	"""View staff details"""
	try:
		staff = Staff.objects.get(pk=pk)
		context = get_user_context(request)
		context['object'] = staff
		context['title'] = staff.name
		return render(request, 'core/staff_detail.html', context)
	except Staff.DoesNotExist:
		messages.error(request, 'Staff member not found.')
		return redirect('staff_list')


@staff_member_required
def staff_update(request, pk):
	"""Update staff information"""
	try:
		staff = Staff.objects.get(pk=pk)
	except Staff.DoesNotExist:
		messages.error(request, 'Staff member not found.')
		return redirect('staff_list')

	if request.method == 'POST':
		form = StaffForm(request.POST, instance=staff)
		if form.is_valid():
			try:
				form.save()
				messages.success(request, f'{staff.name} has been updated successfully!')
				return redirect('staff_detail', pk=pk)
			except Exception:
				messages.error(request, 'An error occurred while saving the staff member. Please try again.')
		else:
			pass
	else:
		form = StaffForm(instance=staff)
	context = get_user_context(request)
	context['form'] = form
	context['title'] = f"Update {staff.name}"
	return render(request, 'core/form.html', context)


@staff_member_required
def staff_delete(request, pk):
	"""Delete a staff member"""
	try:
		staff = Staff.objects.get(pk=pk)
	except Staff.DoesNotExist:
		messages.error(request, 'Staff member not found.')
		return redirect('staff_list')

	if request.method == 'POST':
		staff_name = staff.name
		try:
			staff.delete()
			messages.success(request, f'Staff "{staff_name}" has been deleted successfully.')
			return redirect('staff_list')
		except Exception:
			messages.error(request, 'Could not delete staff member. They may have related records. Please remove those first.')

	context = get_user_context(request)
	context['object'] = staff
	return render(request, 'core/confirm_delete.html', context)


# ==================== RESERVATION MANAGEMENT ====================

@require_staff_role('Reception')
def reservation_list(request):
	"""List all reservations"""
	try:
		reservations_list = Reservation.objects.select_related('guest', 'room').all()
		context = get_user_context(request)
		context['reservations'] = reservations_list
		return render(request, 'core/reservation_list.html', context)
	except Exception as e:
		messages.error(request, 'An error occurred while retrieving reservations.')
		return redirect('admin_dashboard')


@require_staff_role('Reception')
def reservation_create(request):
	"""Create a new reservation"""
	# Support pre-filling guest and/or room via GET params for reception flow
	if request.method == 'POST':
		form = ReservationForm(request.POST)
		if form.is_valid():
			try:
				from decimal import Decimal
				reservation = form.save(commit=False)
				redeem_requested = request.POST.get('redeem_points') in ['true', 'on', '1']
				apply_discount = reservation.used_points_discount
				if redeem_requested and reservation.guest and reservation.guest.can_redeem():
					apply_discount = True
					reservation.used_points_discount = True
					reservation.points_redeemed = 35

				if reservation.room and reservation.room.rate and reservation.check_in and reservation.check_out:
					nights = (reservation.check_out - reservation.check_in).days
					if nights > 0:
						total = reservation.room.rate * nights
						if apply_discount:
							discount_factor = Decimal('0.90')
							total = total * discount_factor
						reservation.total_charges = total
				reservation.save()
				if apply_discount and reservation.points_redeemed:
					if reservation.guest:
						reservation.guest.redeem_points(reservation.points_redeemed)
				# Note: Room availability is now determined by booked dates, not a boolean flag
				messages.success(request, f'Reservation created successfully! Room {reservation.room.number} is booked for {reservation.check_in} to {reservation.check_out}.')
				return redirect('reservation_list')
			except Exception as e:
				messages.error(request, f'An error occurred while saving the reservation: {str(e)}')
		else:
			# Form has validation errors - they'll be displayed in template
			pass
	else:
		# Prefill from GET when provided
		initial = {}
		guest_id = request.GET.get('guest_id')
		room_id = request.GET.get('room_id')
		if guest_id:
			initial['guest'] = guest_id
		if room_id:
			initial['room'] = room_id
		form = ReservationForm(initial=initial)
	context = get_user_context(request)
	context['form'] = form
	context['title'] = 'Create Reservation'
	return render(request, 'core/form.html', context)


@require_staff_role('Reception')
def reservation_detail(request, pk):
	"""View reservation details"""
	try:
		reservation = Reservation.objects.select_related('guest', 'room').get(pk=pk)
		context = get_user_context(request)
		context['object'] = reservation
		context['title'] = f"Reservation #{reservation.id}"
		return render(request, 'core/reservation_detail.html', context)
	except Reservation.DoesNotExist:
		messages.error(request, 'Reservation not found.')
		return redirect('reservation_list')


@require_staff_role('Reception')
def reservation_update(request, pk):
	"""Update reservation"""
	try:
		reservation = Reservation.objects.get(pk=pk)
	except Reservation.DoesNotExist:
		messages.error(request, 'Reservation not found.')
		return redirect('reservation_list')
	
	if request.method == 'POST':
		form = ReservationForm(request.POST, instance=reservation)
		if form.is_valid():
			try:
				from decimal import Decimal
				reservation = form.save(commit=False)
				redeem_requested = request.POST.get('redeem_points') in ['true', 'on', '1']
				apply_discount = reservation.used_points_discount
				if redeem_requested and not reservation.used_points_discount and reservation.guest and reservation.guest.can_redeem():
					apply_discount = True
					reservation.used_points_discount = True
					reservation.points_redeemed = 35

				if reservation.room and reservation.room.rate and reservation.check_in and reservation.check_out:
					nights = (reservation.check_out - reservation.check_in).days
					if nights > 0:
						total = reservation.room.rate * nights
						if apply_discount:
							discount_factor = Decimal('0.90')
							total = total * discount_factor
						reservation.total_charges = total
				reservation.save()
				if redeem_requested and reservation.used_points_discount and reservation.points_redeemed:
					if reservation.guest:
						reservation.guest.redeem_points(reservation.points_redeemed)
				messages.success(request, f'Reservation #{reservation.id} has been updated successfully!')
				return redirect('reservation_detail', pk=pk)
			except Exception as e:
				messages.error(request, 'An error occurred while updating the reservation. Please try again.')
		else:
			# Form has validation errors - they'll be displayed in template
			pass
	else:
		form = ReservationForm(instance=reservation)
	context = get_user_context(request)
	context['form'] = form
	context['title'] = f"Update Reservation #{reservation.id}"
	context['current_reservation_id'] = reservation.id
	context['current_room_id'] = reservation.room.id
	return render(request, 'core/form.html', context)


@require_staff_role('Reception')
def reservation_delete(request, pk):
	"""Delete a reservation"""
	try:
		reservation = Reservation.objects.select_related('room').get(pk=pk)
	except Reservation.DoesNotExist:
		messages.error(request, 'Reservation not found.')
		return redirect('reservation_list')
	
	if request.method == 'POST':
		room = reservation.room
		reservation_id = reservation.id
		try:
			reservation.delete()
			messages.success(request, f'Reservation #{reservation_id} has been deleted. Room is now available for other bookings.')
			return redirect('reservation_list')
		except Exception as e:
			messages.error(request, 'An error occurred while deleting the reservation. Please try again.')
	
	context = get_user_context(request)
	context['object'] = reservation
	return render(request, 'core/confirm_delete.html', context)


# ==================== HOUSEKEEPING MANAGEMENT ====================

@require_guest_or_staff('Housekeeper', 'Reception')
def housekeeping_list(request):
	"""List all housekeeping tasks"""
	tasks = Housekeeping.objects.select_related('room', 'staff').all()
	context = get_user_context(request)
	context['housekeeping'] = tasks
	return render(request, 'core/housekeeping_list.html', context)


@require_guest_or_staff('Housekeeper', 'Reception')
def housekeeping_create(request):
	"""Create a new housekeeping task"""
	if request.method == 'POST':
		form = HousekeepingForm(request.POST)
		if form.is_valid():
			form.save()
			messages.success(request, 'Housekeeping task created successfully!')
			return redirect('housekeeping_list')
	else:
		form = HousekeepingForm()
	context = get_user_context(request)
	context['form'] = form
	context['title'] = 'Create Housekeeping Task'
	return render(request, 'core/form.html', context)


@require_guest_or_staff('Housekeeper', 'Reception')
def housekeeping_detail(request, pk):
	"""View housekeeping task details"""
	task = Housekeeping.objects.select_related('room', 'staff').get(pk=pk)
	context = get_user_context(request)
	context['object'] = task
	context['title'] = f"Housekeeping Task #{task.id}"
	return render(request, 'core/housekeeping_detail.html', context)


@require_staff_role('Housekeeper', 'Reception')
def housekeeping_update(request, pk):
	"""Update housekeeping task"""
	task = Housekeeping.objects.get(pk=pk)
	if request.method == 'POST':
		form = HousekeepingForm(request.POST, instance=task)
		if form.is_valid():
			form.save()
			messages.success(request, 'Housekeeping task updated successfully!')
			return redirect('housekeeping_detail', pk=pk)
	else:
		form = HousekeepingForm(instance=task)
	context = get_user_context(request)
	context['form'] = form
	context['title'] = f"Update Housekeeping Task #{task.id}"
	return render(request, 'core/form.html', context)


@require_staff_role('Housekeeper', 'Reception')
def housekeeping_delete(request, pk):
	"""Delete a housekeeping task"""
	task = Housekeeping.objects.get(pk=pk)
	if request.method == 'POST':
		task.delete()
		messages.success(request, 'Housekeeping task deleted successfully!')
		return redirect('housekeeping_list')
	context = get_user_context(request)
	context['object'] = task
	return render(request, 'core/confirm_delete.html', context)


# ==================== MAINTENANCE MANAGEMENT ====================

@require_guest_or_staff('Maintenance', 'Reception')
def maintenance_list(request):
	"""Role-aware maintenance board."""
	actor = resolve_actor(request)
	queryset = MaintenanceRequest.objects.select_related('room', 'assigned_to', 'guest', 'reservation')

	if actor['is_admin'] or actor['staff_role'] == 'Reception':
		requests_list = queryset
	elif actor['staff_role'] == 'Maintenance' and actor['staff']:
		requests_list = queryset.filter(assigned_to=actor['staff'])
	elif actor['guest']:
		requests_list = queryset.filter(guest=actor['guest']).exclude(status='cancelled')
	else:
		messages.error(request, 'Please log in as a guest to view maintenance requests.')
		return redirect('guest_login')

	context = get_user_context(request)
	context.update({
		'maintenance_requests': requests_list,
		'is_admin': actor['is_admin'],
		'is_reception': actor['staff_role'] == 'Reception',
		'is_maintenance_staff': actor['staff_role'] == 'Maintenance',
		'is_guest_view': bool(actor['guest'] and not actor['staff'] and not actor['is_admin']),
		'staff_id': actor['staff'].id if actor['staff'] else None,
		'board_stats': {
			'total': requests_list.count(),
			'open': requests_list.exclude(status__in=['completed', 'cancelled']).count(),
			'assigned_to_me': requests_list.filter(assigned_to=actor['staff']).count() if actor['staff'] else 0,
		},
	})
	return render(request, 'core/maintenance_list.html', context)


@require_guest_or_staff('Maintenance', 'Reception')
def maintenance_create(request):
	"""Create a new maintenance request (guests and admins)."""
	actor = resolve_actor(request)
	context = get_user_context(request)

	if actor['guest']:
		active_reservation = Reservation.objects.filter(guest=actor['guest'], status='checked-in').select_related('room').order_by('-check_in').first()
		if not active_reservation:
			messages.error(request, 'You must be checked in to submit a maintenance request.')
			return redirect('maintenance_list')

		form = MaintenanceRequestGuestForm(request.POST or None, reservation=active_reservation)
		if request.method == 'POST' and form.is_valid():
			from django.utils import timezone
			today = timezone.localdate()
			if today < active_reservation.check_in:
				req_date = active_reservation.check_in
			elif today > active_reservation.check_out:
				req_date = active_reservation.check_out
			else:
				req_date = today
			MaintenanceRequest.objects.create(
				guest=actor['guest'],
				reservation=active_reservation,
				room=active_reservation.room,
				requested_by_name=f"{actor['guest'].first_name} {actor['guest'].last_name}",
				request_date=req_date,
				type=form.cleaned_data['type'],
				comment=form.cleaned_data.get('comment', ''),
				status='requested',
			)
			messages.success(request, 'Maintenance request submitted. We will update you soon.')
			return redirect('maintenance_list')

		context.update({
			'form': form,
			'title': 'Request Maintenance',
			'room': active_reservation.room,
			'reservation_window': (active_reservation.check_in, active_reservation.check_out),
		})
		return render(request, 'core/form.html', context)

	if actor['is_admin']:
		form = MaintenanceRequestAdminForm(request.POST or None)
		if request.method == 'POST' and form.is_valid():
			request_obj = form.save(commit=False)
			if request_obj.assigned_to and request_obj.status == 'requested':
				request_obj.status = 'assigned'
			request_obj.save()
			messages.success(request, 'Maintenance request created.')
			return redirect('maintenance_list')
		context.update({'form': form, 'title': 'Create Maintenance Request'})
		return render(request, 'core/form.html', context)

	messages.error(request, 'You do not have permission to create maintenance requests.')
	return redirect('maintenance_list')


@require_guest_or_staff('Maintenance', 'Reception')
def maintenance_detail(request, pk):
	"""View maintenance request details with role-aware visibility."""
	actor = resolve_actor(request)
	try:
		maintenance_req = MaintenanceRequest.objects.select_related('room', 'assigned_to', 'guest', 'reservation').get(pk=pk)
	except MaintenanceRequest.DoesNotExist:
		messages.error(request, 'Maintenance request not found.')
		return redirect('maintenance_list')

	allowed = False
	if actor['is_admin'] or actor['staff_role'] == 'Reception':
		allowed = True
	elif actor['staff_role'] == 'Maintenance' and actor['staff']:
		allowed = maintenance_req.assigned_to_id == actor['staff'].id
	elif actor['guest']:
		allowed = maintenance_req.guest_id == actor['guest'].id

	if not allowed:
		context = get_user_context(request)
		context['title'] = 'Access Prohibited'
		context['message'] = 'You do not have permission to view this request.'
		return render(request, 'core/access_denied.html', context, status=403)

	if actor['guest'] and maintenance_req.status == 'cancelled':
		messages.error(request, 'This request is no longer active.')
		return redirect('maintenance_list')

	can_comment = actor['is_admin'] or (actor['staff_role'] == 'Maintenance' and actor['staff'] and maintenance_req.assigned_to_id == actor['staff'].id)
	comment_form = MaintenanceRequestCommentForm(request.POST or None) if request.method == 'POST' else MaintenanceRequestCommentForm()

	if request.method == 'POST' and can_comment and comment_form.is_valid():
		comment = comment_form.save(commit=False)
		comment.request = maintenance_req
		if actor['staff']:
			comment.author = actor['staff']
			comment.author_name = actor['staff'].name
		elif actor['is_admin']:
			comment.author_name = request.user.get_full_name() or request.user.get_username()
		comment.save()
		messages.success(request, 'Comment added.')
		return redirect('maintenance_detail', pk=pk)

	context = get_user_context(request)
	context.update({
		'object': maintenance_req,
		'title': f"Maintenance Request #{maintenance_req.id}",
		'can_comment': can_comment,
		'comment_form': comment_form,
		'comments': maintenance_req.comments.select_related('author') if not (actor['guest'] and not actor['is_admin'] and not actor['staff']) else [],
		'is_admin': actor['is_admin'],
		'is_reception': actor['staff_role'] == 'Reception',
		'is_maintenance_staff': actor['staff_role'] == 'Maintenance',
		'is_guest_view': bool(actor['guest'] and not actor['staff'] and not actor['is_admin']),
		'staff_id': actor['staff'].id if actor['staff'] else None,
	})
	return render(request, 'core/maintenance_detail.html', context)


@require_guest_or_staff('Maintenance', 'Reception')
def maintenance_comments_api(request, pk):
	"""Return or create maintenance comments for real-time updates."""
	actor = resolve_actor(request)
	try:
		maintenance_req = MaintenanceRequest.objects.select_related('room', 'assigned_to', 'guest').get(pk=pk)
	except MaintenanceRequest.DoesNotExist:
		return JsonResponse({'error': 'Not found'}, status=404)

	allowed = False
	if actor['is_admin'] or actor['staff_role'] == 'Reception':
		allowed = True
	elif actor['staff_role'] == 'Maintenance' and actor['staff']:
		allowed = maintenance_req.assigned_to_id == actor['staff'].id
	elif actor['guest']:
		allowed = maintenance_req.guest_id == actor['guest'].id

	if not allowed:
		return JsonResponse({'error': 'Forbidden'}, status=403)

	can_comment = actor['is_admin'] or (
		actor['staff_role'] == 'Maintenance'
		and actor['staff']
		and maintenance_req.assigned_to_id == actor['staff'].id
	)
	hide_comments_for_guest = actor['guest'] and not actor['is_admin'] and not actor['staff']

	def serialize_comment(comment):
		return {
			'id': comment.id,
			'author': comment.author.name if comment.author else (comment.author_name or 'Unknown'),
			'note': comment.note,
			'created_at': comment.created_at.isoformat(),
			'created_at_display': comment.created_at.strftime('%b %d, %Y %H:%M'),
		}

	if request.method == 'POST':
		if not can_comment:
			return JsonResponse({'error': 'Permission denied'}, status=403)
		form = MaintenanceRequestCommentForm(request.POST)
		if form.is_valid():
			comment = form.save(commit=False)
			comment.request = maintenance_req
			if actor['staff']:
				comment.author = actor['staff']
				comment.author_name = actor['staff'].name
			elif actor['is_admin']:
				comment.author_name = request.user.get_full_name() or request.user.get_username()
			comment.save()
			return JsonResponse({'comment': serialize_comment(comment), 'message': 'Comment added.'}, status=201)
		return JsonResponse({'errors': form.errors}, status=400)

	if hide_comments_for_guest:
		comments_qs = MaintenanceRequestComment.objects.none()
	else:
		comments_qs = maintenance_req.comments.select_related('author')
	return JsonResponse({
		'comments': [serialize_comment(c) for c in comments_qs],
		'can_comment': can_comment,
	})


@require_guest_or_staff('Maintenance', 'Reception')
def maintenance_update(request, pk):
	"""Update maintenance status based on role."""
	actor = resolve_actor(request)
	try:
		maintenance_req = MaintenanceRequest.objects.select_related('assigned_to').get(pk=pk)
	except MaintenanceRequest.DoesNotExist:
		messages.error(request, 'Maintenance request not found.')
		return redirect('maintenance_list')

	allow_assignment = False
	allowed_statuses = []
	if actor['is_admin']:
		allow_assignment = True
		allowed_statuses = ['requested', 'assigned', 'in_progress', 'completed', 'cancelled']
	elif actor['staff_role'] == 'Maintenance' and actor['staff'] and maintenance_req.assigned_to_id == actor['staff'].id:
		allowed_statuses = ['in_progress', 'completed']
	else:
		messages.error(request, 'You do not have permission to update this request.')
		return redirect('maintenance_detail', pk=pk)

	form = MaintenanceRequestStatusForm(request.POST or None, instance=maintenance_req, allowed_statuses=allowed_statuses, allow_assignment=allow_assignment)

	if request.method == 'POST' and form.is_valid():
		updated = form.save(commit=False)
		if allow_assignment and updated.assigned_to and updated.status == 'requested':
			updated.status = 'assigned'
		updated.save()
		messages.success(request, 'Maintenance request updated.')
		return redirect('maintenance_detail', pk=pk)

	context = get_user_context(request)
	context.update({
		'form': form,
		'title': f"Update Maintenance Request #{maintenance_req.id}",
	})
	return render(request, 'core/form.html', context)


@require_guest_or_staff('Maintenance', 'Reception')
def maintenance_delete(request, pk):
	"""Allow admins to delete maintenance requests if needed."""
	actor = resolve_actor(request)
	if not actor['is_admin']:
		messages.error(request, 'Only admins can delete maintenance requests.')
		return redirect('maintenance_detail', pk=pk)

	try:
		maintenance_req = MaintenanceRequest.objects.get(pk=pk)
	except MaintenanceRequest.DoesNotExist:
		messages.error(request, 'Maintenance request not found.')
		return redirect('maintenance_list')

	if request.method == 'POST':
		maintenance_req.delete()
		messages.success(request, 'Maintenance request deleted.')
		return redirect('maintenance_list')

	context = get_user_context(request)
	context['object'] = maintenance_req
	return render(request, 'core/confirm_delete.html', context)


# ==================== SERVICE REQUEST MANAGEMENT ====================

@require_guest_or_staff('Reception')
def service_list(request):
	"""List all service requests"""
	service_requests = ServiceRequest.objects.select_related('guest', 'reservation').all()
	context = get_user_context(request)
	context['service_requests'] = service_requests
	return render(request, 'core/service_list.html', context)


@require_staff_role('Reception')
def service_create(request):
	"""Create a new service request"""
	if request.method == 'POST':
		form = ServiceRequestForm(request.POST)
		if form.is_valid():
			form.save()
			messages.success(request, 'Service request created successfully!')
			return redirect('service_list')
	else:
		form = ServiceRequestForm()
	context = get_user_context(request)
	context['form'] = form
	context['title'] = 'Create Service Request'
	return render(request, 'core/form.html', context)


@require_guest_or_staff('Reception')
def service_detail(request, pk):
	"""View service request details"""
	service = ServiceRequest.objects.select_related('guest', 'reservation').get(pk=pk)
	context = get_user_context(request)
	context['object'] = service
	context['title'] = f"Service Request #{service.id}"
	return render(request, 'core/service_detail.html', context)


@require_staff_role('Reception')
def service_update(request, pk):
	"""Update service request"""
	service = ServiceRequest.objects.get(pk=pk)
	if request.method == 'POST':
		form = ServiceRequestForm(request.POST, instance=service)
		if form.is_valid():
			form.save()
			messages.success(request, 'Service request updated successfully!')
			return redirect('service_detail', pk=pk)
	else:
		form = ServiceRequestForm(instance=service)
	context = get_user_context(request)
	context['form'] = form
	context['title'] = f"Update Service Request #{service.id}"
	return render(request, 'core/form.html', context)


@require_staff_role('Reception')
def service_delete(request, pk):
	"""Delete a service request"""
	service = ServiceRequest.objects.get(pk=pk)
	if request.method == 'POST':
		service.delete()
		messages.success(request, 'Service request deleted successfully!')
		return redirect('service_list')
	context = get_user_context(request)
	context['object'] = service
	return render(request, 'core/confirm_delete.html', context)

def guest_logout(request):
	request.session.flush()
	context = get_user_context(request)
	return render(request, 'logout.html', context)

# Note: guest-specific profile views removed — use unified `user_profile` and `change_password` views instead.


# ==================== UNIFIED USER PROFILE ====================

@csrf_protect
def user_profile(request):
	"""Unified profile page for all user types (guests, staff, admins)"""
	guest_id = request.session.get('guest_id')
	staff_id = request.session.get('staff_id')
	is_admin = request.user.is_authenticated and request.user.is_staff
	
	# Determine user type and get user object
	user_type = None
	user_obj = None
	form = None
	guest_reservations = []
	guest_id_display = ''
	
	if guest_id:
		user_type = 'guest'
		try:
			user_obj = Guest.objects.get(id=guest_id)
			guest_id_display = user_obj.id_document.split('|')[0] if user_obj.id_document else ''
			guest_reservations = list(
				Reservation.objects.filter(guest=user_obj)
				.select_related('room')
				.order_by('-check_in')
			)
		except Guest.DoesNotExist:
			request.session.flush()
			messages.error(request, 'Guest not found. Please log in again.')
			return redirect('guest_login')
	elif staff_id:
		user_type = 'staff'
		try:
			user_obj = Staff.objects.get(id=staff_id)
		except Staff.DoesNotExist:
			request.session.flush()
			messages.error(request, 'Staff not found. Please log in again.')
			return redirect('housekeeper_login')
	elif is_admin:
		user_type = 'admin'
		user_obj = request.user
	else:
		messages.error(request, 'You must be logged in to access your profile.')
		return redirect('guest_login')
	
	# Handle form submission
	if request.method == 'POST':
		if user_type == 'guest':
			form = GuestProfileForm(request.POST, instance=user_obj)
		elif user_type == 'staff':
			form = StaffProfileForm(request.POST, instance=user_obj)
		elif user_type == 'admin':
			form = None  # Admin profile editing not implemented yet
		
		if form and form.is_valid():
			try:
				form.save()
				messages.success(request, 'Your profile has been updated successfully!')
				return redirect('user_profile')
			except Exception as e:
				messages.error(request, f'An error occurred: {str(e)}')
	else:
		if user_type == 'guest':
			form = GuestProfileForm(instance=user_obj)
		elif user_type == 'staff':
			form = StaffProfileForm(instance=user_obj)
	
	context = get_user_context(request)
	context['form'] = form
	context['user_obj'] = user_obj
	context['user_type'] = user_type
	context['guest_reservations'] = guest_reservations
	context['guest_id_display'] = guest_id_display
	
	# Add reservation statistics for guest profile
	if user_type == 'guest':
		total_reservations = Reservation.objects.filter(guest=user_obj).count()
		completed_reservations = Reservation.objects.filter(
			guest=user_obj,
			status='checked-out'
		).count()
		context['total_reservations'] = total_reservations
		context['completed_reservations'] = completed_reservations
		context['points_balance'] = user_obj.loyalty_points
		context['can_redeem_points'] = user_obj.can_redeem()
		context['points_needed'] = max(35 - user_obj.loyalty_points, 0)
	
	return render(request, 'user_profile.html', context)


@csrf_protect
def change_password(request):
	"""Unified password change for all user types"""
	guest_id = request.session.get('guest_id')
	staff_id = request.session.get('staff_id')
	is_admin = request.user.is_authenticated and request.user.is_staff
	
	# Determine user type and get user object
	user_type = None
	user_obj = None
	
	if guest_id:
		user_type = 'guest'
		try:
			user_obj = Guest.objects.get(id=guest_id)
		except Guest.DoesNotExist:
			request.session.flush()
			messages.error(request, 'Guest not found. Please log in again.')
			return redirect('guest_login')
	elif staff_id:
		user_type = 'staff'
		try:
			user_obj = Staff.objects.get(id=staff_id)
		except Staff.DoesNotExist:
			request.session.flush()
			messages.error(request, 'Staff not found. Please log in again.')
			return redirect('housekeeper_login')
	elif is_admin:
		user_type = 'admin'
		user_obj = request.user
	else:
		messages.error(request, 'You must be logged in to change your password.')
		return redirect('guest_login')
	
	if request.method == 'POST':
		if user_type == 'guest':
			form = GuestPasswordChangeForm(request.POST)
		elif user_type == 'staff':
			form = StaffPasswordChangeForm(request.POST)
		elif user_type == 'admin':
			# reuse staff/admin password form fields
			form = StaffPasswordChangeForm(request.POST)
		
		if form.is_valid():
			try:
				if user_type == 'guest':
					# Verify current password
					current_password = form.cleaned_data['current_password']
					current_hash = hashlib.sha256(current_password.encode()).hexdigest()
					
					# Extract password hash from id_document
					stored = user_obj.id_document.split('|')
					stored_hash = stored[1] if len(stored) > 1 else ''
					
					if current_hash != stored_hash:
						messages.error(request, 'Current password is incorrect.')
						return redirect('change_password')
					
					# Update password
					new_password = form.cleaned_data['new_password']
					new_hash = hashlib.sha256(new_password.encode()).hexdigest()
					
					original_id = stored[0] if stored else user_obj.id_document
					user_obj.id_document = original_id + '|' + new_hash
					user_obj.save()
					
				elif user_type == 'staff':
					# Verify current password
					current_password = form.cleaned_data['current_password']
					current_hash = hashlib.sha256(current_password.encode()).hexdigest()

					if current_hash != user_obj.password_hash:
						messages.error(request, 'Current password is incorrect.')
						return redirect('change_password')

					# Update password
					new_password = form.cleaned_data['new_password']
					new_hash = hashlib.sha256(new_password.encode()).hexdigest()
					user_obj.password_hash = new_hash

				elif user_type == 'admin':
					# Verify current password using Django's User model
					current_password = form.cleaned_data['current_password']
					if not request.user.check_password(current_password):
						messages.error(request, 'Current password is incorrect.')
						return redirect('change_password')
					new_password = form.cleaned_data['new_password']
					request.user.set_password(new_password)
					request.user.save()
					# Re-authenticate and log the user back in
					user = authenticate(request, username=request.user.username, password=new_password)
					if user is not None:
						login(request, user)

				messages.success(request, 'Your password has been changed successfully!')
				return redirect('change_password')
			except Exception as e:
				messages.error(request, f'An error occurred: {str(e)}')
	else:
		if user_type == 'guest':
			form = GuestPasswordChangeForm()
		elif user_type == 'staff':
			form = StaffPasswordChangeForm()
		elif user_type == 'admin':
			form = StaffPasswordChangeForm()
		else:
			form = None
	
	context = get_user_context(request)
	context['form'] = form
	context['user_obj'] = user_obj
	context['user_type'] = user_type
	return render(request, 'change_password.html', context)


def api_room_rate(request, room_id):
	"""API endpoint to get room's daily rate"""
	try:
		room = Room.objects.get(id=room_id)
		return JsonResponse({'rate': float(room.rate)})
	except Room.DoesNotExist:
		return JsonResponse({'error': 'Room not found'}, status=404)


def api_room_booked_dates(request, room_id):
	"""API endpoint to get booked dates for a room"""
	try:
		room = Room.objects.get(id=room_id)
		bookings = Reservation.objects.filter(room=room, status__in=['confirmed', 'checked-in']).values('id', 'check_in', 'check_out')
		# Convert to proper format for JSON
		formatted_dates = []
		for booking in bookings:
			formatted_dates.append({
				'id': booking['id'],
				'check_in': booking['check_in'].isoformat(),
				'check_out': booking['check_out'].isoformat()
			})
		return JsonResponse({'booked_dates': formatted_dates})
	except Room.DoesNotExist:
		return JsonResponse({'error': 'Room not found'}, status=404)


def api_guest_points_info(request, guest_id):
	"""API endpoint to get a guest's point balance and redemption eligibility."""
	try:
		guest = Guest.objects.get(id=guest_id)
		return JsonResponse({
			'points': guest.loyalty_points,
			'can_redeem': guest.can_redeem(),
			'redeem_cost': 35,
			'discount_percent': 10 if guest.can_redeem() else 0,
		})
	except Guest.DoesNotExist:
		return JsonResponse({'error': 'Guest not found'}, status=404)


def error_403(request, exception=None):
	"""Render the branded 403 page with consistent navigation."""
	context = get_user_context(request)
	context['requested_path'] = request.path
	return render(request, '403.html', context, status=403)


def error_404(request, exception):
	"""Render the branded 404 page with consistent navigation."""
	context = get_user_context(request)
	context['requested_path'] = request.path
	return render(request, '404.html', context, status=404)


def error_500(request):
	"""Render the branded 500 page with consistent navigation."""
	context = get_user_context(request)
	context['requested_path'] = request.path
	return render(request, '500.html', context, status=500)