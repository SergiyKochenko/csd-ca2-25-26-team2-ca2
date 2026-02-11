from datetime import date, timedelta
from django.test import TestCase
from core.forms import GuestForm, RoomForm, ReservationForm
from core.models import Guest, Room, Reservation


class GuestFormTests(TestCase):
    def test_guest_form_valid_data(self):
        form = GuestForm(data={
            "first_name": "Vijaya",
            "last_name": "PB",
            "email": "vijaya@test.com",
            "phone": "1234567890",
            "id_document": "ID12345",
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_guest_form_duplicate_email_fails(self):
        Guest.objects.create(
            first_name="A", last_name="B",
            email="dup@test.com", phone="1234567890", id_document="ID11111"
        )
        form = GuestForm(data={
            "first_name": "C",
            "last_name": "D",
            "email": "dup@test.com",
            "phone": "1234567890",
            "id_document": "ID22222"
        })
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_guest_form_short_password_fails(self):
        form = GuestForm(data={
            "first_name": "Vijaya",
            "last_name": "PB",
            "email": "pw@test.com",
            "phone": "1234567890",
            "id_document": "ID33333",
            "password": "123"
        })
        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)


class RoomFormTests(TestCase):
    def test_room_form_duplicate_room_number_fails(self):
        Room.objects.create(number="101", floor=1, type="Single", beds=1, rate=100.00)
        form = RoomForm(data={
            "number": "101",
            "floor": 2,
            "type": "Double",
            "beds": 2,
            "rate": 150.00,
            "smoking_allowed": False,
            "available": True
        })
        self.assertFalse(form.is_valid())
        self.assertIn("number", form.errors)

    def test_room_form_invalid_rate_fails(self):
        form = RoomForm(data={
            "number": "202",
            "floor": 2,
            "type": "Double",
            "beds": 2,
            "rate": 0,
            "smoking_allowed": False,
            "available": True
        })
        self.assertFalse(form.is_valid())
        self.assertIn("rate", form.errors)


class ReservationFormTests(TestCase):
    def setUp(self):
        self.guest = Guest.objects.create(
            first_name="A", last_name="B",
            email="g@test.com", phone="1234567890", id_document="ID44444"
        )
        self.room = Room.objects.create(number="303", floor=3, type="Single", beds=1, rate=100.00)

    def test_reservation_form_check_out_before_check_in_fails(self):
        form = ReservationForm(data={
            "guest": self.guest.id,
            "room": self.room.id,
            "check_in": date.today() + timedelta(days=5),
            "check_out": date.today() + timedelta(days=4),
            "status": "confirmed",
        })
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_reservation_form_past_check_in_fails(self):
        form = ReservationForm(data={
            "guest": self.guest.id,
            "room": self.room.id,
            "check_in": date.today() - timedelta(days=1),
            "check_out": date.today() + timedelta(days=2),
            "status": "confirmed",
        })
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_reservation_form_overlapping_confirmed_fails(self):
        Reservation.objects.create(
            guest=self.guest,
            room=self.room,
            check_in=date.today() + timedelta(days=5),
            check_out=date.today() + timedelta(days=7),
            status="confirmed",
            total_charges=200
        )
        form = ReservationForm(data={
            "guest": self.guest.id,
            "room": self.room.id,
            "check_in": date.today() + timedelta(days=6),
            "check_out": date.today() + timedelta(days=8),
            "status": "confirmed"
        })
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())
