from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from cats.models import Cat, Achievement
from care.models import Handover, CareTask, HandoverEvent


class Command(BaseCommand):
    help = "Создать демонстрационные аккаунты и черновик смены для локального показа."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        password = "Cat-care-2026-demo!"
        users = []
        for name in ("demo_owner", "demo_sitter"):
            user, created = User.objects.get_or_create(username=name)
            if created:
                user.set_password(password)
                user.save()
            elif not user.check_password(password):
                raise CommandError(
                    f"Логин {name} занят другим аккаунтом. Пароль не изменён."
                )
            users.append(user)
        owner, sitter = users
        cat, _ = Cat.objects.get_or_create(
            owner=owner, name="Персик", defaults={"color": "ginger", "birth_year": 2022}
        )
        achievement, _ = Achievement.objects.get_or_create(name="Освоил переноску")
        cat.achievements.add(achievement)
        if not cat.handovers.filter(status__in=["draft", "active"]).exists():
            now = timezone.now()
            h = Handover.objects.create(
                cat=cat,
                owner=owner,
                sitter=sitter,
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(days=2),
                instructions="Корм утром и вечером по 50 г. Свежая вода каждый день.",
            )
            HandoverEvent.objects.create(handover=h, actor=owner, kind="created")
            for title, hours, photo in [
                ("Заменить воду", 3, False),
                ("Вечернее кормление", 6, True),
            ]:
                task = CareTask.objects.create(
                    handover=h,
                    title=title,
                    due_at=now + timedelta(hours=hours),
                    photo_required=photo,
                )
                HandoverEvent.objects.create(
                    handover=h,
                    actor=owner,
                    kind="task_created",
                    detail={"task": task.pk},
                )
        self.stdout.write(
            self.style.SUCCESS(
                "Демо готово: demo_owner / demo_sitter. Пароль: Cat-care-2026-demo!"
            )
        )
