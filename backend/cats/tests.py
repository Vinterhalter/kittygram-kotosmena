from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from .models import Cat, Achievement


class CatAccessTests(APITestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            "cat_owner", password="Cat-owner-482!"
        )
        self.other = get_user_model().objects.create_user(
            "cat_other", password="Cat-other-482!"
        )
        self.cat = Cat.objects.create(
            owner=self.owner, name="Персик", color="ginger", birth_year=2022
        )
        self.client.force_authenticate(self.owner)

    def test_owner_is_taken_from_authentication(self):
        response = self.client.post(
            "/api/cats/",
            {
                "name": "Луна",
                "color": "white",
                "birth_year": 2023,
                "owner": self.other.pk,
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["owner"], self.owner.pk)

    def test_other_user_reads_but_cannot_change_or_delete(self):
        self.client.force_authenticate(self.other)
        url = f"/api/cats/{self.cat.pk}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.patch(url, {"name": "Чужое имя"}).status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.name, "Персик")

    def test_invalid_birth_year_does_not_create_cat(self):
        response = self.client.post(
            "/api/cats/",
            {"name": "Луна", "color": "white", "birth_year": timezone.now().year + 1},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("birth_year", response.data)
        self.assertEqual(Cat.objects.count(), 1)

    def test_achievements_can_be_assigned_and_removed(self):
        achievement = Achievement.objects.create(name="Освоил переноску")
        url = f"/api/cats/{self.cat.pk}/"
        response = self.client.patch(
            url, {"achievements": [achievement.pk]}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["achievements"], [achievement.pk])
        self.assertEqual(
            self.client.patch(url, {"achievements": []}, format="json").status_code, 200
        )
        self.assertFalse(self.cat.achievements.exists())

    def test_guest_cannot_read_cats(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/cats/").status_code, 401)
