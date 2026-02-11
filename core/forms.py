from django import forms
from django.forms.widgets import DateInput, TimeInput, DateTimeInput
from django.core.exceptions import ValidationError
from django.core.cache import cache
from datetime import datetime, timedelta
from .models import (
    Guest,
    Reservation,
    Room,
    Housekeeping,
    Maintenance,
    MaintenanceRequest,
    MaintenanceRequestComment,
    ServiceRequest,
    Staff,
    Role,
)
import re


class ReportFilterForm(forms.Form):
    """Filters for admin reports (date range)."""

    start_date = forms.DateField(
        widget=DateInput(attrs={"class": "form-control", "type": "date"})
    )
    end_date = forms.DateField(
        widget=DateInput(attrs={"class": "form-control", "type": "date"})
    )

    include_occupancy = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Occupancy"
    )
    include_reservations = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Reservations"
    )
    include_services = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Service requests"
    )
    include_housekeeping = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Housekeeping"
    )
    include_maintenance = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Maintenance"
    )

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_date")
        end = cleaned_data.get("end_date")
        include_occupancy = cleaned_data.get("include_occupancy")
        include_reservations = cleaned_data.get("include_reservations")
        include_services = cleaned_data.get("include_services")
        include_housekeeping = cleaned_data.get("include_housekeeping")
        include_maintenance = cleaned_data.get("include_maintenance")

        if start and end and start > end:
            raise ValidationError("Start date must be on or before end date.")

        if not any([
            include_occupancy,
            include_reservations,
            include_services,
            include_housekeeping,
            include_maintenance,
        ]):
            raise ValidationError("Select at least one category to include in the report.")

        return cleaned_data


