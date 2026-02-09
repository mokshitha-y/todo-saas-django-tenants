"""
RBAC utilities and permission decorators.
"""
from functools import wraps
from rest_framework import status
from rest_framework.response import Response
from django_tenants.utils import get_tenant_model
from customers.models import RolesMap, Role
import logging

logger = logging.getLogger(__name__)

Client = get_tenant_model()


def get_user_role_in_tenant(user, tenant):
    """
    Get the user's role in a specific tenant.
    
    Returns:
        str: Role name (OWNER, MEMBER, VIEWER) or None if user not in tenant
    """
    try:
        role_map = RolesMap.objects.select_related("role").get(
            user=user,
            tenant=tenant
        )
        return role_map.role.name
    except RolesMap.DoesNotExist:
        return None


def user_has_role(user, tenant, required_role):
    """
    Check if user has a specific role in a tenant.
    
    Args:
        user: Django user object
        tenant: Client (tenant) object
        required_role: Role name (str) or list of role names
    
    Returns:
        bool: True if user has the required role(s)
    """
    user_role = get_user_role_in_tenant(user, tenant)
    
    if not user_role:
        return False
    
    if isinstance(required_role, list):
        return user_role in required_role
    
    return user_role == required_role


def require_role(required_roles):
    """
    Decorator to require specific roles for API views.
    
    Usage:
        @require_role(['OWNER', 'MEMBER'])
        def my_view(request, *args, **kwargs):
            ...
    """
    if isinstance(required_roles, str):
        required_roles = [required_roles]
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get tenant from request (set by TenantFromTokenMiddleware)
            tenant = getattr(request, "tenant", None)
            
            if not tenant:
                return Response(
                    {"error": "No tenant context found"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not request.user or not request.user.is_authenticated:
                return Response(
                    {"error": "Authentication required"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            if not user_has_role(request.user, tenant, required_roles):
                logger.warning(
                    f"User {request.user.username} denied access to "
                    f"{view_func.__name__} - insufficient permissions"
                )
                return Response(
                    {"error": f"Access denied. Required roles: {', '.join(required_roles)}"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


def owner_only(view_func):
    """Decorator to restrict access to OWNER role only."""
    return require_role("OWNER")(view_func)


def member_or_higher(view_func):
    """Decorator to restrict access to MEMBER or OWNER."""
    return require_role(["MEMBER", "OWNER"])(view_func)


class RBACPermission:
    """
    Base permission class for DRF views with role-based access control.
    """
    
    required_roles = None  # Override in subclasses: ["OWNER"] or ["MEMBER", "OWNER"]
    
    @staticmethod
    def has_permission(request, view):
        """Check if request user has required role."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False
        
        # If no specific roles required, authenticated + in tenant is enough
        if not view.required_roles:
            return True
        
        return user_has_role(request.user, tenant, view.required_roles)


class OwnerOnly(RBACPermission):
    """Permission class: only OWNER role allowed."""
    
    def has_permission(self, request, view):
        if not self.has_permission(request, view):
            return False
        
        tenant = getattr(request, "tenant", None)
        return user_has_role(request.user, tenant, "OWNER")


class MemberOrHigher(RBACPermission):
    """Permission class: MEMBER or OWNER allowed."""
    
    def has_permission(self, request, view):
        if not self.has_permission(request, view):
            return False
        
        tenant = getattr(request, "tenant", None)
        return user_has_role(request.user, tenant, ["MEMBER", "OWNER"])
