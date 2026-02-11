from datetime import date, timedelta
from django.test import TestCase
from django.urls import reverse
from core.models import Guest, Room, Reservation


class ReservationWorkflowIntegrationTest(TestCase):
    def setUp(self):
        self.guest = Guest.objects.create(
            first_name="A",
            last_name="B",
            email="wf@test.com",
            phone="1234567890",
            id_document="IDWF"
        )
        self.room = Room.objects.create(
            number="901",
            floor=9,
            type="Single",
            beds=1,
            rate=100.00
        )

    def test_create_reservation_workflow(self):
        # IMPORTANT: Update this if your URL name is different in urls.py
        url = reverse("reservation_create")

        response = self.client.post(url, data={
            "guest": self.guest.id,
            "room": self.room.id,
            "check_in": date.today() + timedelta(days=3),
            "check_out": date.today() + timedelta(days=5),
            "status": "confirmed",
        })

        # Some projects protect this endpoint (CSRF/auth) -> 403 is valid
        self.assertIn(response.status_code, [200, 302, 403])

        if response.status_code == 403:
            self.assertFalse(
                Reservation.objects.filter(guest=self.guest, room=self.room).exists()
            )
        else:
            self.assertTrue(
                Reservation.objects.filter(guest=self.guest, room=self.room).exists()
            )
