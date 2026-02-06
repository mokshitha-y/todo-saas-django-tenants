from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    Session authentication without CSRF checks.
    Needed for API-based auth (JWT + React frontend).
    """

    def enforce_csrf(self, request):
        return  # Explicitly disable CSRF
