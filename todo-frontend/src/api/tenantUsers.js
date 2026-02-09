import api from "./axios";

export const fetchTenantUsers = async () => {
  const res = await api.get("customers/users/");
  // Handle both paginated and non-paginated responses
  const data = res.data.results || res.data;
  return Array.isArray(data) ? data : [];
};

export const removeUserFromTenant = async (userId, deleteFromKeycloak = false) => {
  const res = await api.delete(`customers/users/${userId}/remove/`, {
    data: { delete_from_keycloak: deleteFromKeycloak }
  });
  return res.data;
};

export const updateUserRole = async (userId, newRole) => {
  const res = await api.patch(`customers/users/${userId}/role/`, {
    role: newRole
  });
  return res.data;
};
