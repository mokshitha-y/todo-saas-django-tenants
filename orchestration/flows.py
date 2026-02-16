import os
import django
from prefect import flow, task, get_run_logger
from prefect.context import get_run_context
from datetime import datetime
from typing import Optional

# Setup Django configuration
# This must be done before importing any Django models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "todo_saas.settings")
django.setup()

from django.db import transaction, connection
from django.utils import timezone
from django_tenants.utils import schema_context, get_tenant_model
from users.models import User
from todos.models import Todo
from customers.models import (
    Client,
    TenantUser,
    RolesMap,
    Organization,
    SystemAuditLog,
    Invitation,
    EmailConfiguration,
)
from customers.services import KeycloakService
from todo_saas.utils.keycloak_admin import get_keycloak_admin_client

Client = get_tenant_model()


# ============================================
# HELPER: GET PREFECT FLOW RUN ID
# ============================================

def get_flow_run_id() -> Optional[str]:
    """Get current Prefect flow run ID if available."""
    try:
        ctx = get_run_context()
        if ctx and ctx.flow_run:
            return str(ctx.flow_run.id)
    except Exception:
        pass
    return None


# ============================================
# HELPER: LOG TO SYSTEM AUDIT (PUBLIC SCHEMA)
# ============================================

def log_to_system_audit(
    operation: str,
    tenant_name: str,
    schema_name: str = None,
    status: str = "STARTED",
    triggered_by: str = "system",
    details: dict = None,
    error_message: str = None,
    started_at: datetime = None,
    completed_at: datetime = None,
) -> SystemAuditLog:
    """
    Create or update a SystemAuditLog entry in public schema.
    Used for destructive operations that survive tenant deletion.
    """
    with schema_context("public"):
        log = SystemAuditLog.objects.create(
            operation=operation,
            tenant_name=tenant_name,
            schema_name=schema_name,
            status=status,
            triggered_by=triggered_by,
            flow_run_id=get_flow_run_id(),
            details=details,
            error_message=error_message,
            started_at=started_at or timezone.now(),
            completed_at=completed_at,
        )
        return log


def update_system_audit(
    log_id: int,
    status: str,
    details: dict = None,
    error_message: str = None,
):
    """Update an existing SystemAuditLog entry."""
    with schema_context("public"):
        SystemAuditLog.objects.filter(id=log_id).update(
            status=status,
            details=details,
            error_message=error_message,
            completed_at=timezone.now(),
        )


# ============================================
# HELPER: LOG TO ORCHESTRATION LOG (TENANT SCHEMA)
# ============================================

def log_to_tenant(
    schema_name: str,
    flow_name: str,
    status: str = "STARTED",
    triggered_by: str = "system",
    details: dict = None,
    error_message: str = None,
    started_at: datetime = None,
    completed_at: datetime = None,
) -> int:
    """
    Create OrchestrationLog entry in tenant schema.
    Returns the log ID for later updates.
    """
    from report.models import OrchestrationLog
    
    try:
        with schema_context(schema_name):
            log = OrchestrationLog.objects.create(
                flow_name=flow_name,
                status=status,
                flow_run_id=get_flow_run_id(),
                triggered_by=triggered_by,
                details=details,
                error_message=error_message,
                started_at=started_at or timezone.now(),
                completed_at=completed_at,
            )
            return log.id
    except Exception:
        return None


def update_tenant_log(
    schema_name: str,
    log_id: int,
    status: str,
    details: dict = None,
    error_message: str = None,
):
    """Update an existing OrchestrationLog entry in tenant schema."""
    from report.models import OrchestrationLog
    
    try:
        with schema_context(schema_name):
            OrchestrationLog.objects.filter(id=log_id).update(
                status=status,
                details=details,
                error_message=error_message,
                completed_at=timezone.now(),
            )
    except Exception:
        pass


# ============================================
# TASK 1: DASHBOARD AGGREGATION
# ============================================

