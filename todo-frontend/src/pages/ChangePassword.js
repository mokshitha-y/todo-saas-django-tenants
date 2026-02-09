import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";
import Navbar from "../components/Navbar";

function ChangePassword() {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleChange = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!oldPassword || !newPassword || !confirmPassword) {
      setError("All fields are required");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("New passwords do not match");
      return;
    }

    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters");
      return;
    }

    if (oldPassword === newPassword) {
      setError("New password must be different from current password");
      return;
    }

    setLoading(true);
    try {
      const res = await api.post("auth/change-password/", {
        old_password: oldPassword,
        new_password: newPassword,
      });
      setSuccess(res.data.message || "Password changed successfully!");
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err.response?.data?.error || "Failed to change password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="max-w-4xl mx-auto py-6 px-4">
        <Navbar />

        <div className="flex justify-center">
          <form
            onSubmit={handleChange}
            className="bg-white p-6 rounded-lg shadow-md w-96"
            autoComplete="off"
          >
            <h2 className="text-xl font-semibold mb-2 text-center">
              Change Password
            </h2>
            <p className="text-sm text-gray-500 mb-4 text-center">
              Enter your current password and choose a new one.
            </p>

            <input
              type="password"
              className="w-full mb-3 px-3 py-2 border rounded"
              placeholder="Current Password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              autoComplete="current-password"
              required
            />

            <input
              type="password"
              className="w-full mb-3 px-3 py-2 border rounded"
              placeholder="New Password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              required
            />

            <input
              type="password"
              className="w-full mb-3 px-3 py-2 border rounded"
              placeholder="Confirm New Password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              required
            />

            {error && (
              <p className="text-red-500 text-sm mb-3 text-center">{error}</p>
            )}

            {success && (
              <p className="text-green-500 text-sm mb-3 text-center">{success}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 transition disabled:opacity-50"
            >
              {loading ? "Changing..." : "Change Password"}
            </button>

            <p className="text-sm text-center mt-4">
              <span
                className="text-gray-500 cursor-pointer hover:underline"
                onClick={() => navigate("/todos")}
              >
                ← Back to Todos
              </span>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}

export default ChangePassword;
