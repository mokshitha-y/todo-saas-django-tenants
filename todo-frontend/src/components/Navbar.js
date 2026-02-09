
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";

function Navbar() {
  const role = localStorage.getItem("role");
  const username = localStorage.getItem("username");
  const currentTenant = localStorage.getItem("tenant");
  const [tenants, setTenants] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loadingSwitch, setLoadingSwitch] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    // Try to get tenants from localStorage (set at login)
    const stored = localStorage.getItem("tenants");
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        setTenants(parsed);
        console.log("[Navbar] Tenants loaded from localStorage:", parsed);
      } catch {
        setTenants([]);
      }
    }
  }, []);

  const logout = () => {
    localStorage.clear();
    navigate("/");
    window.location.reload();
  };

  const handleTenantSwitch = async (tenant) => {
    setLoadingSwitch(true);
    try {
      const refresh = localStorage.getItem("refresh");
      console.log("[Tenant Switch] Sending tenant_schema:", tenant.schema);
      const res = await api.post("auth/switch-tenant/", {
        tenant_schema: tenant.schema,
        refresh,
      });
      localStorage.setItem("access", res.data.access);
      localStorage.setItem("refresh", res.data.refresh);
      localStorage.setItem("role", res.data.user.role);
      localStorage.setItem("username", res.data.user.username);
      localStorage.setItem("tenant", tenant.schema);
      if (res.data.tenants) {
        localStorage.setItem("tenants", JSON.stringify(res.data.tenants));
        setTenants(res.data.tenants);
      }
      setShowDropdown(false);
      setLoadingSwitch(false);
      window.location.reload();
    } catch (err) {
      setLoadingSwitch(false);
      alert("Failed to switch tenant. Please try again.");
      if (err.response) {
        console.error("[Tenant Switch] Error response:", err.response.data);
      } else {
        console.error("[Tenant Switch] Error:", err);
      }
    }
  };

  return (
    <div className="flex justify-between items-center px-6 py-3 bg-gray-900 text-white rounded mb-6">
      <div className="text-lg font-semibold">Todo SaaS</div>

      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-300">
          {username} ({role})
        </span>


        <button
          onClick={() => navigate("/todos")}
          className="bg-blue-600 px-3 py-1 rounded hover:bg-blue-700 transition text-sm"
        >
          Todos
        </button>

        <button
          onClick={() => navigate("/dashboard")}
          className="bg-purple-600 px-3 py-1 rounded hover:bg-purple-700 transition text-sm"
        >
          Dashboard
        </button>

        <button
          onClick={() => navigate("/change-password")}
          className="bg-yellow-600 px-3 py-1 rounded hover:bg-yellow-700 transition text-sm"
        >
          Change Password
        </button>

        <button
          onClick={logout}
          className="bg-red-600 px-3 py-1 rounded hover:bg-red-700 transition"
        >
          Logout
        </button>
      </div>
    </div>
  );
}

export default Navbar;
