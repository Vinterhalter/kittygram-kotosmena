from djoser.views import TokenDestroyView
from drf_spectacular.utils import extend_schema


class LogoutView(TokenDestroyView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        return super().post(request)
