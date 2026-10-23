from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase
from PIL import Image
from cats.models import Cat
from .models import Handover, CareTask, Completion, Incident


class CareFlowTests(APITestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user("owner", password="Owner-pass-426!")
        self.sitter = users.objects.create_user("sitter", password="Sitter-pass-426!")
        self.stranger = users.objects.create_user(
            "stranger", password="Stranger-pass-426!"
        )
        self.cat = Cat.objects.create(
            owner=self.owner, name="Марс", color="ginger", birth_year=2021
        )
        self.now = timezone.now()
        self.h = Handover.objects.create(
            cat=self.cat,
            owner=self.owner,
            sitter=self.sitter,
            starts_at=self.now - timedelta(hours=1),
            ends_at=self.now + timedelta(days=1),
        )
        self.t = CareTask.objects.create(
            handover=self.h, title="Покормить", due_at=self.now + timedelta(hours=1)
        )
        self.client.force_authenticate(self.owner)

    def url(self, tail=""):
        return f"/api/handovers/{self.h.pk}/{tail}"

    def activate(self):
        self.h.status = "active"
        self.h.save()

    def submit(self):
        self.client.force_authenticate(self.sitter)
        return self.client.post(
            "/api/completions/", {"task": self.t.pk, "note": "Корм и вода заменены."}
        )

    def test_full_flow_with_rework_and_incident(self):
        self.client.force_authenticate(self.sitter)
        self.assertEqual(self.client.post(self.url("accept/")).status_code, 200)
        r = self.submit()
        self.assertEqual(r.status_code, 201)
        first = r.data["id"]
        self.client.force_authenticate(self.owner)
        r = self.client.post(
            f"/api/completions/{first}/review/",
            {"decision": "rejected", "note": "Уточните объём корма."},
        )
        self.assertEqual(r.status_code, 200)
        r = self.submit()
        self.assertEqual(r.status_code, 201)
        second = r.data["id"]
        incident = self.client.post(
            "/api/incidents/",
            {
                "handover": self.h.pk,
                "severity": "urgent",
                "description": "Корм заканчивается.",
            },
        )
        self.assertEqual(incident.status_code, 201)
        self.client.force_authenticate(self.owner)
        self.assertEqual(
            self.client.post(
                f"/api/completions/{second}/review/", {"decision": "approved"}
            ).status_code,
            200,
        )
        self.assertEqual(self.client.post(self.url("close/")).status_code, 400)
        self.assertEqual(
            self.client.post(
                f"/api/incidents/{incident.data['id']}/resolve/",
                {"resolution": "Передан запас корма."},
            ).status_code,
            200,
        )
        self.assertEqual(self.client.post(self.url("close/")).status_code, 200)
        self.assertEqual(
            self.client.get(self.url("report/")).data["approved_required"], 1
        )
        self.assertEqual(self.h.events.count(), 8)

    def test_private_lists_and_detail(self):
        self.client.force_authenticate(self.stranger)
        for resource, obj in [("handovers", self.h), ("tasks", self.t)]:
            self.assertEqual(self.client.get(f"/api/{resource}/").data["count"], 0)
            self.assertEqual(
                self.client.get(f"/api/{resource}/{obj.pk}/").status_code, 404
            )
        self.assertEqual(self.client.get(self.url("events/")).status_code, 404)
        self.assertEqual(self.client.get(self.url("report/")).status_code, 404)
        self.assertEqual(
            self.client.post(
                "/api/completions/", {"task": self.t.pk, "note": "Попытка постороннего"}
            ).status_code,
            404,
        )

    def test_guest_unauthorized(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/handovers/").status_code, 401)

    def test_owner_cannot_accept(self):
        self.assertEqual(self.client.post(self.url("accept/")).status_code, 403)

    def test_accept_requires_required_task(self):
        self.t.delete()
        self.client.force_authenticate(self.sitter)
        self.assertEqual(self.client.post(self.url("accept/")).status_code, 400)

    def test_expired_accept(self):
        self.h.starts_at = self.now - timedelta(days=2)
        self.h.ends_at = self.now - timedelta(days=1)
        self.h.save()
        self.client.force_authenticate(self.sitter)
        self.assertEqual(self.client.post(self.url("accept/")).status_code, 400)

    def test_invalid_dates(self):
        r = self.client.post(
            "/api/handovers/",
            {
                "cat": self.cat.pk,
                "sitter": "sitter",
                "starts_at": self.now.isoformat(),
                "ends_at": (self.now - timedelta(hours=1)).isoformat(),
            },
        )
        self.assertEqual(r.status_code, 400)

    def test_self_assignment(self):
        r = self.client.post(
            "/api/handovers/",
            {
                "cat": self.cat.pk,
                "sitter": "owner",
                "starts_at": self.now.isoformat(),
                "ends_at": (self.now + timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(r.status_code, 400)

    def test_foreign_cat(self):
        self.client.force_authenticate(self.stranger)
        r = self.client.post(
            "/api/handovers/",
            {
                "cat": self.cat.pk,
                "sitter": "sitter",
                "starts_at": self.now.isoformat(),
                "ends_at": (self.now + timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(r.status_code, 400)

    def test_overlap(self):
        r = self.client.post(
            "/api/handovers/",
            {
                "cat": self.cat.pk,
                "sitter": "sitter",
                "starts_at": self.now.isoformat(),
                "ends_at": (self.now + timedelta(days=2)).isoformat(),
            },
        )
        self.assertEqual(r.status_code, 400)

    def test_adjacent_period(self):
        r = self.client.post(
            "/api/handovers/",
            {
                "cat": self.cat.pk,
                "sitter": "sitter",
                "starts_at": self.h.ends_at.isoformat(),
                "ends_at": (self.h.ends_at + timedelta(days=2)).isoformat(),
            },
        )
        self.assertEqual(r.status_code, 201)

    def test_task_due_outside_shift(self):
        self.assertEqual(
            self.client.patch(
                f"/api/tasks/{self.t.pk}/",
                {"due_at": (self.h.ends_at + timedelta(days=1)).isoformat()},
            ).status_code,
            400,
        )

    def test_sitter_cannot_edit_plan(self):
        self.client.force_authenticate(self.sitter)
        self.assertEqual(
            self.client.patch(
                f"/api/tasks/{self.t.pk}/", {"title": "Другой план"}
            ).status_code,
            403,
        )

    def test_active_plan_immutable(self):
        self.activate()
        for verb in [self.client.patch, self.client.delete]:
            r = verb(f"/api/tasks/{self.t.pk}/", {"title": "Изменено"})
            self.assertEqual(r.status_code, 400)

    def test_owner_cannot_complete(self):
        self.activate()
        self.assertEqual(
            self.client.post(
                "/api/completions/", {"task": self.t.pk, "note": "Готово"}
            ).status_code,
            403,
        )

    def test_duplicate_submission(self):
        self.activate()
        self.assertEqual(self.submit().status_code, 201)
        duplicate = self.submit()
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("task", duplicate.data)

    def test_photo_required(self):
        self.activate()
        self.t.photo_required = True
        self.t.save()
        self.assertEqual(self.submit().status_code, 400)

    def test_private_photo_access(self):
        self.activate()
        self.client.force_authenticate(self.sitter)
        with TemporaryDirectory() as temp:
            from .models import private_storage

            with override_settings(PRIVATE_MEDIA_ROOT=temp):
                # Storage instance is explicitly configured; temporarily point it at the test directory.
                previous = private_storage.location
                private_storage.__dict__["location"] = temp
                try:
                    buf = BytesIO()
                    Image.new("RGB", (32, 32), "red").save(buf, format="PNG")
                    photo = SimpleUploadedFile(
                        "test.png", buf.getvalue(), content_type="image/png"
                    )
                    r = self.client.post(
                        "/api/completions/",
                        {"task": self.t.pk, "note": "Готово", "evidence": photo},
                        format="multipart",
                    )
                    self.assertEqual(r.status_code, 201)
                    url = f"/api/completions/{r.data['id']}/evidence/"
                    self.assertNotIn("/media/", r.data["evidence_url"])
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(
                        b"".join(response.streaming_content), buf.getvalue()
                    )
                    self.client.force_authenticate(self.stranger)
                    self.assertEqual(self.client.get(url).status_code, 404)
                finally:
                    private_storage.__dict__["location"] = previous

    def test_sitter_cannot_review(self):
        self.activate()
        r = self.submit()
        self.assertEqual(
            self.client.post(
                f"/api/completions/{r.data['id']}/review/", {"decision": "approved"}
            ).status_code,
            403,
        )

    def test_rejection_reason_required(self):
        self.activate()
        r = self.submit()
        self.client.force_authenticate(self.owner)
        self.assertEqual(
            self.client.post(
                f"/api/completions/{r.data['id']}/review/", {"decision": "rejected"}
            ).status_code,
            400,
        )

    def test_double_review(self):
        self.activate()
        r = self.submit()
        self.client.force_authenticate(self.owner)
        url = f"/api/completions/{r.data['id']}/review/"
        self.assertEqual(
            self.client.post(url, {"decision": "approved"}).status_code, 200
        )
        self.assertEqual(
            self.client.post(url, {"decision": "approved"}).status_code, 400
        )

    def test_close_unapproved_tasks(self):
        self.activate()
        self.assertEqual(self.client.post(self.url("close/")).status_code, 400)

    def test_complete_outside_period(self):
        self.activate()
        self.h.starts_at = self.now + timedelta(hours=2)
        self.h.save()
        self.assertEqual(self.submit().status_code, 400)

    def test_sitter_cannot_resolve(self):
        self.activate()
        i = Incident.objects.create(
            handover=self.h,
            author=self.sitter,
            severity="normal",
            description="Проблема",
        )
        self.client.force_authenticate(self.sitter)
        self.assertEqual(
            self.client.post(
                f"/api/incidents/{i.pk}/resolve/", {"resolution": "Готово"}
            ).status_code,
            403,
        )

    def test_no_direct_state_patch(self):
        self.assertEqual(
            self.client.patch(self.url(), {"status": "closed"}).status_code, 405
        )

    def test_overdue_and_filter(self):
        self.activate()
        self.t.due_at = self.now - timedelta(minutes=5)
        self.t.save()
        r = self.client.get("/api/tasks/overdue/", {"handover": self.h.pk})
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(
            self.client.get("/api/handovers/", {"status": "closed"}).data["count"], 0
        )

    def test_cats_owner_permissions_and_year(self):
        self.client.force_authenticate(self.stranger)
        self.assertEqual(
            self.client.patch(
                f"/api/cats/{self.cat.pk}/", {"name": "Чужой"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/cats/", {"name": "Кот", "color": "black", "birth_year": 2999}
            ).status_code,
            400,
        )

    def test_pagination_and_search(self):
        for n in range(11):
            CareTask.objects.create(
                handover=self.h, title=f"Проверка {n}", due_at=self.now
            )
        r = self.client.get("/api/tasks/", {"search": "Проверка"})
        self.assertEqual(r.data["count"], 11)
        self.assertEqual(len(r.data["results"]), 10)
        self.assertIsNotNone(r.data["next"])

    def test_event_log_read_only(self):
        self.assertEqual(self.client.post(self.url("events/"), {}).status_code, 405)

    def test_registration_and_token(self):
        self.client.force_authenticate(None)
        r = self.client.post(
            "/api/users/", {"username": "newuser", "password": "New-user-password-426!"}
        )
        self.assertEqual(r.status_code, 201)
        r = self.client.post(
            "/api/token/login/",
            {"username": "newuser", "password": "New-user-password-426!"},
        )
        self.assertEqual(r.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + r.data["auth_token"])
        self.assertEqual(self.client.get("/api/users/me/").status_code, 200)
        self.assertEqual(self.client.post("/api/token/logout/").status_code, 204)
        self.assertEqual(self.client.get("/api/users/me/").status_code, 401)

    def test_extend_and_resume_expired_shift(self):
        self.activate()
        self.h.ends_at = self.now - timedelta(minutes=1)
        self.h.save()
        r = self.client.post(
            self.url("extend/"),
            {
                "ends_at": (self.now + timedelta(days=2)).isoformat(),
                "reason": "Продлить уход",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.submit().status_code, 201)

    def test_extend_overlap_rejected(self):
        Handover.objects.create(
            cat=self.cat,
            owner=self.owner,
            sitter=self.sitter,
            starts_at=self.h.ends_at,
            ends_at=self.h.ends_at + timedelta(days=2),
        )
        self.assertEqual(
            self.client.post(
                self.url("extend/"),
                {
                    "ends_at": (self.h.ends_at + timedelta(days=1)).isoformat(),
                    "reason": "Дольше",
                },
            ).status_code,
            400,
        )

    def test_sitter_cannot_extend(self):
        self.client.force_authenticate(self.sitter)
        self.assertEqual(
            self.client.post(
                self.url("extend/"),
                {
                    "ends_at": (self.h.ends_at + timedelta(days=1)).isoformat(),
                    "reason": "Дольше",
                },
            ).status_code,
            403,
        )

    def test_cancel_requires_reason(self):
        self.assertEqual(self.client.post(self.url("cancel/"), {}).status_code, 400)
        self.assertEqual(
            self.client.post(
                self.url("cancel/"), {"reason": "Поездка отменена"}
            ).status_code,
            200,
        )
        self.client.force_authenticate(self.sitter)
        self.assertEqual(self.client.post(self.url("accept/")).status_code, 400)

    def test_closed_shift_cannot_extend(self):
        self.h.status = "closed"
        self.h.save()
        self.assertEqual(
            self.client.post(
                self.url("extend/"),
                {
                    "ends_at": (self.h.ends_at + timedelta(days=1)).isoformat(),
                    "reason": "Дольше",
                },
            ).status_code,
            400,
        )
