
from django.db import models
from cloudinary.models import CloudinaryField


class Role(models.Model):
	"""Roles stored in DB. category indicates broad type: 'admin', 'guest', or 'staff'."""
	ROLE_CATEGORY_CHOICES = [
		('admin', 'Admin'),
		('guest', 'Guest'),
		('staff', 'Staff'),
	]
	name = models.CharField(max_length=50, unique=True)
	category = models.CharField(max_length=10, choices=ROLE_CATEGORY_CHOICES, default='staff')

	def __str__(self):
		return self.name

class Guest(models.Model):
	first_name = models.CharField(max_length=50)
	last_name = models.CharField(max_length=50)
	email = models.EmailField()
	phone = models.CharField(max_length=20)
	id_document = models.CharField(max_length=100)
	preferences = models.TextField(blank=True)
	special_requests = models.TextField(blank=True)
	loyalty_points = models.IntegerField(default=0)

	def __str__(self):
		return f"{self.first_name} {self.last_name}"
	
	def award_points(self, points: int):
		"""Increase the guest's point balance by the given amount."""
		if points <= 0:
			return
		self.loyalty_points = models.F('loyalty_points') + points
		self.save(update_fields=['loyalty_points'])
		self.refresh_from_db(fields=['loyalty_points'])

	def remove_points(self, points: int):
		"""Safely remove points without going negative."""
		if points <= 0:
			return
		self.loyalty_points = models.F('loyalty_points') - points
		self.save(update_fields=['loyalty_points'])
		self.refresh_from_db(fields=['loyalty_points'])
		if self.loyalty_points < 0:
			self.loyalty_points = 0
			self.save(update_fields=['loyalty_points'])

	def can_redeem(self, cost: int = 35) -> bool:
		"""Return True when the guest has enough points to redeem."""
		return self.loyalty_points >= cost

	def redeem_points(self, cost: int = 35) -> bool:
		"""Deduct points if possible. Returns True when deduction happened."""
		if not self.can_redeem(cost):
			return False
		self.loyalty_points = models.F('loyalty_points') - cost
		self.save(update_fields=['loyalty_points'])
		self.refresh_from_db(fields=['loyalty_points'])
		return True

class Room(models.Model):
	number = models.CharField(max_length=10)
	floor = models.IntegerField()
	type = models.CharField(max_length=50)
	beds = models.IntegerField(default=1)
	rate = models.DecimalField(max_digits=8, decimal_places=2)
	smoking_allowed = models.BooleanField(default=False)
	available = models.BooleanField(default=True)
	image = CloudinaryField('room-image', folder='rooms', blank=True, null=True)

	def __str__(self):
		return f"Room {self.number}"
	
	def get_booked_dates(self):
		"""Return a list of booked date ranges for this room"""
		from datetime import timedelta
		bookings = Reservation.objects.filter(room=self, status__in=['confirmed', 'checked-in']).values_list('check_in', 'check_out')
		booked_ranges = []
		for check_in, check_out in bookings:
			# Generate all dates in range
			current = check_in
			dates = []
			while current < check_out:
				dates.append(current.isoformat())
				current += timedelta(days=1)
			booked_ranges.append({
				'check_in': check_in.isoformat(),
				'check_out': check_out.isoformat(),
				'dates': dates
			})
		return booked_ranges
	
	def is_available_for_dates(self, check_in, check_out):
		"""Check if room is available for given date range.
		Ensures no overlap with confirmed or checked-in reservations.
		Checked-out reservations don't block availability (guest has already left).
		"""
		# Convert to date objects if they're strings
		if isinstance(check_in, str):
			from datetime import datetime
			check_in = datetime.fromisoformat(check_in).date()
		if isinstance(check_out, str):
			from datetime import datetime
			check_out = datetime.fromisoformat(check_out).date()
		
		overlapping = Reservation.objects.filter(
			room=self,
			status__in=['confirmed', 'checked-in'],
			check_in__lt=check_out,
			check_out__gt=check_in
		)
		return not overlapping.exists()

class Reservation(models.Model):
	guest = models.ForeignKey(Guest, on_delete=models.CASCADE)
	room = models.ForeignKey(Room, on_delete=models.CASCADE)
	check_in = models.DateField()
	check_out = models.DateField()
	status = models.CharField(max_length=20, choices=[
		("confirmed", "Confirmed"),
		("checked-in", "Checked-in"),
		("checked-out", "Checked-out"),
		("cancelled", "Cancelled")
	])
	total_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
	used_points_discount = models.BooleanField(default=False)
	points_redeemed = models.IntegerField(default=0)
	points_awarded = models.BooleanField(default=False)

	def __str__(self):
		return f"Reservation for {self.guest} in {self.room}"

class Staff(models.Model):
	name = models.CharField(max_length=100)
	# role moved to Role model (ForeignKey)
	role = models.ForeignKey('Role', on_delete=models.SET_NULL, null=True)
	email = models.EmailField(unique=True)
	password_hash = models.CharField(max_length=128)

	def __str__(self):
		return self.name

