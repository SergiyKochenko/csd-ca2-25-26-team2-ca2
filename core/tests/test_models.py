from datetime import date, timedelta
from django.test import TestCase
from core.models import Guest, Room, Reservation


class GuestModelTest(TestCase):
    def test_guest_str(self):
        guest = Guest.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="1234567890",
            id_document="ID12345"
        )
        self.assertEqual(str(guest), "John Doe")


class RoomModelTest(TestCase):
    def test_room_str(self):
        room = Room.objects.create(
            number="101",
            floor=1,
            type="Single",
            beds=1,
            rate=100.00
        )
        self.assertEqual(str(room), "Room 101")


class ReservationModelTest(TestCase):
    def test_reservation_str(self):
        guest = Guest.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            phone="0987654321",
            id_document="ID67890"
        )
        room = Room.objects.create(
            number="102",
            floor=1,
            type="Double",
            beds=2,
            rate=150.00
        )
        reservation = Reservation.objects.create(
            guest=guest,
            room=room,
            check_in=date.today() + timedelta(days=1),
            check_out=date.today() + timedelta(days=3),
            status="confirmed"
        )
        self.assertIn("Reservation for", str(reservation))
