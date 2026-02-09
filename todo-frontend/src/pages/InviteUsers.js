import { useState } from "react";
import api from "../api/axios";

function InviteUsers({ onUserInvited }) {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const validateEmail = (value) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  };

  const validateUsername = (value) => {
    return value && value.trim().length >= 3;
  };

  const handleInvite = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");

    if (!role) {
      setError("Please select a role");
      return;
    }

    if (!validateUsername(username)) {
      setError("Username is required (min 3 chars)");
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

    try {
      await api.post("auth/invite/", {
        username,
        email,
        password,
        role,
      });

      setMessage(`Invite sent to ${email} (username: ${username})`);
      setUsername("");
      setEmail("");
      setPassword("");
      setRole("");

      // Notify parent to refresh team list
      if (onUserInvited) {
        onUserInvited();
      }
    } catch (err) {
      setError(
        err.response?.data?.error || "Failed to invite user"
      );
    }
  };

  return (
    <div className="border p-4 rounded bg-gray-50 mt-4">
      <h3 className="font-semibold mb-2">Invite User</h3>

      <form onSubmit={handleInvite} className="flex flex-col gap-2" autoComplete="off">
        <input
          className="border px-3 py-2 rounded"
          placeholder="Username"
          value={username}
          required
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="off"
        />

        <input
          className="border px-3 py-2 rounded"
          placeholder="invitee@company.com"
          value={email}
          required
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="off"
        />

        <input
          type="password"
          className="border px-3 py-2 rounded"
          placeholder="Temporary password (optional)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
        />

        <select
          className="border px-3 py-2 rounded"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          required
        >
          <option value="" disabled>Select Role</option>
          <option value="MEMBER">Member</option>
          <option value="VIEWER">Viewer</option>
        </select>

        <button className="bg-blue-600 text-white py-2 rounded hover:bg-blue-700">
          Invite
        </button>

        {message && <p className="text-green-600 text-sm">{message}</p>}
        {error && <p className="text-red-600 text-sm">{error}</p>}
      </form>
    </div>
  );
}

export default InviteUsers;
