import { useEffect, useState } from "react";
import { fetchTenantUsers, removeUserFromTenant, updateUserRole } from "../api/tenantUsers";

function TenantUsersList({ refreshKey = 0 }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  
  // Get current user's role from localStorage
  const currentUserRole = localStorage.getItem("role");
  const currentUsername = localStorage.getItem("username");
  const isOwner = currentUserRole === "OWNER";

  const loadUsers = async () => {
    try {
      const data = await fetchTenantUsers();
      setUsers(data);
    } catch (err) {
      console.error("Failed to load tenant users");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, [refreshKey]);

  const handleRemoveUser = async (user) => {
    if (!window.confirm(`Remove ${user.username} from this organization? They will lose access immediately.`)) {
      return;
    }

    setActionLoading(user.id);
    setMessage("");
    setError("");

    try {
      const result = await removeUserFromTenant(user.id);
      setMessage(`${user.username} has been removed. ${result.keycloak_tokens_revoked ? "Access revoked." : ""}`);
      // Refresh the list
      await loadUsers();
    } catch (err) {
      setError(err.response?.data?.error || "Failed to remove user");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRoleChange = async (user, newRole) => {
    if (newRole === user.role) return;
    
    const action = newRole === "OWNER" ? "promote" : "change role of";
    if (!window.confirm(`${action} ${user.username} to ${newRole}?\n\nThey will be logged out and must re-login to get their new permissions.`)) {
      return;
    }

    setActionLoading(user.id);
    setMessage("");
    setError("");

    try {
      const result = await updateUserRole(user.id, newRole);
      setMessage(`${user.username}'s role changed: ${result.old_role} → ${result.new_role}. They must re-login for changes to take effect.`);
      // Refresh the list
      await loadUsers();
    } catch (err) {
      setError(err.response?.data?.error || "Failed to update role");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return <p className="text-sm text-gray-500 mt-4">Loading team...</p>;
  }

  if (users.length === 0) {
    return <p className="text-sm text-gray-500 mt-4">No team members yet</p>;
  }

  return (
    <div className="mt-6">
      <h3 className="text-lg font-semibold mb-2">Team Members</h3>

      {/* Status Messages */}
      {message && (
        <div className="bg-green-100 border border-green-400 text-green-700 px-3 py-2 rounded mb-3 text-sm">
          ✅ {message}
        </div>
      )}
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-3 py-2 rounded mb-3 text-sm">
          ❌ {error}
        </div>
      )}

      <div className="border rounded overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-100">
            <tr>
              <th className="p-2 text-left">Username</th>
              <th className="p-2 text-left">Role</th>
              <th className="p-2 text-left">Joined</th>
              {isOwner && <th className="p-2 text-left">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const isCurrentUser = u.username === currentUsername;
              const isUserOwner = u.role === "OWNER";
              const canManage = isOwner && !isCurrentUser && !isUserOwner;
              const isLoading = actionLoading === u.id;

              return (
                <tr key={u.id} className={`border-t ${isCurrentUser ? "bg-blue-50" : ""}`}>
                  <td className="p-2">
                    {u.username}
                    {isCurrentUser && <span className="text-xs text-blue-600 ml-1">(you)</span>}
                  </td>
                  <td className="p-2">
                    {canManage ? (
                      <select
                        className="border rounded px-2 py-1 text-sm bg-white"
                        value={u.role}
                        onChange={(e) => handleRoleChange(u, e.target.value)}
                        disabled={isLoading}
                      >
                        <option value="OWNER">OWNER</option>
                        <option value="MEMBER">MEMBER</option>
                        <option value="VIEWER">VIEWER</option>
                      </select>
                    ) : (
                      <span className={`font-medium ${
                        u.role === "OWNER" ? "text-purple-600" : 
                        u.role === "MEMBER" ? "text-blue-600" : "text-gray-600"
                      }`}>
                        {u.role}
                      </span>
                    )}
                  </td>
                  <td className="p-2 text-gray-500">
                    {new Date(u.joined_at).toLocaleDateString()}
                  </td>
                  {isOwner && (
                    <td className="p-2">
                      {canManage && (
                        <button
                          onClick={() => handleRemoveUser(u)}
                          disabled={isLoading}
                          className={`text-red-600 hover:text-red-800 text-sm font-medium ${
                            isLoading ? "opacity-50 cursor-not-allowed" : ""
                          }`}
                        >
                          {isLoading ? "..." : "Remove"}
                        </button>
                      )}
                      {isUserOwner && !isCurrentUser && (
                        <span className="text-gray-400 text-xs">Owner</span>
                      )}
                      {isCurrentUser && (
                        <span className="text-gray-400 text-xs">—</span>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {isOwner && (
        <p className="text-xs text-gray-500 mt-2">
          💡 As Owner, you can change roles and remove team members. Removed users lose access immediately.
        </p>
      )}
    </div>
  );
}

export default TenantUsersList;
