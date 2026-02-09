import os
import django
from prefect import flow, task, get_run_logger
from datetime import datetime

# Setup Django configuration
# This must be done before importing any Django models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "todo_saas.settings")
django.setup()

from django.db import transaction, connection
from django_tenants.utils import schema_context, get_tenant_model
from users.models import User
from todos.models import Todo
from customers.models import Client, TenantUser, RolesMap, Organization
from customers.services import KeycloakService
from todo_saas.utils.keycloak_admin import get_keycloak_admin_client

Client = get_tenant_model()


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
    Store aggregated metrics in report table (public schema).
    
    Args:
        metrics_list: List of metric dicts from all tenants
    """
    logger = get_run_logger()
    
    try:
        from report.models import DashboardMetrics
        
        with schema_context("public"):
            for metrics in metrics_list:
                # Get the tenant object by schema_name
                try:
                    tenant = Client.objects.get(schema_name=metrics["schema_name"])
                except Client.DoesNotExist:
                    logger.warning(f"Tenant not found for schema: {metrics['schema_name']}")
                    continue
                
                # Upsert: delete old, insert new
                # DashboardMetrics uses: tenant, todos_new, todos_completed, total_users
                DashboardMetrics.objects.filter(tenant=tenant).delete()
                
                DashboardMetrics.objects.create(
                    tenant=tenant,
                    todos_new=metrics["new_todos"],
                    todos_completed=metrics["completed_todos"],
                    total_users=metrics.get("total_users", 0),  # Will be updated by Job A
                )
        
        logger.info(f"Stored {len(metrics_list)} metric records")
        return len(metrics_list)
    except Exception as e:
        logger.error(f"Failed to store dashboard metrics: {e}", exc_info=True)
        raise


@flow(name="Dashboard Aggregation")
def dashboard_aggregation_flow():
    """
    Aggregate dashboard metrics across all tenants.

    Tracked as a Prefect flow run — visible in Prefect dashboard.
    Called directly by API (manual) and by scheduled deployment (automated).

    Execution steps:
    1. Iterate through all active tenants
    2. Fetch metrics for each tenant schema
    3. Count invited users per tenant
    4. Store results in DashboardMetrics table
    """
    logger = get_run_logger()
    logger.info("Starting dashboard aggregation flow")

    try:
        with schema_context("public"):
            active_tenants = list(Client.objects.filter(on_trial=True))

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
    Delete tenant metadata from public schema (Client, TenantUser, RolesMap,
    Organization) and return the list of orphaned user IDs.

    Orphan users are NOT deleted here because the tenant schema (which contains
    todos_todo with FK constraints to users_user) must be dropped first.
    """
    logger = get_run_logger()

    try:
        from django.db.models import Count

        with schema_context("public"):
            with transaction.atomic():
                tenant = Client.objects.get(id=tenant_id)
                schema_name = tenant.schema_name

                # Capture user ids that are associated with this tenant so we can
                # determine which become orphans after we remove TenantUser rows.
                associated_user_ids = list(
                    TenantUser.objects.filter(tenant=tenant).values_list("user_id", flat=True)
                )

                # Delete related mappings
                TenantUser.objects.filter(tenant=tenant).delete()
                RolesMap.objects.filter(tenant=tenant).delete()

                # Delete organization
                if tenant.organization:
                    tenant.organization.delete()

                # Delete tenant itself
                tenant.delete()

                # Identify orphan users (no remaining tenant memberships)
                orphan_user_ids = list(
                    User.objects.filter(id__in=associated_user_ids)
                    .annotate(tenant_count=Count("tenant_memberships"))
                    .filter(tenant_count=0)
                    .values_list("id", flat=True)
                )

                logger.info(
                    f"Deleted local tenant data for {schema_name} (ID: {tenant_id}), "
                    f"orphan_user_ids={orphan_user_ids}"
                )

        return {"schema_name": schema_name, "orphan_user_ids": orphan_user_ids}
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

@flow(name="Account Deletion")
def account_deletion_flow(tenant_id: int):
    """
    Orchestrate end-to-end PERMANENT deletion of a tenant account.

    Tracked as a Prefect flow run — visible in Prefect dashboard.

    Execution steps:
    1. Fetch tenant and user data
    2. Clean up Keycloak users (permanent delete for orphans, cleanup for shared)
    3. Delete Keycloak group, client, organization
    4. Delete Django data (metrics, mappings, org, tenant)
    5. Drop PostgreSQL schema
    """
    logger = get_run_logger()
    logger.info(f"Starting account deletion flow for tenant {tenant_id}")

    try:
        # =====================
        # STEP 1: FETCH ALL DATA
        # =====================
        with schema_context("public"):
            tenant = Client.objects.get(id=tenant_id)
            schema_name = tenant.schema_name
            org_name = tenant.name
            keycloak_group_id = tenant.keycloak_group_id
            keycloak_client_id = tenant.keycloak_client_id

            tenant_user_objs = list(
                TenantUser.objects.filter(tenant=tenant).select_related("user")
            )

        logger.info(
            f"Tenant data: schema={schema_name}, org={org_name}, "
            f"client_id={keycloak_client_id}, group_id={keycloak_group_id}, "
            f"users={len(tenant_user_objs)}"
        )

        # =====================
        # STEP 2: KEYCLOAK USER CLEANUP
        # =====================
        deleted_users = []
        kept_users = []

        for tu in tenant_user_objs:
            user = tu.user
            if not user.keycloak_id:
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
            f"KC user cleanup done: deleted={deleted_users}, kept={kept_users}"
        )

        # =====================
        # STEP 3: DELETE KC GROUP / CLIENT / ORG
        # =====================
        if keycloak_group_id:
            delete_keycloak_group(keycloak_group_id)

        if keycloak_client_id:
            delete_keycloak_client(keycloak_client_id)

        if org_name:
            delete_keycloak_organization(org_name)

        # =====================
        # STEP 4: DELETE DJANGO DATA (Client, TenantUser, Organization)
        # Returns orphan_user_ids for cleanup after schema drop
        # =====================
        local_result = delete_local_tenant_data(tenant_id)
        orphan_user_ids = local_result.get("orphan_user_ids", [])

        # =====================
        # STEP 5: DROP SCHEMA
        # Must happen BEFORE deleting orphan users because tenant-scoped
        # tables (todos_todo) have FK constraints to users_user.
        # Dropping the schema removes those constraints.
        # =====================
        delete_tenant_schema(schema_name)

        # =====================
        # STEP 6: DELETE ORPHAN USERS (safe now that schema is gone)
        # =====================
        delete_orphan_users(orphan_user_ids)

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
def recurring_todo_flow():
    """
    Process recurring todos across all tenants.

    Tracked as a Prefect flow run — visible in Prefect dashboard.
    Called directly by API and by scheduled deployment.

    Execution steps:
    1. Iterate through all active tenants
    2. Find todos with recurrence settings that are completed
    3. Create new todo instances with updated due dates
    """
    logger = get_run_logger()

    try:
        with schema_context("public"):
            active_tenants = list(Client.objects.filter(on_trial=True))
            tenant_list = [(t.id, t.schema_name) for t in active_tenants]

        logger.info(f"Processing recurring todos for {len(tenant_list)} tenant(s)")

        total_created = 0
        for tenant_id, schema_name in tenant_list:
            recurring_todos = find_recurring_todos(schema_name)

            for todo_data in recurring_todos:
                result = create_recurring_instance(schema_name, todo_data)
                if result is not None:
                    total_created += 1

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
        raise