@task(retries=1)
def fetch_tenant_metrics(schema_name: str):
    """
    Fetch aggregated metrics for a tenant schema.
    
    Returns:
        dict: Metrics including todo counts by status and user count
    """
    logger = get_run_logger()
    
    try:
        with schema_context(schema_name):
            metrics = {
                "schema_name": schema_name,
                "new_todos": Todo.objects.filter(is_completed=False, is_deleted=False).count(),
                "completed_todos": Todo.objects.filter(is_completed=True, is_deleted=False).count(),
                "deleted_todos": Todo.objects.filter(is_deleted=True).count(),
                "total_todos": Todo.objects.filter(is_deleted=False).count(),
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            logger.info(f"Fetched metrics for {schema_name}: {metrics}")
            return metrics
    except Exception as e:
        logger.warning(f"Failed to fetch metrics for {schema_name}: {e} — returning zeros")
        # Return zero metrics instead of failing (handles stale/dropped schemas)
        return {
            "schema_name": schema_name,
            "new_todos": 0,
            "completed_todos": 0,
            "deleted_todos": 0,
            "total_todos": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }


@task(retries=2)
def count_invited_users(tenant_id: int):
    """
    Count invited/invited users for a tenant in the public schema.
    
    Returns:
        dict: User count and details
    """
    logger = get_run_logger()
    
    try:
        tenant = Client.objects.get(id=tenant_id)
        user_count = TenantUser.objects.filter(tenant=tenant).count()
        
        owner_count = TenantUser.objects.filter(tenant=tenant, role="OWNER").count()
        member_count = TenantUser.objects.filter(tenant=tenant, role="MEMBER").count()
        viewer_count = TenantUser.objects.filter(tenant=tenant, role="VIEWER").count()
        
        result = {
            "tenant_id": tenant_id,
            "tenant_name": tenant.name,
            "total_users": user_count,
            "owners": owner_count,
            "members": member_count,
            "viewers": viewer_count,
        }
        
        logger.info(f"Counted users for {tenant.name}: {result}")
        return result
    except Client.DoesNotExist:
        logger.warning(f"Tenant {tenant_id} not found — returning zeros")
        return {
            "tenant_id": tenant_id,
            "tenant_name": "unknown",
            "total_users": 0,
            "owners": 0,
            "members": 0,
            "viewers": 0,
        }
    except Exception as e:
        logger.error(f"Failed to count users for tenant {tenant_id}: {e}")
        raise


@task(retries=2)
def store_dashboard_metrics(metrics_list: list):
    """
    Store aggregated metrics in each tenant's schema.
    
    Args:
        metrics_list: List of metric dicts from all tenants
    """
    logger = get_run_logger()
    
    try:
        from report.models import DashboardMetrics
        
        stored_count = 0
        for metrics in metrics_list:
            schema_name = metrics.get("schema_name")
            if not schema_name or schema_name == "public":
                continue
            
            try:
                with schema_context(schema_name):
                    # Upsert: delete old, insert new (single row per tenant)
                    DashboardMetrics.objects.all().delete()
                    
                    DashboardMetrics.objects.create(
                        todos_new=metrics.get("new_todos", 0),
                        todos_completed=metrics.get("completed_todos", 0),
                        todos_deleted=metrics.get("deleted_todos", 0),
                        total_todos=metrics.get("total_todos", 0),
                        total_users=metrics.get("total_users", 0),
                    )
                    stored_count += 1
            except Exception as e:
                logger.warning(f"Failed to store metrics for {schema_name}: {e}")
        
        logger.info(f"Stored metrics in {stored_count} tenant schema(s)")
        return stored_count
    except Exception as e:
        logger.error(f"Failed to store dashboard metrics: {e}", exc_info=True)
        raise


@flow(name="Dashboard Aggregation")
def dashboard_aggregation_flow(triggered_by: str = "system"):
    """
    Aggregate dashboard metrics across all tenants.

    Tracked as a Prefect flow run — visible in Prefect dashboard.
    Called directly by API (manual) and by scheduled deployment (automated).

    Execution steps:
    1. Iterate through all active tenants
    2. Fetch metrics for each tenant schema
    3. Count invited users per tenant
    4. Store results in DashboardMetrics table (per-tenant)
    5. Log to OrchestrationLog in each tenant schema
    """
    logger = get_run_logger()
    logger.info("Starting dashboard aggregation flow")
    
    start_time = timezone.now()
    tenant_logs = {}  # schema_name -> log_id

    try:
        with schema_context("public"):
            active_tenants = list(Client.objects.filter(on_trial=True))
        
        # Log start in each tenant's OrchestrationLog
        for tenant in active_tenants:
            log_id = log_to_tenant(
                schema_name=tenant.schema_name,
                flow_name="DASHBOARD_AGGREGATION",
                status="STARTED",
                triggered_by=triggered_by,
                started_at=start_time,
            )
            tenant_logs[tenant.schema_name] = log_id

        # Fetch schema metrics (sequential — works both direct-call and worker)
        metrics_list = []
        for tenant in active_tenants:
            metrics = fetch_tenant_metrics(tenant.schema_name)
            metrics_list.append(metrics)

        # Count users per tenant
        user_counts = []
        for tenant in active_tenants:
            counts = count_invited_users(tenant.id)
            user_counts.append(counts)

        # Merge user counts into metrics
        user_count_map = {uc["tenant_id"]: uc for uc in user_counts}
        for metrics in metrics_list:
            for tenant in active_tenants:
                if tenant.schema_name == metrics["schema_name"]:
                    uc = user_count_map.get(tenant.id, {})
                    metrics["total_users"] = uc.get("total_users", 0)
                    break

        # Store all metrics
        store_dashboard_metrics(metrics_list)
        
        # Update logs in each tenant
        for tenant in active_tenants:
            log_id = tenant_logs.get(tenant.schema_name)
            if log_id:
                # Find this tenant's metrics
                tenant_metrics = next(
                    (m for m in metrics_list if m["schema_name"] == tenant.schema_name),
                    {}
                )
                update_tenant_log(
                    schema_name=tenant.schema_name,
                    log_id=log_id,
                    status="COMPLETED",
                    details={
                        "todos_new": tenant_metrics.get("new_todos", 0),
                        "todos_completed": tenant_metrics.get("completed_todos", 0),
                        "total_users": tenant_metrics.get("total_users", 0),
                    },
                )

        logger.info(
            f"Dashboard aggregation completed: "
            f"processed {len(metrics_list)} tenants, "
            f"counted users for {len(user_counts)} tenants"
        )

        return {
            "success": True,
            "tenants_processed": len(metrics_list),
            "user_counts": user_counts,
            "message": f"Successfully aggregated metrics for {len(metrics_list)} tenant(s)",
        }

    except Exception as e:
        logger.error(f"Dashboard aggregation flow failed: {e}")
        # Update logs as failed
        for schema_name, log_id in tenant_logs.items():
            if log_id:
                update_tenant_log(
                    schema_name=schema_name,
                    log_id=log_id,
                    status="FAILED",
                    error_message=str(e),
                )
        raise


# ============================================
# TASK 2: ACCOUNT DELETION & CLEANUP
# ============================================

@task(retries=1)
def delete_tenant_schema(schema_name: str):
    """
    Drop the tenant's PostgreSQL schema.
    
    CAUTION: This is destructive and cannot be undone.
    """
    logger = get_run_logger()
    
    try:
        from psycopg2 import sql as psql

        with connection.cursor() as cursor:
            # Check if schema exists
            cursor.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name = %s",
                [schema_name]
            )
            
            if cursor.fetchone():
                # Use sql.Identifier to safely quote the schema name
                cursor.execute(
                    psql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        psql.Identifier(schema_name)
                    )
                )
                logger.info(f"Dropped schema: {schema_name}")
            else:
                logger.warning(f"Schema {schema_name} does not exist")
        
        return True
    except Exception as e:
        logger.error(f"Failed to drop schema {schema_name}: {e}")
        raise


