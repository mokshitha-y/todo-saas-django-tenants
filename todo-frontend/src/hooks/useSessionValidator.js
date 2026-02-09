import { useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";

/**
 * Hook that periodically validates the user's session and role.
 * If the session is invalid, role has changed, or user was removed, alerts and redirects to login.
 * 
 * @param {number} intervalMs - How often to check (default: 30 seconds)
 */
function useSessionValidator(intervalMs = 30000) {
  const navigate = useNavigate();

  const validateSession = useCallback(async () => {
    const token = localStorage.getItem("access");
    if (!token) return; // Not logged in, nothing to validate

    try {
      // Call an endpoint that returns the user's current role
      const response = await api.get("customers/users/");
      
      // Check if current user's role matches stored role
      const currentUsername = localStorage.getItem("username");
      const storedRole = localStorage.getItem("role");
      
      if (response.data && Array.isArray(response.data)) {
        const currentUser = response.data.find(u => u.username === currentUsername);
        
        if (!currentUser) {
          // User was removed from tenant!
          localStorage.clear();
          alert("You have been removed from this organization by an administrator. Please contact your administrator if this was unexpected.");
          navigate("/login", { replace: true });
          return;
        }
        
        if (currentUser.role !== storedRole) {
          // Role has changed!
          localStorage.clear();
          alert(`Your role has been changed from ${storedRole} to ${currentUser.role}. Please log in again to continue with your new permissions.`);
          navigate("/login", { replace: true });
        }
      }
    } catch (error) {
      // 401 or 403 means session invalid or user removed
      if (error.response?.status === 401 || error.response?.status === 403) {
        localStorage.clear();
        alert("Your session has ended. You may have been removed from this organization or your permissions have changed. Please log in again.");
        navigate("/login", { replace: true });
      }
      // Other errors we ignore (network issues, etc.)
    }
  }, [navigate]);

  useEffect(() => {
    // Validate immediately on mount
    validateSession();

    // Then validate periodically
    const interval = setInterval(validateSession, intervalMs);

    return () => clearInterval(interval);
  }, [validateSession, intervalMs]);
}

export default useSessionValidator;
