import { useState, useEffect, useCallback } from "react";
import api from "../api/axios";

function InviteUsers({ onUserInvited }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [invitations, setInvitations] = useState([]);
  const [showInvitations, setShowInvitations] = useState(false);

  const validateEmail = (value) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  };

  const fetchInvitations = useCallback(async () => {
    try {
      const response = await api.get("customers/invitations/list/");
      setInvitations(response.data.invitations || []);
    } catch (err) {
      console.error("Failed to fetch invitations:", err);
    }
  }, []);

  useEffect(() => {
    if (showInvitations) {
      fetchInvitations();
    }
  }, [showInvitations, fetchInvitations]);

  const handleInvite = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");

    if (!role) {
      setError("Please select a role");
      return;
    }

    if (!email.trim()) {
      setError("Email is required");
      return;
    }

    if (!validateEmail(email)) {
      setError("Invalid email format");
      return;
    }

    setLoading(true);
    try {
      const response = await api.post("customers/invitations/", {
        email,
        role,
      });

      setMessage(response.data.message || `Invitation sent to ${email}`);
      setEmail("");
      setRole("");

      // Refresh invitations list if visible
      if (showInvitations) {
        fetchInvitations();
      }

      // Notify parent to refresh team list
      if (onUserInvited) {
        onUserInvited();
      }
    } catch (err) {
      setError(
        err.response?.data?.error || "Failed to send invitation"
      );
    } finally {
      setLoading(false);
    }
  };

  const handleCancelInvitation = async (token) => {
    try {
      await api.delete(`customers/invitations/${token}/cancel/`);
      fetchInvitations();
    } catch (err) {
      setError(err.response?.data?.error || "Failed to cancel invitation");
    }
  };

  const handleResendInvitation = async (token) => {
    try {
      const response = await api.post(`customers/invitations/${token}/resend/`);
      setMessage(response.data.message || "Invitation resent");
      fetchInvitations();
    } catch (err) {
      setError(err.response?.data?.error || "Failed to resend invitation");
    }
  };

  const getStatusBadge = (status) => {
    const badges = {
      pending: "bg-yellow-100 text-yellow-800",
      accepted: "bg-green-100 text-green-800",
      expired: "bg-gray-100 text-gray-800",
      cancelled: "bg-red-100 text-red-800",
    };
    return badges[status] || "bg-gray-100 text-gray-800";
  };

  return (
    <div className="border p-4 rounded bg-gray-50 mt-4">
      <h3 className="font-semibold mb-2">Invite User</h3>
      <p className="text-sm text-gray-600 mb-3">
        Send an email invitation. The invitee will set their own username and password.
      </p>

      <form onSubmit={handleInvite} className="flex flex-col gap-2" autoComplete="off">
        <input
          type="email"
          className="border px-3 py-2 rounded"
          placeholder="invitee@company.com"
          value={email}
          required
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="off"
        />

        <select
          className="border px-3 py-2 rounded"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          required
        >
          <option value="" disabled>Select Role</option>
          <option value="MEMBER">Member - Can create and edit todos</option>
          <option value="VIEWER">Viewer - Read-only access</option>
        </select>

        <button 
          className="bg-blue-600 text-white py-2 rounded hover:bg-blue-700 disabled:opacity-50"
          disabled={loading}
        >
          {loading ? "Sending..." : "Send Invitation"}
        </button>

        {message && <p className="text-green-600 text-sm">{message}</p>}
        {error && <p className="text-red-600 text-sm">{error}</p>}
      </form>

      {/* Toggle to show/hide invitations */}
      <button
        className="mt-4 text-blue-600 text-sm hover:underline"
        onClick={() => setShowInvitations(!showInvitations)}
      >
        {showInvitations ? "Hide Invitations" : "View Pending Invitations"}
      </button>

      {/* Invitations List */}
      {showInvitations && (
        <div className="mt-3">
          <h4 className="font-medium text-sm mb-2">Invitations</h4>
          {invitations.length === 0 ? (
            <p className="text-gray-500 text-sm">No invitations sent yet.</p>
          ) : (
            <div className="space-y-2">
              {invitations.map((inv) => (
                <div key={inv.token} className="bg-white p-3 rounded border text-sm">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="font-medium">{inv.email}</p>
                      <p className="text-gray-500">
                        Role: {inv.role} · Sent: {new Date(inv.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs ${getStatusBadge(inv.status)}`}>
                      {inv.status}
                    </span>
                  </div>
                  {inv.status === "pending" && (
                    <div className="mt-2 flex gap-2">
                      <button
                        className="text-blue-600 hover:underline text-xs"
                        onClick={() => handleResendInvitation(inv.token)}
                      >
                        Resend
                      </button>
                      <button
                        className="text-red-600 hover:underline text-xs"
                        onClick={() => handleCancelInvitation(inv.token)}
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                  {inv.status === "expired" && (
                    <button
                      className="mt-2 text-blue-600 hover:underline text-xs"
                      onClick={() => handleResendInvitation(inv.token)}
                    >
                      Resend Invitation
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default InviteUsers;