class GuestForm(forms.ModelForm):
    """Form for creating and updating Guest records with validation"""
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password (leave blank to keep current password)'
        }),
        help_text='Leave blank if you do not want to change the password.'
    )
    
    class Meta:
        model = Guest
        fields = ['first_name', 'last_name', 'email', 'phone', 'id_document', 
                  'preferences', 'special_requests']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last Name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email Address'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone Number'
            }),
            'id_document': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ID Document Number'
            }),
            'preferences': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Guest Preferences',
                'rows': 3
            }),
            'special_requests': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Special Requests',
                'rows': 3
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make preferences and special_requests optional
        self.fields['preferences'].required = False
        self.fields['special_requests'].required = False

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name', '').strip()
        if not first_name:
            raise ValidationError("First name is required.")
        if len(first_name) < 2:
            raise ValidationError("First name must be at least 2 characters long.")
        if len(first_name) > 50:
            raise ValidationError("First name cannot exceed 50 characters.")
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '').strip()
        if not last_name:
            raise ValidationError("Last name is required.")
        if len(last_name) < 2:
            raise ValidationError("Last name must be at least 2 characters long.")
        if len(last_name) > 50:
            raise ValidationError("Last name cannot exceed 50 characters.")
        return last_name

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            raise ValidationError("Email address is required.")
        # Check if email already exists (excluding current instance)
        if Guest.objects.filter(email=email).exclude(id=self.instance.id).exists():
            raise ValidationError("This email address is already registered.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            raise ValidationError("Phone number is required.")
        # Remove non-digit characters for validation
        digits_only = re.sub(r'\D', '', phone)
        if len(digits_only) < 10:
            raise ValidationError("Phone number must contain at least 10 digits.")
        if len(digits_only) > 15:
            raise ValidationError("Phone number cannot exceed 15 digits.")
        return phone

    def clean_id_document(self):
        id_document = self.cleaned_data.get('id_document', '').strip()
        if not id_document:
            raise ValidationError("ID document number is required.")
        if len(id_document) < 5:
            raise ValidationError("ID document must be at least 5 characters long.")
        # Only check uniqueness when creating new guest, not when updating
        # (since we append password hash to id_document)
        if self.instance.pk is None:  # New instance
            if Guest.objects.filter(id_document__startswith=id_document + '|').exists():
                raise ValidationError("This ID document is already registered.")
        return id_document

    def clean_password(self):
        password = self.cleaned_data.get('password', '').strip()
        if password and len(password) < 6:
            raise ValidationError("Password must be at least 6 characters long.")
        return password


class GuestRegistrationForm(forms.Form):
    """Public guest registration with basic strength and uniqueness checks."""

    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20)
    id_document = forms.CharField(max_length=100)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name', '').strip()
        if len(first_name) < 2:
            raise ValidationError("First name must be at least 2 characters long.")
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '').strip()
        if len(last_name) < 2:
            raise ValidationError("Last name must be at least 2 characters long.")
        return last_name

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if Guest.objects.filter(email=email).exists():
            raise ValidationError("This email address is already registered.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        digits_only = re.sub(r"\D", "", phone)
        if len(digits_only) < 10 or len(digits_only) > 15:
            raise ValidationError("Phone number must contain 10-15 digits.")
        return phone

    def clean_id_document(self):
        id_document = self.cleaned_data.get('id_document', '').strip()
        if len(id_document) < 5:
            raise ValidationError("ID document must be at least 5 characters long.")
        if Guest.objects.filter(id_document__startswith=f"{id_document}|").exists():
            raise ValidationError("This ID document is already registered.")
        return id_document

    def clean(self):
        cleaned = super().clean()
        pwd = cleaned.get('password', '').strip()
        confirm = cleaned.get('confirm_password', '').strip()
        if pwd and len(pwd) < 6:
            raise ValidationError("Password must be at least 6 characters long.")
        if pwd and confirm and pwd != confirm:
            raise ValidationError("Passwords do not match.")
        return cleaned


class ReservationForm(forms.ModelForm):
    """Form for creating and updating Reservation records with validation"""
    class Meta:
        model = Reservation
        fields = ['guest', 'room', 'check_in', 'check_out', 'status', 'total_charges']
        widgets = {
            'guest': forms.Select(attrs={
                'class': 'form-control'
            }),
            'room': forms.Select(attrs={
                'class': 'form-control'
            }),
            'check_in': DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'check_out': DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'total_charges': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Auto-calculated',
                'step': '0.01',
                'readonly': True
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make total_charges optional and read-only
        self.fields['total_charges'].required = False
        self.fields['total_charges'].widget.attrs['readonly'] = True

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in')
        check_out = cleaned_data.get('check_out')
        room = cleaned_data.get('room')

        if check_in and check_out:
            if check_in >= check_out:
                raise ValidationError("Check-out date must be after check-in date.")
            
            if (check_out - check_in).days < 1:
                raise ValidationError("Minimum stay is 1 night.")
            
            if (check_out - check_in).days > 365:
                raise ValidationError("Maximum stay is 365 days.")

            # Check if check-in is not in the past
            if check_in < datetime.now().date():
                raise ValidationError("Check-in date cannot be in the past.")

            # Check room availability if room is selected
            if room:
                # Only block if there's an active reservation (confirmed or checked-in)
                # Checked-out and cancelled reservations don't block availability
                overlapping_reservations = Reservation.objects.filter(
                    room=room,
                    check_in__lt=check_out,
                    check_out__gt=check_in,
                    status__in=['confirmed', 'checked-in']
                ).exclude(id=self.instance.id)
                
                if overlapping_reservations.exists():
                    raise ValidationError("This room is already booked for the selected dates.")

        total_charges = cleaned_data.get('total_charges')
        if total_charges and total_charges < 0:
            raise ValidationError("Total charges cannot be negative.")

        return cleaned_data


class RoomForm(forms.ModelForm):
    """Form for creating and updating Room records with validation"""
    class Meta:
        model = Room
        fields = ['number', 'floor', 'type', 'beds', 'rate', 'smoking_allowed', 'available', 'image']
        widgets = {
            'number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Room Number'
            }),
            'floor': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Floor Number'
            }),
            'type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Room Type (e.g., Single, Double, Suite)'
            }),
            'beds': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of Beds',
                'min': '1'
            }),
            'rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nightly Rate',
                'step': '0.01'
            }),
            'smoking_allowed': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'available': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control'
            }),
        }

    def clean_number(self):
        number = self.cleaned_data.get('number', '').strip()
        if not number:
            raise ValidationError("Room number is required.")
        if Room.objects.filter(number=number).exclude(id=self.instance.id).exists():
            raise ValidationError("This room number already exists.")
        return number

    def clean_floor(self):
        floor = self.cleaned_data.get('floor')
        if floor is not None and floor < 1:
            raise ValidationError("Floor number must be at least 1.")
        if floor is not None and floor > 50:
            raise ValidationError("Floor number cannot exceed 50.")
        return floor

    def clean_rate(self):
        rate = self.cleaned_data.get('rate')
        if rate is not None and rate <= 0:
            raise ValidationError("Room rate must be greater than 0.")
        if rate is not None and rate > 99999:
            raise ValidationError("Room rate seems too high. Please verify.")
        return rate

    def clean_type(self):
        room_type = self.cleaned_data.get('type', '').strip()
        if not room_type:
            raise ValidationError("Room type is required.")
        if len(room_type) < 2:
            raise ValidationError("Room type must be at least 2 characters long.")
        return room_type