@task(retries=2)
def delete_local_tenant_data(tenant_id: int):
    """
    Delete all tenant metadata from public schema for this org: TenantUser,
    RolesMap, Invitation, EmailConfiguration, Client, Organization.
    Returns the list of orphaned user IDs.

    Orphan users are NOT deleted here because the tenant schema (which contains
    todos_todo with FK constraints to users_user) must be dropped first.
    
    Also identifies globally orphaned disabled users (users who were previously
    removed from tenants and have is_active=False with 0 memberships).
    """
    logger = get_run_logger()

    try:
        from django.db.models import Count

        with schema_context("public"):
            with transaction.atomic():
                tenant = Client.objects.get(id=tenant_id)
                schema_name = tenant.schema_name
                organization = tenant.organization

                # Capture user ids that are associated with this tenant so we can
                # determine which become orphans after we remove TenantUser rows.
                associated_user_ids = list(
                    TenantUser.objects.filter(tenant=tenant).values_list("user_id", flat=True)
                )

                # Delete all tenant-related data (order matters: dependents first)
                TenantUser.objects.filter(tenant=tenant).delete()
                RolesMap.objects.filter(tenant=tenant).delete()
                Invitation.objects.filter(tenant=tenant).delete()
                EmailConfiguration.objects.filter(tenant=tenant).delete()

                # Delete tenant (Client) then organization
                tenant.delete()
                if organization:
                    organization.delete()

                # Identify orphan users from THIS tenant (no remaining tenant memberships)
                new_orphan_ids = list(
                    User.objects.filter(id__in=associated_user_ids)
                    .annotate(tenant_count=Count("tenant_memberships"))
                    .filter(tenant_count=0)
                    .values_list("id", flat=True)
                )

                # Also find globally orphaned disabled users (previously removed members
                # who have is_active=False and 0 tenant memberships anywhere)
                stale_orphan_ids = list(
                    User.objects.filter(is_active=False)
                    .annotate(tenant_count=Count("tenant_memberships"))
                    .filter(tenant_count=0)
                    .values_list("id", flat=True)
                )

                # Combine both lists (deduplicated)
                all_orphan_ids = list(set(new_orphan_ids) | set(stale_orphan_ids))

                logger.info(
                    f"Deleted local tenant data for {schema_name} (ID: {tenant_id}), "
                    f"new_orphans={new_orphan_ids}, stale_orphans={stale_orphan_ids}, "
                    f"total_orphans={len(all_orphan_ids)}"
                )

        return {"schema_name": schema_name, "orphan_user_ids": all_orphan_ids}
    except Exception as e:
        logger.error(f"Failed to delete local tenant data for {tenant_id}: {e}")
        raise


