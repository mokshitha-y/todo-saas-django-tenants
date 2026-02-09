import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";
import TodoItem from "../components/TodoItem";
import Navbar from "../components/Navbar";
import useSessionValidator from "../hooks/useSessionValidator";
import TenantUsersList from "../components/TenantUsersList";
import InviteUsers from "./InviteUsers";

const PAGE_SIZE = 5;

function Todos() {
  // Validate session every 5 seconds - auto logout if role changed
  useSessionValidator(5000);
  const [todos, setTodos] = useState([]);
  const [filteredTodos, setFilteredTodos] = useState([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [recurrenceType, setRecurrenceType] = useState("NONE");
  const [assignedTo, setAssignedTo] = useState("");
  const [tenantUsers, setTenantUsers] = useState([]);
  const [filter, setFilter] = useState("ALL");
  const [page, setPage] = useState(1);
  const [showTeamManagement, setShowTeamManagement] = useState(false);
  const [teamRefreshKey, setTeamRefreshKey] = useState(0);

  const role = localStorage.getItem("role");
  const currentUsername = localStorage.getItem("username");
  const navigate = useNavigate();
  const isOwner = role === "OWNER";

  // Callback to refresh team list when a new user is invited
  const handleUserInvited = () => {
    setTeamRefreshKey(prev => prev + 1);
    // Also refresh tenant users for assignment dropdown
    fetchTenantUsers();
  };

  const fetchTodos = useCallback(async () => {
    try {
      const res = await api.get("todos/");
      // Handle both paginated and non-paginated responses
      const data = res.data.results || res.data;
      setTodos(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Unauthorized, redirecting to login");
      localStorage.clear();
      navigate("/login", { replace: true });
    }
  }, [navigate]);

  const fetchTenantUsers = useCallback(async () => {
    try {
      const res = await api.get("customers/users/");
      setTenantUsers(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error("Failed to fetch tenant users");
    }
  }, []);

  useEffect(() => {
    fetchTodos();
    // Fetch users for assignment dropdown (OWNER and MEMBER can assign)
    if (role === "OWNER" || role === "MEMBER") {
      fetchTenantUsers();
    }
  }, [fetchTodos, fetchTenantUsers, role]);

  useEffect(() => {
    let data = [...todos];

    if (filter === "COMPLETED") {
      data = data.filter((t) => t.is_completed);
    }

    if (filter === "PENDING") {
      data = data.filter((t) => !t.is_completed);
    }

    if (filter === "OVERDUE") {
      data = data.filter((t) => t.is_overdue && !t.is_completed);
    }

    if (filter === "RECURRING") {
      data = data.filter((t) => t.recurrence_type && t.recurrence_type !== "NONE");
    }

    if (filter === "MY TASKS") {
      data = data.filter((t) => t.assigned_to_username === currentUsername);
    }

    setFilteredTodos(data);
    setPage(1);
  }, [todos, filter, currentUsername]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;

    // Find current user's ID for auto-assignment
    const currentUser = tenantUsers.find(u => u.username === currentUsername);

    const payload = { 
      title, 
      description,
      recurrence_type: recurrenceType,
    };
    
    // Only include due_date if set
    if (dueDate) {
      payload.due_date = new Date(dueDate).toISOString();
    }

    // Auto-assign to creator if no one selected
    if (assignedTo) {
      payload.assigned_to = parseInt(assignedTo, 10);
    } else if (currentUser) {
      payload.assigned_to = currentUser.id;
    }

    await api.post("todos/", payload);
    setTitle("");
    setDescription("");
    setDueDate("");
    setRecurrenceType("NONE");
    setAssignedTo("");
    fetchTodos();
  };

  const start = (page - 1) * PAGE_SIZE;
  const paginatedTodos = filteredTodos.slice(start, start + PAGE_SIZE);
  const totalPages = Math.ceil(filteredTodos.length / PAGE_SIZE);

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-2xl mx-auto bg-white p-6 rounded shadow">
        <Navbar />

        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">
            Todos <span className="text-sm text-gray-500">({role})</span>
          </h2>
          {isOwner && (
            <button
              onClick={() => setShowTeamManagement(!showTeamManagement)}
              className={`px-4 py-2 rounded text-sm flex items-center gap-2 transition ${
                showTeamManagement 
                  ? "bg-gray-600 text-white hover:bg-gray-700" 
                  : "bg-indigo-600 text-white hover:bg-indigo-700"
              }`}
            >
              <span>👥</span> {showTeamManagement ? "Hide" : "Invite Users"}
            </button>
          )}
        </div>

        {/* Team Management Section - OWNER ONLY */}
        {isOwner && showTeamManagement && (
          <div className="mb-6 p-4 bg-indigo-50 rounded-lg border border-indigo-200">
            <h3 className="text-lg font-semibold text-indigo-800 mb-4">👥 Team Management</h3>
            
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Invite Users Form */}
              <div className="bg-white p-4 rounded-lg border">
                <InviteUsers onUserInvited={handleUserInvited} />
              </div>
              
              {/* Team Members List */}
              <div className="bg-white p-4 rounded-lg border">
                <TenantUsersList refreshKey={teamRefreshKey} />
              </div>
            </div>
          </div>
        )}

        {/* ✅ OWNER + MEMBER – Create todo */}
        {(role === "OWNER" || role === "MEMBER") && (
          <form onSubmit={handleCreate} className="mb-6 mt-4 p-4 bg-gray-50 rounded-lg border" autoComplete="off">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Create New Todo</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
              <input
                className="border px-3 py-2 rounded w-full"
                placeholder="Title *"
                value={title}
                required
                onChange={(e) => setTitle(e.target.value)}
                autoComplete="off"
              />
              <input
                className="border px-3 py-2 rounded w-full"
                placeholder="Description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                autoComplete="off"
              />
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Due Date</label>
                <input
                  type="datetime-local"
                  className="border px-3 py-2 rounded w-full text-sm"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Recurrence</label>
                <select
                  className="border px-3 py-2 rounded w-full text-sm"
                  value={recurrenceType}
                  onChange={(e) => setRecurrenceType(e.target.value)}
                >
                  <option value="NONE">No Repeat</option>
                  <option value="DAILY">Daily</option>
                  <option value="WEEKLY">Weekly</option>
                  <option value="MONTHLY">Monthly</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Assign To (optional)</label>
                <select
                  className="border px-3 py-2 rounded w-full text-sm"
                  value={assignedTo}
                  onChange={(e) => setAssignedTo(e.target.value)}
                >
                  <option value="">Select</option>
                  {tenantUsers
                    .filter((user) => user.role !== "VIEWER" && user.username !== currentUsername)
                    .map((user) => (
                      <option key={user.id} value={user.id}>
                        {user.username} ({user.role})
                      </option>
                    ))}
                </select>
              </div>
              <div className="flex items-end">
                <button className="bg-green-600 text-white px-6 py-2 rounded hover:bg-green-700 w-full">
                  + Create Todo
                </button>
              </div>
            </div>
          </form>
        )}

        {/* Filters */}
        <div className="flex flex-wrap gap-2 mb-4">
          {["ALL", "PENDING", "COMPLETED", "OVERDUE", "RECURRING", ...(role !== "VIEWER" ? ["MY TASKS"] : [])].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded text-sm ${
                filter === f 
                  ? f === "OVERDUE" 
                    ? "bg-red-600 text-white" 
                    : f === "RECURRING"
                    ? "bg-purple-600 text-white"
                    : f === "MY TASKS"
                    ? "bg-orange-600 text-white"
                    : "bg-blue-600 text-white" 
                  : "bg-gray-200"
              }`}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Todos list */}
        {paginatedTodos.length === 0 ? (
          <p className="text-gray-500 text-sm">No todos found</p>
        ) : (
          paginatedTodos.map((todo) => (
            <TodoItem key={todo.id} todo={todo} onChange={fetchTodos} tenantUsers={tenantUsers} />
          ))
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex justify-center gap-4 mt-4">
            <button
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
              className="px-3 py-1 bg-gray-200 rounded disabled:opacity-50"
            >
              Prev
            </button>
            <span className="text-sm">
              Page {page} of {totalPages}
            </span>
            <button
              disabled={page === totalPages}
              onClick={() => setPage(page + 1)}
              className="px-3 py-1 bg-gray-200 rounded disabled:opacity-50"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default Todos;
