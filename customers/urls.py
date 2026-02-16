from django.urls import path
from .views import TenantUsersListView, RemoveUserFromTenantView, UpdateUserRoleView
from .orchestration_views import (
    DashboardMetricsView,
    TriggerDashboardAggregationView,
    DeleteAccountView,
    DeleteAccountWarningView,
)
from .invitation_views import (
    SendInvitationView,
    ValidateInvitationView,
    AcceptInvitationView,
    ListInvitationsView,
    CancelInvitationView,
    ResendInvitationView,
)

urlpatterns = [
    # User management (OWNER only)
    path("users/", TenantUsersListView.as_view(), name="tenant-users-list"),
    path("users/<int:user_id>/remove/", RemoveUserFromTenantView.as_view(), name="remove-user"),
    path("users/<int:user_id>/role/", UpdateUserRoleView.as_view(), name="update-user-role"),
    
    # Invitation system (uses Keycloak for email)
    path("invitations/", SendInvitationView.as_view(), name="send-invitation"),
    path("invitations/list/", ListInvitationsView.as_view(), name="list-invitations"),
    path("invitations/<uuid:token>/", ValidateInvitationView.as_view(), name="validate-invitation"),
    path("invitations/<uuid:token>/accept/", AcceptInvitationView.as_view(), name="accept-invitation"),
    path("invitations/<uuid:token>/cancel/", CancelInvitationView.as_view(), name="cancel-invitation"),
    path("invitations/<uuid:token>/resend/", ResendInvitationView.as_view(), name="resend-invitation"),
    
    # Orchestration endpoints
    path("metrics/dashboard/", DashboardMetricsView.as_view(), name="dashboard-metrics"),
    path("orchestration/aggregate-dashboard/", TriggerDashboardAggregationView.as_view(), name="trigger-aggregation"),
    path("account/delete-warning/", DeleteAccountWarningView.as_view(), name="delete-warning"),
    path("account/delete/", DeleteAccountView.as_view(), name="delete-account"),
]
