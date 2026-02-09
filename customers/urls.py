from django.urls import path
from .views import TenantUsersListView, RemoveUserFromTenantView, UpdateUserRoleView
from .orchestration_views import (
    DashboardMetricsView,
    TriggerDashboardAggregationView,
    DeleteAccountView,
    DeleteAccountWarningView,
)

urlpatterns = [
    # User management (OWNER only)
    path("users/", TenantUsersListView.as_view(), name="tenant-users-list"),
    path("users/<int:user_id>/remove/", RemoveUserFromTenantView.as_view(), name="remove-user"),
    path("users/<int:user_id>/role/", UpdateUserRoleView.as_view(), name="update-user-role"),
    
    # Orchestration endpoints
    path("metrics/dashboard/", DashboardMetricsView.as_view(), name="dashboard-metrics"),
    path("orchestration/aggregate-dashboard/", TriggerDashboardAggregationView.as_view(), name="trigger-aggregation"),
    path("account/delete-warning/", DeleteAccountWarningView.as_view(), name="delete-warning"),
    path("account/delete/", DeleteAccountView.as_view(), name="delete-account"),
]
