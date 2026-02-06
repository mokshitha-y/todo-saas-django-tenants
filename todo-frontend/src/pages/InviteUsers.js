import { useState } from "react";
import api from "../api/axios";

function InviteUsers() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("MEMBER");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const handleInvite = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");

    try {
      await api.post("auth/invite/", {
        username,
        password,
        role,
      });

      setMessage(`User ${username} invited successfully`);
      setUsername("");
      setPassword("");
      setRole("MEMBER");
    } catch (err) {
      setError(
        err.response?.data?.error || "Failed to invite user"
      );
    }
  };

  return (
    <div className="border p-4 rounded bg-gray-50 mt-4">
      <h3 className="font-semibold mb-2">Invite User</h3>

      <form onSubmit={handleInvite} className="flex flex-col gap-2">
        <input
          className="border px-3 py-2 rounded"
          placeholder="Username"
          value={username}
          required
          onChange={(e) => setUsername(e.target.value)}
        />

        <input
          type="password"
          className="border px-3 py-2 rounded"
          placeholder="Password"
          value={password}
          required
          onChange={(e) => setPassword(e.target.value)}
        />

        <select
          className="border px-3 py-2 rounded"
          value={role}
          onChange={(e) => setRole(e.target.value)}
        >
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