@task(retries=2)
def delete_orphan_users(orphan_user_ids: list):
    """
    Delete orphan users from users_user using raw SQL.

    IMPORTANT: This must run AFTER the tenant schema is dropped, because
    tenant-scoped tables (todos_todo) have FK constraints pointing to
    users_user. Dropping the schema removes those constraints first.
    """
    logger = get_run_logger()

    if not orphan_user_ids:
        return 0

    try:
        with connection.cursor() as cursor:
            placeholders = ",".join(["%s"] * len(orphan_user_ids))
            cursor.execute(
                f"DELETE FROM users_user WHERE id IN ({placeholders})",
                orphan_user_ids,
            )
            deleted_count = cursor.rowcount
        logger.info(f"Deleted {deleted_count} orphan local user(s): {orphan_user_ids}")
        return deleted_count
    except Exception as e:
        logger.error(f"Failed to delete orphan users {orphan_user_ids}: {e}")
        raise


@task(retries=1)
def delete_stale_orphan_keycloak_users(orphan_user_ids: list):
    """
    Delete stale orphan users from Keycloak.
    
    These are users who were previously removed from tenants (disabled) and
    are now being permanently deleted. They weren't in the current tenant's
    TenantUser list, so we need to look them up by ID and delete from KC.
    """
    logger = get_run_logger()

    if not orphan_user_ids:
        return 0

    deleted_count = 0
    try:
        kc = get_keycloak_admin_client()
        
        with schema_context("public"):
            orphan_users = User.objects.filter(id__in=orphan_user_ids, keycloak_id__isnull=False)
            
            for user in orphan_users:
                try:
                    kc.delete_user(user.keycloak_id)
                    deleted_count += 1
                    logger.info(f"Deleted stale orphan from Keycloak: {user.username} ({user.keycloak_id})")
                except Exception as e:
                    # User may already be deleted from Keycloak, continue
                    logger.warning(f"Failed to delete {user.username} from Keycloak: {e}")
        
        logger.info(f"Deleted {deleted_count} stale orphan users from Keycloak")
        return deleted_count
    except Exception as e:
        logger.error(f"Failed to delete stale orphan Keycloak users: {e}")
        # Don't fail the flow, just log the error
        return deleted_count


