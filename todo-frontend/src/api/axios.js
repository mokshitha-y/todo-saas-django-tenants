import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000/api/",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access");

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const wasLoggedIn = localStorage.getItem("access");
    
    if (error.response?.status === 401) {
      localStorage.clear();
      
      if (wasLoggedIn) {
        alert("Your session has ended. This may be because your role was changed by an administrator. Please log in again.");
      }
      
      window.location.href = "/login";
    }
    
    // Handle 403 - role changed or permissions revoked
    if (error.response?.status === 403 && wasLoggedIn) {
      const errorMsg = error.response?.data?.detail || error.response?.data?.error || "";
      
      // Check if it's a role/permission related 403
      if (errorMsg.includes("cannot") || errorMsg.includes("not") || errorMsg.includes("permission")) {
        localStorage.clear();
        alert("Your permissions have changed. This may be because your role was updated by an administrator. Please log in again.");
        window.location.href = "/login";
      }
    }
    
    return Promise.reject(error);
  }
);

export default api;
