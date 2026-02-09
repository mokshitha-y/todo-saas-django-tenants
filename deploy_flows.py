#!/usr/bin/env python
"""
Deploy Prefect flows for the Todo SaaS platform.

This script registers all flows with the Prefect server and creates
deployments that can be triggered manually or scheduled.
"""
import os
import sys

# Setup Django before importing flows
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "todo_saas.settings")

import django
django.setup()

from prefect import serve
from prefect.client.schemas.schedules import CronSchedule, IntervalSchedule
from datetime import timedelta

# Import flows
from orchestration.flows import (
    dashboard_aggregation_flow,
    account_deletion_flow,
    recurring_todo_flow,
)


def deploy_all_flows():
    """Deploy all flows to Prefect server."""
    
    print("🚀 Deploying Prefect flows...")
    
    # Create deployments
    dashboard_deployment = dashboard_aggregation_flow.to_deployment(
        name="dashboard-aggregation-hourly",
        description="Aggregates dashboard metrics across all tenants. Runs hourly.",
        schedule=IntervalSchedule(interval=timedelta(hours=1)),
        tags=["dashboard", "metrics", "scheduled"],
    )
    
    # Account deletion is ALWAYS manual - never scheduled
    # It's triggered by API call when OWNER confirms account deletion
    account_deletion_deployment = account_deletion_flow.to_deployment(
        name="account-deletion-manual",
        description="Deletes tenant account, schema, and Keycloak resources. API-triggered only (OWNER must confirm).",
        tags=["cleanup", "deletion", "manual", "destructive"],
        # NO schedule - this is intentionally manual-only for safety
    )
    
    # Recurring todos run daily at midnight to create new instances of recurring tasks
    recurring_todo_deployment = recurring_todo_flow.to_deployment(
        name="recurring-todos-daily",
        description="Creates new instances of recurring todos. Runs daily at midnight UTC.",
        schedule=CronSchedule(cron="0 0 * * *"),  # Daily at midnight UTC
        tags=["todos", "recurring", "scheduled"],
    )
    
    print("✅ Deployments created:")
    print("   - Dashboard Aggregation (hourly)")
    print("   - Account Deletion (manual trigger only - API initiated)")
    print("   - Recurring Todos (daily at midnight UTC)")
    
    # Serve all deployments
    print("\n🔄 Starting Prefect worker to serve deployments...")
    print("   Press Ctrl+C to stop the worker\n")
    
    serve(
        dashboard_deployment,
        account_deletion_deployment,
        recurring_todo_deployment,
    )


if __name__ == "__main__":
    deploy_all_flows()
