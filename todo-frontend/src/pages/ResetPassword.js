import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";

function ResetPassword() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleReset = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!username || !email || !newPassword || !confirmPassword) {
      setError("All fields are required");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setLoading(true);
    try {
      const res = await api.post("auth/reset-password/", {
        username,
        email,
        new_password: newPassword,
      });
      setSuccess(res.data.message || "Password reset successfully!");
      setTimeout(() => navigate("/login"), 2500);
    } catch (err) {
      setError(err.response?.data?.error || "Failed to reset password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <form
        onSubmit={handleReset}
        className="bg-white p-6 rounded-lg shadow-md w-96"
        autoComplete="off"
      >
        <h2 className="text-xl font-semibold mb-2 text-center">
          Forgot Password
        </h2>
        <p className="text-sm text-gray-500 mb-4 text-center">
          Verify your identity with your username and email, then set a new password.
        </p>

        <input
          className="w-full mb-3 px-3 py-2 border rounded"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="off"
          required
        />

        <input
          type="email"
          className="w-full mb-3 px-3 py-2 border rounded"
          placeholder="Email (used during invite/signup)"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="off"
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
          {loading ? "Resetting..." : "Reset Password"}
        </button>

        <p className="text-sm text-center mt-4">
          <span
            className="text-blue-600 cursor-pointer hover:underline"
            onClick={() => navigate("/login")}
          >
            Back to Login
          </span>
        </p>
      </form>
    </div>
  );
}

export default ResetPassword;