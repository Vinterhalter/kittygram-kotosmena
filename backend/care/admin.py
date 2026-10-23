from django.contrib import admin
from .models import Handover, CareTask, Completion, Incident, HandoverEvent


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for model in [Handover, CareTask, Completion, Incident, HandoverEvent]:
    admin.site.register(model, ReadOnlyAdmin)
