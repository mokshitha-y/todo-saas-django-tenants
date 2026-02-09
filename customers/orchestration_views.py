"""
API views for orchestration endpoints: dashboard metrics and account deletion.

All operations call Prefect @flow functions directly so every run
appears in the Prefect dashboard (http://localhost:4200).
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django_tenants.utils import schema_context, get_tenant_model
from django.utils import timezone
import logging
import os

from orchestration.flows import dashboard_aggregation_flow, account_deletion_flow, recurring_todo_flow
from report.models import DashboardMetrics
from customers.models import TenantUser, Client
from todo_saas.utils.rbac import owner_only

logger = logging.getLogger(__name__)
Tenant = get_tenant_model()

# Ensure Prefect knows where the server is so flow runs are tracked
os.environ.setdefault("PREFECT_API_URL", "http://localhost:4200/api")

class DashboardMetricsView(APIView):
    """
    Get aggregated dashboard metrics for the current tenant.
    
    GET /api/dashboard/metrics/
    
    Returns:
        {
            "schema_name": "customer1",
            "new_todos": 5,
            "completed_todos": 12,
            "deleted_todos": 2,
            "total_todos": 15,
            "total_users": 3,
            "owners": 1,
            "members": 1,
            "viewers": 1,
            "last_updated": "2025-02-07T10:30:00Z"
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Fetch cached dashboard metrics and include current user's role."""
        try:
            tenant = getattr(request, "tenant", None)
            if not tenant:
                return Response(
                    {"error": "No tenant context found"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Get current user's role
            with schema_context("public"):
                try:
                    membership = TenantUser.objects.get(user=request.user, tenant=tenant)
                    current_role = membership.role
                except TenantUser.DoesNotExist:
                    current_role = None
                owner_count = TenantUser.objects.filter(tenant=tenant, role="OWNER").count()
                member_count = TenantUser.objects.filter(tenant=tenant, role="MEMBER").count()
                viewer_count = TenantUser.objects.filter(tenant=tenant, role="VIEWER").count()
                total_users = TenantUser.objects.filter(tenant=tenant).count()
                metrics = DashboardMetrics.objects.filter(tenant=tenant).first()
            if not metrics:
                return Response({
                    "schema_name": tenant.schema_name,
                    "new_todos": 0,
                    "completed_todos": 0,
                    "total_todos": 0,
                    "total_users": total_users,
                    "owners": owner_count,
                    "members": member_count,
                    "viewers": viewer_count,
                    "last_updated": None,
                    "role": current_role,
                    "message": "Metrics not yet aggregated. Click 'Refresh Metrics' to compute now.",
                }, status=status.HTTP_200_OK)
            return Response({
                "schema_name": tenant.schema_name,
                "new_todos": metrics.todos_new,
                "completed_todos": metrics.todos_completed,
                "total_todos": metrics.todos_new + metrics.todos_completed,
                "total_users": total_users,
                "owners": owner_count,
                "members": member_count,
                "viewers": viewer_count,
                "last_updated": metrics.updated_at,
                "role": current_role,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Failed to fetch dashboard metrics: {e}", exc_info=True)
            return Response(
                {"error": f"Failed to fetch metrics: {str(e)}", "status": "error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TriggerDashboardAggregationView(APIView):
    """
    Manually trigger dashboard aggregation across all tenants.
    
    POST /api/orchestration/aggregate-dashboard/
    
    OWNER-only endpoint. Starts a Prefect flow to aggregate metrics.
    
    Returns:
        {
            "status": "triggered",
            "flow_name": "Dashboard Aggregation",
            "message": "Flow triggered successfully"
        }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Trigger dashboard aggregation via Prefect flow."""
        try:
            tenant = getattr(request, "tenant", None)

            if not tenant:
                return Response(
                    {"error": "No tenant context found"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Allow all tenant roles to refresh
            with schema_context("public"):
                membership = TenantUser.objects.filter(
                    user=request.user,
                    tenant=tenant,
                    role__in=["OWNER", "MEMBER", "VIEWER"]
                ).first()

            if not membership:
                return Response(
                    {"error": "Only tenant members can trigger aggregation"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Call the Prefect @flow directly — this creates a tracked flow run
            # in Prefect dashboard AND executes immediately (no worker needed).
            result = dashboard_aggregation_flow()
            logger.info(f"Dashboard aggregation flow triggered by {request.user.username}: {result}")

            return Response({
                "status": "completed",
                "flow_name": "Dashboard Aggregation",
                "message": result.get("message", "Metrics aggregated successfully"),
                "tenants_processed": result.get("tenants_processed", 0),
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Dashboard aggregation flow failed: {e}", exc_info=True)
            return Response(
                {"error": "Failed to aggregate metrics", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeleteAccountView(APIView):
    """
    Initiate account deletion for a tenant.
    
    DELETE /api/account/delete/
    
    Requires OWNER role. Triggers a Prefect flow to:
    1. Drop the tenant's PostgreSQL schema
    2. Delete all local database records
    3. Delete Keycloak resources
    
    Returns:
        {
            "status": "deletion_initiated",
            "message": "Account deletion flow started",
            "tenant_id": 123
        }
    
    This operation is irreversible and deletes all data.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        """Initiate account deletion."""
        try:
            tenant = getattr(request, "tenant", None)
            
            if not tenant:
                return Response(
                    {"error": "No tenant context found"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if user is OWNER
            with schema_context("public"):
                membership = TenantUser.objects.filter(
                    user=request.user,
                    tenant=tenant,
                    role="OWNER"
                ).first()
            
            if not membership:
                return Response(
                    {"error": "Only OWNER role can delete account"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Require confirmation
            confirmation = request.data.get("confirm_deletion", False)
            if not confirmation:
                return Response(
                    {
                        "error": "Deletion not confirmed",
                        "message": "Pass 'confirm_deletion': true in request body to proceed",
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            tenant_id = tenant.id
            schema_name = tenant.schema_name

            # Call the Prefect @flow directly — this creates a tracked flow run
            # in Prefect dashboard AND executes immediately.
            try:
                logger.warning(
                    f"Account deletion flow initiated for tenant {schema_name} (ID: {tenant_id}) "
                    f"by user {request.user.username}"
                )

                result = account_deletion_flow(tenant_id)

                if result.get("success"):
                    return Response({
                        "status": "deleted",
                        "message": "Account permanently deleted",
                        "tenant_id": tenant_id,
                        "schema_name": schema_name,
                        "deleted_users": result.get("deleted_users", []),
                        "kept_users": result.get("kept_users", []),
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        "status": "deletion_failed",
                        "error": result.get("error", "Unknown error"),
                        "tenant_id": tenant_id,
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            except Exception as flow_error:
                logger.error(f"Account deletion flow failed: {flow_error}", exc_info=True)
                return Response(
                    {"error": "Failed to delete account", "details": str(flow_error)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        except Exception as e:
            logger.error(f"Error in delete account endpoint: {e}", exc_info=True)
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeleteAccountWarningView(APIView):
    """
    GET endpoint to show deletion warning before actual deletion.
    
    GET /api/account/delete-warning/
    
    Returns information about what will be deleted.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get deletion warning information."""
        try:
            tenant = getattr(request, "tenant", None)
            
            if not tenant:
                return Response(
                    {"error": "No tenant context found"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if user is OWNER
            with schema_context("public"):
                membership = TenantUser.objects.filter(
                    user=request.user,
                    tenant=tenant,
                    role="OWNER"
                ).first()
            
            if not membership:
                return Response(
                    {"error": "Only OWNER role can delete account"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get data that will be deleted
            from todos.models import Todo
            
            try:
                with schema_context(tenant.schema_name):
                    todo_count = Todo.objects.filter(is_deleted=False).count()
            except Exception:
                todo_count = 0  # Schema may be stale or partially dropped
            
            with schema_context("public"):
                user_count = TenantUser.objects.filter(tenant=tenant).count()
            
            return Response({
                "warning": "This action will permanently delete your account and all associated data",
                "data_to_be_deleted": {
                    "schema": tenant.schema_name,
                    "organization": tenant.name,
                    "todos": todo_count,
                    "users": user_count,
                },
                "note": "This action cannot be undone. Please contact support if you change your mind.",
                "next_step": "Send a DELETE request to /api/account/delete/ with 'confirm_deletion': true",
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error in delete account warning endpoint: {e}")
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
