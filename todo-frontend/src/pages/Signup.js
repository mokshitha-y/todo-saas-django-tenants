import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";

function Signup() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [tenantName, setTenantName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();

  const handleSignup = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await api.post("auth/register/", {
        username,
        password,
        tenant_name: tenantName,
      });

      alert("Account created successfully! Please login.");
      navigate("/login");
    } catch (err) {
      setError(
        err.response?.data?.error ||
          "Signup failed. Try a different username."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <form
        onSubmit={handleSignup}
        className="bg-white p-6 rounded-lg shadow-md w-96"
      >
        <h2 className="text-xl font-semibold mb-4 text-center">
          Create Your Organization
        </h2>

        <input
          className="w-full mb-3 px-3 py-2 border rounded focus:outline-none focus:ring focus:ring-blue-300"
          placeholder="Organization / Tenant Name"
          value={tenantName}
          onChange={(e) => setTenantName(e.target.value)}
          required
        />

        <input
          className="w-full mb-3 px-3 py-2 border rounded focus:outline-none focus:ring focus:ring-blue-300"
          placeholder="Owner Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />

        <input
          type="password"
          className="w-full mb-3 px-3 py-2 border rounded focus:outline-none focus:ring focus:ring-blue-300"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        {error && (
          <p className="text-red-500 text-sm mb-3 text-center">{error}</p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-green-600 text-white py-2 rounded hover:bg-green-700 transition disabled:opacity-50"
        >
          {loading ? "Creating..." : "Create Account"}
        </button>

        <p className="text-sm text-center mt-4">
          Already have an account?{" "}
          <span
            className="text-blue-600 cursor-pointer hover:underline"
            onClick={() => navigate("/login")}
          >
            Login
          </span>
        </p>
      </form>
    </div>
  );
}

export default Signup;
