import { useState, useEffect } from "react"; // ⭐ added useEffect
import { useNavigate } from "react-router-dom";
import api from "../api/axios";

function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [tenantOptions, setTenantOptions] = useState([]);
  const [showTenantModal, setShowTenantModal] = useState(false);
  const [loginResponse, setLoginResponse] = useState(null);

  const navigate = useNavigate();

  // ⭐ Force clear fields on mount (prevents autofill restore)
  useEffect(() => {
    setUsername("");
    setPassword("");
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");

    try {
      const res = await api.post("auth/login/", { username, password });

      const tenant =
        res.data.tenant || (Array.isArray(res.data.tenants) && res.data.tenants[0]);
      const tenantsList = res.data.tenants || (tenant ? [tenant] : []);

      // Always save tokens (for default tenant) so switch-tenant can be called when needed
      localStorage.setItem("access", res.data.access);
      localStorage.setItem("refresh", res.data.refresh);
      localStorage.setItem("role", res.data.user?.role || "");
      localStorage.setItem("email", res.data.user?.email || "");
      localStorage.setItem("username", res.data.user?.username || "");
      localStorage.setItem("tenant", tenant?.schema || "");
      localStorage.setItem("tenants", JSON.stringify(tenantsList));

      if (Array.isArray(tenantsList) && tenantsList.length > 1) {
        setTenantOptions(tenantsList);
        setLoginResponse(res.data);
        setShowTenantModal(true);
        return;
      }

      setUsername("");
      setPassword("");
      navigate("/todos");
    } catch (err) {
      const msg = err.response?.data?.error || "Invalid username/email or password";
      setError(msg);
    }
  };

  const handleTenantSelect = async (selectedTenant) => {
    setShowTenantModal(false);

    const currentSchema = loginResponse?.tenant?.schema;
    if (selectedTenant.schema === currentSchema) {
      navigate("/todos");
      return;
    }

    try {
      const res = await api.post("auth/switch-tenant/", {
        tenant_schema: selectedTenant.schema,
      });

      localStorage.setItem("access", res.data.access);
      localStorage.setItem("refresh", res.data.refresh);
      localStorage.setItem("role", res.data.user?.role || "");
      localStorage.setItem("username", res.data.user?.username || "");
      localStorage.setItem("tenant", res.data.tenant?.schema || "");

      navigate("/todos");
    } catch {
      setError("Failed to switch organisation. Please try again.");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      {showTenantModal && (
        <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-40 z-50">
          <div className="bg-white p-6 rounded-lg shadow-lg w-96">
            <h3 className="text-lg font-semibold mb-4 text-center">
              Select a Tenant
            </h3>
            <ul className="mb-4">
              {tenantOptions.map((tenant) => (
                <li key={tenant.schema} className="mb-2">
                  <button
                    className="w-full bg-blue-500 text-white py-2 rounded hover:bg-blue-600"
                    onClick={() => handleTenantSelect(tenant)}
                  >
                    {tenant.name || tenant.schema}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <div className="bg-white p-6 rounded shadow w-96">
        {/* ⭐ autoComplete trick to defeat browser autofill */}
        <form onSubmit={handleLogin} autoComplete="new-password">
          <input
            type="text"
            name="login-username"
            placeholder="Username or email"
            className="w-full mb-1 p-2 border rounded"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="new-password"
          />
          <div className="text-xs text-gray-500 mb-3">You can login with your username or the email you were invited with.</div>

          <input
            type="password"
            name="login-password" // ⭐ unique name
            placeholder="Password"
            className="w-full mb-3 p-2 border rounded"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
          />

          <button
            type="submit"
            className="w-full bg-blue-500 text-white py-2 rounded hover:bg-blue-600"
          >
            Login
          </button>

          {error && (
            <div className="text-red-500 text-sm mt-2 text-center">
              {error}
            </div>
          )}
        </form>

        <p className="mt-4 text-center">
          New here?{" "}
          <span
            className="text-blue-600 cursor-pointer hover:underline"
            onClick={() => navigate("/signup")}
          >
            Create an account
          </span>
        </p>
        <p className="mt-2 text-center">
          <span
            className="text-blue-600 cursor-pointer hover:underline text-sm"
            onClick={() => navigate("/reset-password")}
          >
            Forgot Password?
          </span>
        </p>
      </div>
    </div>
  );
}

export default Login;
