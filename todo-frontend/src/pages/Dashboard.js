import { useState, useEffect } from "react";
import api from "../api/axios";
import { useNavigate } from "react-router-dom";
import TenantUsersList from "../components/TenantUsersList";
import InviteUsers from "./InviteUsers";
import useSessionValidator from "../hooks/useSessionValidator";

function Dashboard() {
  // Validate session every 5 seconds
  useSessionValidator(5000);

  const navigate = useNavigate();

  // ===================== STATE =====================
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const [showTeamManagement, setShowTeamManagement] = useState(false);

  const [showDeleteWarning, setShowDeleteWarning] = useState(false);
  const [deleteConfirmed, setDeleteConfirmed] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [teamRefreshKey, setTeamRefreshKey] = useState(0);

  const isOwner = metrics?.role === "OWNER";

  // ===================== FETCH METRICS =====================
  const fetchMetrics = async () => {
    try {
      const res = await api.get("customers/metrics/dashboard/");
      setMetrics(res.data);
    } catch (err) {
      setError(
        err.response?.data?.error || "Failed to load dashboard metrics"
      );
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  // ===================== MANUAL AGGREGATION =====================
  const handleManualAggregation = async () => {
    try {
      setRefreshing(true);

      const res = await api.post("customers/orchestration/aggregate-dashboard/");

      if (res.data.status === "completed") {
        // Sync aggregation succeeded — just re-fetch the updated metrics
        await fetchMetrics();
        setRefreshing(false);
      } else {
        // Prefect flow was triggered (async) — poll until updated
        const oldLastUpdated = metrics?.last_updated;
        let attempts = 0;
        const maxAttempts = 15;

        const poll = async () => {
          const metricsRes = await api.get("customers/metrics/dashboard/");
          setMetrics(metricsRes.data);

          if (
            metricsRes.data.last_updated !== oldLastUpdated ||
            attempts >= maxAttempts
          ) {
            setRefreshing(false);
            return;
          }

          attempts++;
          setTimeout(poll, 1000);
        };

        setTimeout(poll, 1000);
      }
    } catch (err) {
      setError(
        err.response?.data?.error || "Failed to refresh metrics"
      );
      setRefreshing(false);
    }
  };

  // ===================== DELETE ACCOUNT =====================
  const handleDeleteAccount = async () => {
    if (!deleteConfirmed) return;

    try {
      setDeleting(true);

      await api.delete("customers/account/delete/", {
        data: { confirm_deletion: true },
      });

      localStorage.clear();
      navigate("/login");
    } catch (err) {
      setError(err.response?.data?.error || "Failed to delete account");
    } finally {
      setDeleting(false);
    }
  };

  const handleUserInvited = () => {
    setTeamRefreshKey((k) => k + 1);
    fetchMetrics();
  };

  // ===================== JSX =====================
  return (
    <div className="max-w-4xl mx-auto bg-white p-8 rounded-xl shadow-lg mt-8 relative">
      <div className="flex flex-col md:flex-row md:justify-between md:items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-800 mb-1">Dashboard</h1>
          <p className="text-gray-600">Organization: {metrics?.schema_name || "-"}</p>
          <p className="text-xs text-gray-400 mt-1">Current role: {metrics?.role || "-"}</p>
        </div>
        <div className="flex gap-3 mt-4 md:mt-0">
          <button
            onClick={handleManualAggregation}
            disabled={refreshing}
            className="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 transition disabled:opacity-50"
          >
            {refreshing ? "Refreshing..." : "Refresh Metrics"}
          </button>
          <button
            onClick={() => navigate("/todos")}
            className="bg-gray-600 text-white px-6 py-2 rounded hover:bg-gray-700 transition"
          >
            Go to Todos
          </button>
          <button
            onClick={() => setShowTeamManagement((v) => !v)}
            className="bg-purple-600 text-white px-6 py-2 rounded hover:bg-purple-700 transition"
          >
            {showTeamManagement ? "Hide Team" : "Manage Team"}
          </button>
        </div>
        {/* Delete Account button: right by default, left when Manage Team or Delete modal is open */}
        {isOwner && (
          <button
            onClick={() => setShowDeleteWarning(true)}
            className="bg-red-600 text-white px-6 py-2 rounded shadow-lg hover:bg-red-700 transition disabled:opacity-50"
            style={{ position: 'absolute', bottom: '3%', 
              left: (showTeamManagement || showDeleteWarning) ? '32px' : 'auto',
              right: (showTeamManagement || showDeleteWarning) ? 'auto' : '32px',
              zIndex: 40 }}
          >
            Delete Account
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">{error}</div>
      )}

      {metrics?.message && (
        <div className="bg-blue-100 border border-blue-400 text-blue-700 px-4 py-3 rounded mb-6">
          ℹ️ {metrics.message}
          <br />
          <small>Click “Refresh Metrics” to compute them now.</small>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-8">
        <MetricCard title="Active Todos" value={metrics?.new_todos || 0} />
        <MetricCard title="Completed" value={metrics?.completed_todos || 0} />
        <MetricCard title="Total Todos" value={metrics?.total_todos || 0} />
        <MetricCard title="Team Members" value={metrics?.total_users || 0} />
      </div>

      <div className="bg-gray-50 rounded-lg shadow p-6 mb-8">
        <h2 className="text-lg font-bold text-gray-800 mb-3">Team Roles</h2>
        <div className="grid grid-cols-3 gap-6">
          <div className="text-center">
            <p className="text-2xl font-bold text-blue-600">{metrics?.owners || 0}</p>
            <p className="text-gray-600 text-sm">Owners</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-green-600">{metrics?.members || 0}</p>
            <p className="text-gray-600 text-sm">Members</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-yellow-600">{metrics?.viewers || 0}</p>
            <p className="text-gray-600 text-sm">Viewers</p>
          </div>
        </div>
      </div>

      {metrics?.last_updated && (
        <div className="flex flex-col items-start mb-6">
          <div className="text-left text-sm text-gray-500 mb-2">
            Last updated: {new Date(metrics.last_updated).toLocaleString()}
          </div>
        </div>
      )}

      {showTeamManagement && (
        <div className="bg-white shadow rounded-xl p-6 mb-20 flex flex-col items-start">
          <h2 className="text-xl font-semibold mb-4">Team Management</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {isOwner && <InviteUsers onUserInvited={handleUserInvited} />}
            <TenantUsersList refreshKey={teamRefreshKey} />
          </div>
        </div>
      )}

      {showDeleteWarning && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white p-8 rounded-xl shadow-lg max-w-md w-full">
            <h2 className="text-xl font-bold text-red-600 mb-4">Confirm Account Deletion</h2>
            <p className="text-gray-700 mb-4">This will permanently delete:</p>
            <ul className="list-disc list-inside text-gray-700 mb-4">
              <li>{metrics?.total_todos || 0} todos</li>
              <li>{metrics?.total_users || 0} users</li>
              <li>Entire organization schema</li>
              <li>All Keycloak identities</li>
            </ul>
            <label className="flex items-center mb-4">
              <input
                type="checkbox"
                checked={deleteConfirmed}
                onChange={(e) => setDeleteConfirmed(e.target.checked)}
                className="mr-2"
              />
              <span className="text-gray-700">I understand this cannot be undone</span>
            </label>
            <div className="flex gap-4">
              <button
                onClick={() => {
                  setShowDeleteWarning(false);
                  setDeleteConfirmed(false);
                }}
                className="flex-1 bg-gray-300 text-gray-800 px-4 py-2 rounded"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAccount}
                disabled={!deleteConfirmed || deleting}
                className="flex-1 bg-red-600 text-white px-4 py-2 rounded disabled:opacity-50"
              >
                {deleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ===================== SMALL COMPONENT ===================== */

function MetricCard({ title, value }) {
  return (
    <div className="bg-white shadow rounded p-4 text-center">
      <p className="text-gray-600 text-sm">{title}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}

export default Dashboard;