class Housekeeping(models.Model):
	room = models.ForeignKey(Room, on_delete=models.CASCADE)
	staff = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
	date = models.DateField()
	status = models.CharField(max_length=20, choices=[
		("scheduled", "Scheduled"),
		("in-progress", "In-progress"),
		("completed", "Completed"),
		("inspected", "Inspected")
	])
	time_spent = models.DurationField(null=True, blank=True)
	deep_cleaning = models.BooleanField(default=False)

	def __str__(self):
		return f"Housekeeping {self.room} on {self.date}"

class Maintenance(models.Model):
	room = models.ForeignKey(Room, on_delete=models.CASCADE)
	requested_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name="maintenance_requests")
	date_requested = models.DateField()
	time_from = models.TimeField(null=True, blank=True)
	time_to = models.TimeField(null=True, blank=True)
	type = models.CharField(max_length=30, choices=[
		("plumbing", "Plumbing"),
		("electrical", "Electrical"),
		("hvac", "HVAC"),
		("furniture", "Furniture"),
		("appliances", "Appliances"),
		("Room Cleaning", "Room Cleaning"),
	])
	priority = models.CharField(max_length=10, choices=[
		("low", "Low"),
		("medium", "Medium"),
		("high", "High"),
		("emergency", "Emergency")
	])
	assigned_to = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name="maintenance_assigned")
	cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
	status = models.CharField(max_length=20, choices=[
		("scheduled", "Scheduled"),
		("in-progress", "In-progress"),
		("completed", "Completed"),
		("inspected", "Inspected")
	])

	def __str__(self):
		return f"Maintenance {self.type} in {self.room}"


class MaintenanceRequest(models.Model):
	"""Guest-facing maintenance request with role-aware workflow."""

	STATUS_CHOICES = [
		("requested", "Requested"),
		("assigned", "Assigned"),
		("in_progress", "In Progress"),
		("completed", "Completed"),
		("cancelled", "Cancelled"),
	]

	TYPE_CHOICES = [
		("plumbing", "Plumbing"),
		("electrical", "Electrical"),
		("hvac", "HVAC"),
		("furniture", "Furniture"),
		("appliances", "Appliances"),
		("room_cleaning", "Room Cleaning"),
		("other", "Other"),
	]

	guest = models.ForeignKey(Guest, on_delete=models.SET_NULL, null=True, blank=True, related_name="maintenance_requests")
	reservation = models.ForeignKey(Reservation, on_delete=models.SET_NULL, null=True, blank=True, related_name="maintenance_requests")
	room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="maintenance_requests")
	requested_by_name = models.CharField(max_length=120)
	request_date = models.DateField()
	type = models.CharField(max_length=30, choices=TYPE_CHOICES)
	comment = models.TextField(blank=True)
	internal_comment = models.TextField(blank=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="requested")
	assigned_to = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_maintenance_requests")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		return f"{self.get_type_display()} for {self.room}"

	@property
	def guest_visible_status(self) -> str:
		"""Collapse internal statuses to the limited guest-friendly set."""
		if self.status in {"assigned", "in_progress"}:
			return "In Progress"
		if self.status == "completed":
			return "Completed"
		if self.status == "cancelled":
			return "Completed"
		return "Requested"


class MaintenanceRequestComment(models.Model):
	"""Internal comment for maintenance requests (hidden from guests)."""

	request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, related_name="comments")
	author = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="maintenance_comments")
	author_name = models.CharField(max_length=120, blank=True)
	note = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["created_at"]

	def __str__(self):
		return f"Comment on request #{self.request_id}"

class ServiceRequest(models.Model):
	guest = models.ForeignKey(Guest, on_delete=models.CASCADE)
	reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE)
	request_type = models.CharField(max_length=50)
	timestamp = models.DateTimeField(auto_now_add=True)
	fulfilled_time = models.DateTimeField(null=True, blank=True)
	charge = models.DecimalField(max_digits=8, decimal_places=2, default=0)

	def __str__(self):
		return f"Service {self.request_type} for {self.guest}"


# Signal handlers for point accrual
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


@receiver(post_save, sender=Reservation)
def sync_points_on_reservation_save(sender, instance, created, **kwargs):
	"""Award or roll back points when reservation status changes."""
	if not instance.guest:
		return

	if instance.status == 'checked-out' and not instance.points_awarded:
		instance.guest.award_points(5)
		Reservation.objects.filter(pk=instance.pk).update(points_awarded=True)
	elif instance.status != 'checked-out' and instance.points_awarded:
		instance.guest.remove_points(5)
		Reservation.objects.filter(pk=instance.pk).update(points_awarded=False)


@receiver(post_delete, sender=Reservation)
def sync_points_on_reservation_delete(sender, instance, **kwargs):
	"""Return awarded points if a reservation is removed."""
	if instance.guest and instance.points_awarded:
		instance.guest.remove_points(5)
