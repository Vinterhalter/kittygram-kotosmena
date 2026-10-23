from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateEvidenceStorage(FileSystemStorage):
    """Resolve the private directory at runtime without freezing a machine path in migrations."""

    def __init__(self):
        super().__init__(location=settings.PRIVATE_MEDIA_ROOT)
