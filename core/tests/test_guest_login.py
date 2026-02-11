import hashlib
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from core.models import Guest


class GuestLoginViewTests(TestCase):
    def setUp(self):
        self.password = "StaySecure123"
        password_hash = hashlib.sha256(self.password.encode()).hexdigest()
        # id_document stores the plain document plus the hashed password separated by '|'
        self.guest = Guest.objects.create(
            first_name="Grace",
            last_name="Hopper",
            email="guest@example.com",
            phone="1234567890",
            id_document=f"ID12345|{password_hash}",
        )
        self.url = reverse("guest_login")

    def test_login_success_redirects_home_and_sets_session(self):
        response = self.client.post(self.url, {
            "email": self.guest.email,
            "password": self.password,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))
        self.assertEqual(self.client.session.get("guest_id"), self.guest.id)

    def test_login_with_invalid_password_shows_error(self):
        response = self.client.post(self.url, {
            "email": self.guest.email,
            "password": "wrongpass",
        })

        self.assertEqual(response.status_code, 200)
        messages = list(response.context["messages"])
        self.assertTrue(any("Invalid credentials" in m.message for m in messages))
        self.assertIsNone(self.client.session.get("guest_id"))

    def test_rate_limited_request_blocks_login_attempt(self):
        with patch("core.views.check_rate_limit", return_value=False):
            response = self.client.post(self.url, {
                "email": self.guest.email,
                "password": self.password,
            })

        self.assertEqual(response.status_code, 200)
        messages = list(response.context["messages"])
        self.assertTrue(any("Too many login attempts" in m.message for m in messages))
        self.assertIsNone(self.client.session.get("guest_id"))