class HousekeepingForm(forms.ModelForm):
    """Form for creating and updating Housekeeping tasks with validation"""
    class Meta:
        model = Housekeeping
        fields = ['room', 'staff', 'date', 'status', 'time_spent', 'deep_cleaning']
        widgets = {
            'room': forms.Select(attrs={
                'class': 'form-control'
            }),
            'staff': forms.Select(attrs={
                'class': 'form-control'
            }),
            'date': DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'time_spent': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Time Spent (HH:MM:SS)'
            }),
            'deep_cleaning': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date and date < datetime.now().date():
            raise ValidationError("Task date cannot be in the past.")
        return date

    def clean_time_spent(self):
        time_spent = self.cleaned_data.get('time_spent')
        if time_spent:
            try:
                # Validate HH:MM:SS format
                parts = time_spent.split(':')
                if len(parts) != 3:
                    raise ValueError()
                hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
                if not (0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= seconds <= 59):
                    raise ValueError()
            except (ValueError, AttributeError):
                raise ValidationError("Time spent must be in HH:MM:SS format (e.g., 02:30:00).")
        return time_spent


class MaintenanceForm(forms.ModelForm):
    """Form for creating and updating Maintenance requests with validation"""
    class Meta:
        model = Maintenance
        fields = ['room', 'requested_by', 'date_requested', 'time_from', 'time_to', 
                  'type', 'priority', 'assigned_to', 'cost']
        widgets = {
            'room': forms.Select(attrs={
                'class': 'form-control'
            }),
            'requested_by': forms.Select(attrs={
                'class': 'form-control'
            }),
            'date_requested': DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'time_from': TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'time_to': TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-control'
            }),
            'assigned_to': forms.Select(attrs={
                'class': 'form-control'
            }),
            'cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Cost',
                'step': '0.01'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        time_from = cleaned_data.get('time_from')
        time_to = cleaned_data.get('time_to')
        cost = cleaned_data.get('cost')

        if time_from and time_to:
            if time_from >= time_to:
                raise ValidationError("End time must be after start time.")

        if cost is not None and cost < 0:
            raise ValidationError("Cost cannot be negative.")

        return cleaned_data