@task(retries=1)
def cleanup_keycloak_user(
    keycloak_id: str,
    org_name: str = None,
    client_id: str = None,
    role_name: str = None,
    group_id: str = None,
    permanent_delete: bool = False,
):
    """
    Clean up a single Keycloak user:
    - Revoke tokens
    - Remove from org, client role, group
    - Disable OR permanently delete depending on flag
    """
    logger = get_run_logger()

    try:
        kc = get_keycloak_admin_client()

        # 1. Revoke all sessions
        kc.revoke_user_tokens(keycloak_id)

        # 2. Remove from org members
        if org_name:
            kc.remove_user_from_organization(keycloak_id, org_name)

        # 3. Remove client role
        if client_id and role_name:
            kc.remove_client_role(keycloak_id, client_id, role_name)

        # 4. Remove from group
        if group_id:
            try:
                kc.client.group_user_remove(keycloak_id, group_id)
            except Exception:
                pass

        # 5. Disable or permanently delete
        if permanent_delete:
            kc.delete_user(keycloak_id)
            logger.info(f"Permanently deleted Keycloak user: {keycloak_id}")
        else:
            kc.disable_user(keycloak_id)
            logger.info(f"Disabled Keycloak user: {keycloak_id}")

        return True
    except Exception as e:
        logger.warning(f"Failed to cleanup Keycloak user {keycloak_id}: {e}")
        return False


@task(retries=1)
def delete_keycloak_client(keycloak_id: str):
    """
    Delete Keycloak client (OAuth2 app).
    """
    logger = get_run_logger()
    
    try:
        kc_client = get_keycloak_admin_client()
        res = kc_client.delete_client(keycloak_id)
        if res:
            logger.info(f"Deleted Keycloak client: {keycloak_id}")
        else:
            logger.warning(f"Delete client API returned False for {keycloak_id}")
        return res
    except Exception as e:
        logger.warning(f"Failed to delete Keycloak client {keycloak_id}: {e}")
        # Don't fail the whole flow if Keycloak deletion fails
        return False


@task(retries=1)
def delete_keycloak_group(group_id: str):
    """
    Delete Keycloak group (tenant group).
    """
    logger = get_run_logger()
    if not group_id:
        logger.info("No group_id provided, skipping group deletion")
        return False
    try:
        kc_client = get_keycloak_admin_client()
        res = kc_client.delete_group(group_id)
        if res:
            logger.info(f"Deleted Keycloak group: {group_id}")
        else:
            logger.warning(f"Delete group API returned False for {group_id}")
        return res
    except Exception as e:
        logger.warning(f"Failed to delete Keycloak group {group_id}: {e}")
        return False


@task(retries=1)
def delete_keycloak_organization(org_name: str):
    """
    Delete Keycloak organization by name.
    """
    logger = get_run_logger()
    try:
        kc_client = get_keycloak_admin_client()
        res = kc_client.delete_organization_by_name(org_name)
        if res:
            logger.info(f"Deleted Keycloak organization: {org_name}")
        else:
            logger.warning(f"Delete organization returned False for {org_name}")
        return res
    except Exception as e:
        logger.warning(f"Failed to delete Keycloak organization {org_name}: {e}")
        return False


@task(retries=1)
def cleanup_tenant_invitations(tenant_id: int):
    """
    Cancel all pending invitations for a tenant and clean up KC users
    created by those invitations who have no other tenant memberships.
    
    Returns dict with counts and details.
    """
    logger = get_run_logger()
    
    try:
        with schema_context("public"):
            # Get all invitations for this tenant
            invitations = Invitation.objects.filter(tenant_id=tenant_id)
            total_invitations = invitations.count()
            pending_count = invitations.filter(status="PENDING").count()
            
            # Cancel all pending invitations
            cancelled = invitations.filter(status="PENDING").update(status="CANCELLED")
            
            logger.info(
                f"Invitation cleanup: total={total_invitations}, "
                f"pending_cancelled={cancelled}"
            )
            
            return {
                "total_invitations": total_invitations,
                "pending_cancelled": cancelled,
            }
    except Exception as e:
        logger.warning(f"Failed to cleanup invitations for tenant {tenant_id}: {e}")
        return {"total_invitations": 0, "pending_cancelled": 0}