class MaintenanceRequestGuestForm(forms.ModelForm):
    """Guest-facing form without scheduling control; admin/staff decide timing."""

    def __init__(self, *args, **kwargs):
        self.reservation = kwargs.pop('reservation', None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = MaintenanceRequest
        fields = ['type', 'comment']
        widgets = {
            'type': forms.Select(attrs={'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe the issue'}),
        }


class MaintenanceRequestAdminForm(forms.ModelForm):
    """Admin form with full control over assignment and status."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only allow assigning to maintenance staff
        self.fields['assigned_to'].queryset = Staff.objects.filter(role__name='Maintenance')

    class Meta:
        model = MaintenanceRequest
        fields = ['guest', 'reservation', 'room', 'requested_by_name', 'request_date', 'type', 'comment', 'status', 'assigned_to', 'internal_comment']
        widgets = {
            'guest': forms.Select(attrs={'class': 'form-control'}),
            'reservation': forms.Select(attrs={'class': 'form-control'}),
            'room': forms.Select(attrs={'class': 'form-control'}),
            'requested_by_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Requester name'}),
            'request_date': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'type': forms.Select(attrs={'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'internal_comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Internal notes (hidden from guests)'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        requested_by_name = cleaned_data.get('requested_by_name', '').strip()
        guest = cleaned_data.get('guest')
        reservation = cleaned_data.get('reservation')
        room = cleaned_data.get('room')
        if not requested_by_name and guest:
            cleaned_data['requested_by_name'] = f"{guest.first_name} {guest.last_name}"
        elif not requested_by_name and reservation and reservation.guest:
            guest_obj = reservation.guest
            cleaned_data['requested_by_name'] = f"{guest_obj.first_name} {guest_obj.last_name}"
        if reservation:
            if not guest:
                cleaned_data['guest'] = reservation.guest
            elif reservation.guest != guest:
                raise ValidationError('Selected guest does not match the reservation guest.')
            if not room:
                cleaned_data['room'] = reservation.room
            elif reservation.room != room:
                raise ValidationError('Selected room does not match the reservation room.')
        if reservation and cleaned_data.get('request_date'):
            req_date = cleaned_data['request_date']
            if req_date < reservation.check_in or req_date > reservation.check_out:
                raise ValidationError('Request date must fall inside the linked reservation.')
        return cleaned_data


class MaintenanceRequestStatusForm(forms.ModelForm):
    """Role-aware status update form (assignments only for admins)."""

    def __init__(self, *args, **kwargs):
        allowed_statuses = kwargs.pop('allowed_statuses', None)
        allow_assignment = kwargs.pop('allow_assignment', False)
        super().__init__(*args, **kwargs)
        if allowed_statuses:
            self.fields['status'].choices = [c for c in self.fields['status'].choices if c[0] in allowed_statuses]
        if not allow_assignment:
            self.fields.pop('assigned_to', None)
        else:
            # Only allow assigning to maintenance staff
            self.fields['assigned_to'].queryset = Staff.objects.filter(role__name='Maintenance')

    class Meta:
        model = MaintenanceRequest
        fields = ['status', 'assigned_to', 'internal_comment']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'internal_comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Add internal notes visible to staff'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        if status == 'cancelled' and cleaned_data.get('assigned_to') is None:
            # Admin can cancel without assignment; maintenance staff cannot cancel at all.
            pass
        return cleaned_data


class MaintenanceRequestCommentForm(forms.ModelForm):
    """Staff/internal comments (hidden from guests)."""

    class Meta:
        model = MaintenanceRequestComment
        fields = ['note']
        widgets = {
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Add a maintenance update (visible to staff and reception)'}),
        }


class ServiceRequestForm(forms.ModelForm):
    """Form for creating and updating Service requests with validation"""
    class Meta:
        model = ServiceRequest
        fields = ['guest', 'reservation', 'request_type', 'fulfilled_time', 'charge']
        widgets = {
            'guest': forms.Select(attrs={
                'class': 'form-control'
            }),
            'reservation': forms.Select(attrs={
                'class': 'form-control'
            }),
            'request_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Type of Service Request'
            }),
            'fulfilled_time': DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'charge': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Charge',
                'step': '0.01'
            }),
        }

    def clean_request_type(self):
        request_type = self.cleaned_data.get('request_type', '').strip()
        if not request_type:
            raise ValidationError("Service request type is required.")
        if len(request_type) < 3:
            raise ValidationError("Service type must be at least 3 characters long.")
        if len(request_type) > 100:
            raise ValidationError("Service type cannot exceed 100 characters.")
        return request_type

    def clean_charge(self):
        charge = self.cleaned_data.get('charge')
        if charge is not None and charge < 0:
            raise ValidationError("Charge cannot be negative.")
        return charge

class GuestProfileForm(forms.ModelForm):
    """Form for guests to edit their profile information"""
    class Meta:
        model = Guest
        fields = ['first_name', 'last_name', 'phone', 'id_document', 'preferences', 'special_requests']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last Name'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone Number'
            }),
            'id_document': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ID Document Number'
            }),
            'preferences': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Your Preferences (e.g., room type, amenities)',
                'rows': 3
            }),
            'special_requests': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Special Requests',
                'rows': 3
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make fields optional
        self.fields['preferences'].required = False
        self.fields['special_requests'].required = False
        # Prepopulate ID with base part (strip stored hash if present)
        if self.instance and self.instance.id_document:
            self.initial['id_document'] = self.instance.id_document.split('|')[0]

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name', '').strip()
        if not first_name:
            raise ValidationError("First name is required.")
        if len(first_name) < 2:
            raise ValidationError("First name must be at least 2 characters long.")
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '').strip()
        if not last_name:
            raise ValidationError("Last name is required.")
        if len(last_name) < 2:
            raise ValidationError("Last name must be at least 2 characters long.")
        return last_name

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            raise ValidationError("Phone number is required.")
        digits_only = re.sub(r'\D', '', phone)
        if len(digits_only) < 10:
            raise ValidationError("Phone number must contain at least 10 digits.")
        return phone

    def clean_id_document(self):
        id_document = self.cleaned_data.get('id_document', '').strip()
        if not id_document:
            raise ValidationError("ID document number is required.")
        if len(id_document) < 5:
            raise ValidationError("ID document must be at least 5 characters long.")
        # Ensure uniqueness based on the base part of the stored value
        conflict = Guest.objects.exclude(id=self.instance.id).filter(id_document__startswith=f"{id_document}|").exists()
        if conflict:
            raise ValidationError("This ID document is already registered.")
        return id_document

    def save(self, commit=True):
        guest = super().save(commit=False)
        base_id = self.cleaned_data.get('id_document', '').strip()
        existing_hash = ''
        if self.instance and self.instance.id_document and '|' in self.instance.id_document:
            existing_hash = self.instance.id_document.split('|', 1)[1]
        guest.id_document = base_id if not existing_hash else f"{base_id}|{existing_hash}"
        if commit:
            guest.save()
        return guest


class GuestPasswordChangeForm(forms.Form):
    """Form for guests to change their password"""
    current_password = forms.CharField(
        label='Current Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your current password'
        })
    )
    new_password = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your new password'
        })
    )
    confirm_password = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your new password'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError("New passwords do not match.")
            if len(new_password) < 6:
                raise ValidationError("New password must be at least 6 characters long.")
        
        return cleaned_data


class StaffProfileForm(forms.ModelForm):
    """Form for staff to edit their profile information"""
    class Meta:
        model = Staff
        fields = ['name', 'email', 'role']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full Name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email Address',
                'readonly': 'readonly'  # Email shouldn't be changed
            }),
            'role': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your Role',
                'readonly': 'readonly'  # Role is assigned by admin
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make email and role read-only
        self.fields['email'].disabled = True
        self.fields['role'].disabled = True

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError("Name is required.")
        if len(name) < 2:
            raise ValidationError("Name must be at least 2 characters long.")
        return name


class StaffPasswordChangeForm(forms.Form):
    """Form for staff to change their password"""
    current_password = forms.CharField(
        label='Current Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your current password'
        })
    )
    new_password = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your new password'
        })
    )
    confirm_password = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your new password'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError("New passwords do not match.")
            if len(new_password) < 6:
                raise ValidationError("New password must be at least 6 characters long.")
        
        return cleaned_data


class StaffForm(forms.ModelForm):
    """Form for admin to create or update Staff records (includes password on create/update).
    Password is optional on update; if provided it will be hashed and stored in `password_hash`.
    """
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password (leave blank to keep current)'
        })
    )

    class Meta:
        model = Staff
        fields = ['name', 'email', 'role', 'password']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            raise ValidationError('Email is required.')
        # Ensure unique email (exclude current instance)
        if Staff.objects.filter(email=email).exclude(id=self.instance.id).exists():
            raise ValidationError('This email address is already registered.')
        return email

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError('Name is required.')
        if len(name) < 2:
            raise ValidationError('Name must be at least 2 characters long.')
        return name

    def clean_password(self):
        pwd = self.cleaned_data.get('password')
        # Require password when creating a new staff record
        if not self.instance.pk and not pwd:
            raise ValidationError('Password is required when creating a new staff account.')
        if pwd and len(pwd) < 6:
            raise ValidationError('Password must be at least 6 characters long.')
        return pwd

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Use DB-managed Role choices; restrict to staff/admin categories for create/edit
        try:
            self.fields['role'].queryset = Role.objects.filter(category__in=['staff', 'admin'])
        except Exception:
            # If Role table isn't available yet (migrations), fall back to empty queryset
            self.fields['role'].queryset = Role.objects.none()

    def save(self, commit=True):
        instance = super().save(commit=False)
        pwd = self.cleaned_data.get('password')
        if pwd:
            import hashlib
            instance.password_hash = hashlib.sha256(pwd.encode()).hexdigest()
        if commit:
            instance.save()
        return instance


class StaffRegistrationForm(StaffForm):
    """Public staff registration wrapper that requires a role selection."""

    class Meta(StaffForm.Meta):
        fields = ['name', 'email', 'role', 'password']


class PublicReservationRequestForm(forms.Form):
    """Validates public reservation details for booking and payment flows."""

    room = forms.ModelChoiceField(queryset=Room.objects.all())
    check_in = forms.DateField(widget=DateInput(attrs={"type": "date"}))
    check_out = forms.DateField(widget=DateInput(attrs={"type": "date"}))
    id_document = forms.CharField(max_length=100)

    def clean_id_document(self):
        val = self.cleaned_data.get('id_document', '').strip()
        if len(val) < 5:
            raise ValidationError("ID document must be at least 5 characters long.")
        return val

    def clean(self):
        cleaned = super().clean()
        room = cleaned.get('room')
        check_in = cleaned.get('check_in')
        check_out = cleaned.get('check_out')

        if check_in and check_out:
            if check_in >= check_out:
                raise ValidationError("Check-out date must be after check-in date.")
            if (check_out - check_in).days < 1:
                raise ValidationError("Minimum stay is 1 night.")
            if (check_out - check_in).days > 365:
                raise ValidationError("Maximum stay is 365 days.")
            from datetime import date as _date
            if check_in < _date.today():
                raise ValidationError("Check-in date cannot be in the past.")
            if room and not room.is_available_for_dates(check_in, check_out):
                raise ValidationError("Selected room is not available for those dates.")

        return cleaned


class GuestLoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


class StaffLoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


class ServiceOrderForm(forms.Form):
    """Validates menu item selection for service ordering."""

    item_name = forms.CharField(max_length=100)

    def __init__(self, *args, **kwargs):
        self.allowed_items = kwargs.pop('allowed_items', []) or []
        super().__init__(*args, **kwargs)

    def clean_item_name(self):
        name = (self.cleaned_data.get('item_name') or '').strip()
        if not name:
            raise ValidationError("Please pick a menu item to order.")
        if self.allowed_items and name not in self.allowed_items:
            raise ValidationError("Selected item is not available.")
        return name