@flow(name="Account Deletion")
def account_deletion_flow(tenant_id: int, triggered_by: str = "system"):
    """
    Orchestrate end-to-end PERMANENT deletion of a tenant account.

    When the owner clicks "Delete account", everything for that org is dropped:
    - Schema: PostgreSQL tenant schema (DROP SCHEMA ... CASCADE) — all tenant
      tables (todos, etc.) are removed.
    - Org: Keycloak organisation and Django Organization record.
    - Client: Keycloak client (OAuth2 app) and Django Client (tenant) record.
    - Users: Keycloak users in that org (permanently deleted if no other
      tenant); Django TenantUser/RolesMap/Invitation/EmailConfiguration;
      orphan Django users removed after schema drop.

    Also: Keycloak group, cancelled invitations, and stale orphan users.

    Tracked as a Prefect flow run — visible in Prefect dashboard.
    Logs to SystemAuditLog (public schema) - survives tenant deletion.
    """
    logger = get_run_logger()
    logger.info(f"Starting account deletion flow for tenant {tenant_id}")
    
    start_time = timezone.now()
    audit_log = None
    schema_name = None
    org_name = None

    try:
        # =====================
        # STEP 1: FETCH ALL DATA (tenant, users, invitations)
        # =====================
        with schema_context("public"):
            tenant = Client.objects.get(id=tenant_id)
            schema_name = tenant.schema_name
            org_name = tenant.name
            keycloak_group_id = tenant.keycloak_group_id
            keycloak_client_id = tenant.keycloak_client_id

            # ALL users in this tenant (owner + all invited members)
            tenant_user_objs = list(
                TenantUser.objects.filter(tenant=tenant).select_related("user")
            )

            # Count invitations for audit
            invitation_count = Invitation.objects.filter(tenant=tenant).count()
            pending_invitation_count = Invitation.objects.filter(
                tenant=tenant, status="PENDING"
            ).count()
        
        # Log start to SystemAuditLog (public)
        audit_log = log_to_system_audit(
            operation="TENANT_DELETED",
            tenant_name=org_name,
            schema_name=schema_name,
            status="STARTED",
            triggered_by=triggered_by,
            details={
                "user_count": len(tenant_user_objs),
                "invitation_count": invitation_count,
                "pending_invitations": pending_invitation_count,
            },
            started_at=start_time,
        )

        logger.info(
            f"Tenant data: schema={schema_name}, org={org_name}, "
            f"client_id={keycloak_client_id}, group_id={keycloak_group_id}, "
            f"users={len(tenant_user_objs)}, invitations={invitation_count}"
        )

        # =====================
        # STEP 2: KEYCLOAK USER CLEANUP (owner + ALL invited members)
        # Every user in this tenant gets cleaned up from KC:
        # - Tokens revoked
        # - Removed from KC org, client role, group
        # - Permanently DELETED from KC if they have no other tenants
        # - Just cleaned up (not deleted) if they belong to other tenants
        # =====================
        deleted_users = []
        kept_users = []

        logger.info(
            f"Cleaning up {len(tenant_user_objs)} KC users "
            f"(owner + all invited members)"
        )

        for tu in tenant_user_objs:
            user = tu.user
            if not user.keycloak_id:
                logger.warning(f"User {user.username} has no keycloak_id, skipping KC cleanup")
                deleted_users.append(user.username)  # Still count as deleted locally
                continue

            other_tenants = TenantUser.objects.filter(
                user=user
            ).exclude(tenant_id=tenant_id).count()

            is_orphan = other_tenants == 0

            cleanup_keycloak_user(
                keycloak_id=user.keycloak_id,
                org_name=org_name,
                client_id=keycloak_client_id,
                role_name=tu.role,
                group_id=keycloak_group_id,
                permanent_delete=is_orphan,
            )

            if is_orphan:
                deleted_users.append(user.username)
            else:
                kept_users.append(user.username)

        logger.info(
            f"KC user cleanup done: "
            f"permanently_deleted={deleted_users}, "
            f"cleaned_up_kept={kept_users}"
        )

        # =====================
        # STEP 3: CANCEL ALL INVITATIONS
        # Cancel pending invitations so they cannot be used after deletion.
        # Invitation records will be cascade-deleted when Client is deleted.
        # =====================
        invitation_result = cleanup_tenant_invitations(tenant_id)

        # =====================
        # STEP 4: DELETE KC GROUP / CLIENT / ORG
        # Remove all Keycloak resources for this tenant
        # =====================
        if keycloak_group_id:
            delete_keycloak_group(keycloak_group_id)

        if keycloak_client_id:
            delete_keycloak_client(keycloak_client_id)

        if org_name:
            delete_keycloak_organization(org_name)

        # =====================
        # STEP 5: DELETE DJANGO DATA (Client, TenantUser, Organization, Invitations)
        # Invitations cascade-delete via FK to Client.
        # Returns orphan_user_ids for cleanup after schema drop.
        # =====================
        local_result = delete_local_tenant_data(tenant_id)
        orphan_user_ids = local_result.get("orphan_user_ids", [])

        # =====================
        # STEP 6: DROP SCHEMA
        # Must happen BEFORE deleting orphan users because tenant-scoped
        # tables (todos_todo) have FK constraints to users_user.
        # Dropping the schema removes those constraints.
        # =====================
        delete_tenant_schema(schema_name)

        # =====================
        # STEP 7: DELETE ORPHAN USERS FROM KEYCLOAK
        # Delete stale orphan users from Keycloak (they weren't in tenant_user_objs
        # because they were previously removed/disabled)
        # =====================
        stale_kc_deleted = delete_stale_orphan_keycloak_users(orphan_user_ids)

        # =====================
        # STEP 8: DELETE ORPHAN USERS FROM DATABASE (safe now that schema is gone)
        # =====================
        delete_orphan_users(orphan_user_ids)
        
        # =====================
        # STEP 9: UPDATE AUDIT LOG
        # =====================
        if audit_log:
            update_system_audit(
                log_id=audit_log.id,
                status="COMPLETED",
                details={
                    "users_deleted": deleted_users,
                    "users_kept": kept_users,
                    "orphan_users_deleted": len(orphan_user_ids),
                    "stale_kc_users_deleted": stale_kc_deleted,
                    "invitations_cancelled": invitation_result.get("pending_cancelled", 0),
                    "total_invitations_deleted": invitation_result.get("total_invitations", 0),
                },
            )

        logger.info(f"Account deletion COMPLETED for tenant {tenant_id} ({schema_name})")

        return {
            "success": True,
            "tenant_id": tenant_id,
            "schema_name": schema_name,
            "deleted_users": deleted_users,
            "kept_users": kept_users,
            "status": "deleted",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Account deletion flow FAILED for tenant {tenant_id}: {e}")
        # Update audit log as failed
        if audit_log:
            update_system_audit(
                log_id=audit_log.id,
                status="FAILED",
                error_message=str(e),
            )
        raise


# ============================================
# RECURRING TODO SCHEDULING (Job C)
# ============================================

@task(retries=2)
def find_recurring_todos(schema_name: str):
    """
    Find all recurring todos that need new instances created.
    
    A recurring todo needs a new instance when:
    - recurrence_type is not NONE
    - is_completed = True (the current instance is done)
    - is_deleted = False
    """
    logger = get_run_logger()
    
    try:
        with schema_context(schema_name):
            recurring_todos = Todo.objects.filter(
                recurrence_type__in=["DAILY", "WEEKLY", "MONTHLY"],
                is_completed=True,
                is_deleted=False,
            )
            
            result = []
            for todo in recurring_todos:
                result.append({
                    "id": todo.id,
                    "title": todo.title,
                    "description": todo.description,
                    "recurrence_type": todo.recurrence_type,
                    "due_date": todo.due_date.isoformat() if todo.due_date else None,
                    "created_by_id": todo.created_by_id,
                    "assigned_to_id": todo.assigned_to_id,
                })
            
            logger.info(f"Found {len(result)} recurring todos to process in {schema_name}")
            return result
    except Exception as e:
        logger.warning(f"Failed to find recurring todos in {schema_name}: {e} — skipping")
        return []


@task(retries=2)
def create_recurring_instance(schema_name: str, todo_data: dict):
    """
    Create a new instance of a recurring todo with updated due date.
    """
    from datetime import timedelta
    from django.utils import timezone
    
    logger = get_run_logger()
    
    try:
        with schema_context(schema_name):
            original_todo = Todo.objects.get(id=todo_data["id"])
            
            # Calculate new due date based on recurrence type
            if original_todo.due_date:
                if todo_data["recurrence_type"] == "DAILY":
                    new_due_date = original_todo.due_date + timedelta(days=1)
                elif todo_data["recurrence_type"] == "WEEKLY":
                    new_due_date = original_todo.due_date + timedelta(weeks=1)
                elif todo_data["recurrence_type"] == "MONTHLY":
                    new_due_date = original_todo.due_date + timedelta(days=30)
                else:
                    new_due_date = None
            else:
                # If no due date, set based on current time
                now = timezone.now()
                if todo_data["recurrence_type"] == "DAILY":
                    new_due_date = now + timedelta(days=1)
                elif todo_data["recurrence_type"] == "WEEKLY":
                    new_due_date = now + timedelta(weeks=1)
                elif todo_data["recurrence_type"] == "MONTHLY":
                    new_due_date = now + timedelta(days=30)
                else:
                    new_due_date = None
            
            # Create new todo instance
            new_todo = Todo.objects.create(
                title=original_todo.title,
                description=original_todo.description,
                is_completed=False,
                is_deleted=False,
                due_date=new_due_date,
                recurrence_type=original_todo.recurrence_type,
                parent_todo=original_todo,
                created_by=original_todo.created_by,
                assigned_to=original_todo.assigned_to,
            )
            
            # Mark original as no longer recurring (so it doesn't spawn more)
            original_todo.recurrence_type = "NONE"
            original_todo.save()
            
            logger.info(f"Created recurring instance: {new_todo.id} from {original_todo.id}")
            
            return {
                "original_id": original_todo.id,
                "new_id": new_todo.id,
                "new_due_date": new_due_date.isoformat() if new_due_date else None,
            }
    except Exception as e:
        logger.warning(f"Failed to create recurring instance in {schema_name}: {e} — skipping")
        return None


@flow(name="Recurring Todo Processing")
def recurring_todo_flow(triggered_by: str = "system"):
    """
    Process recurring todos across all tenants.

    Tracked as a Prefect flow run — visible in Prefect dashboard.
    Called directly by API and by scheduled deployment.
    Logs to OrchestrationLog in each tenant schema.

    Execution steps:
    1. Iterate through all active tenants
    2. Find todos with recurrence settings that are completed
    3. Create new todo instances with updated due dates
    4. Log to each tenant's OrchestrationLog
    """
    logger = get_run_logger()
    
    start_time = timezone.now()
    tenant_logs = {}  # schema_name -> (log_id, todos_created)

    try:
        with schema_context("public"):
            active_tenants = list(Client.objects.filter(on_trial=True))
            tenant_list = [(t.id, t.schema_name) for t in active_tenants]

        logger.info(f"Processing recurring todos for {len(tenant_list)} tenant(s)")
        
        # Log start in each tenant
        for tenant_id, schema_name in tenant_list:
            log_id = log_to_tenant(
                schema_name=schema_name,
                flow_name="RECURRING_TODO",
                status="STARTED",
                triggered_by=triggered_by,
                started_at=start_time,
            )
            tenant_logs[schema_name] = {"log_id": log_id, "todos_created": 0}

        total_created = 0
        for tenant_id, schema_name in tenant_list:
            recurring_todos = find_recurring_todos(schema_name)
            tenant_created = 0

            for todo_data in recurring_todos:
                result = create_recurring_instance(schema_name, todo_data)
                if result is not None:
                    total_created += 1
                    tenant_created += 1
            
            tenant_logs[schema_name]["todos_created"] = tenant_created
        
        # Update logs in each tenant
        for schema_name, data in tenant_logs.items():
            if data["log_id"]:
                update_tenant_log(
                    schema_name=schema_name,
                    log_id=data["log_id"],
                    status="COMPLETED",
                    details={"todos_created": data["todos_created"]},
                )

        logger.info(f"Recurring todo processing complete. Created {total_created} new instances.")

        return {
            "success": True,
            "tenants_processed": len(tenant_list),
            "todos_created": total_created,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Created {total_created} recurring todo instances",
        }
    except Exception as e:
        logger.error(f"Recurring todo flow failed: {e}")
        # Update logs as failed
        for schema_name, data in tenant_logs.items():
            if data.get("log_id"):
                update_tenant_log(
                    schema_name=schema_name,
                    log_id=data["log_id"],
                    status="FAILED",
                    error_message=str(e),
                )
        raise

