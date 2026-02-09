import { useState } from "react";
import api from "../api/axios";
import TodoHistory from "./TodoHistory";

function TodoItem({ todo, onChange, tenantUsers = [] }) {
  const role = localStorage.getItem("role");
  const username = localStorage.getItem("username");

  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(todo.title);
  const [description, setDescription] = useState(todo.description);
  const [dueDate, setDueDate] = useState(todo.due_date ? todo.due_date.slice(0, 16) : "");
  const [recurrenceType, setRecurrenceType] = useState(todo.recurrence_type || "NONE");
  const [assignedTo, setAssignedTo] = useState(todo.assigned_to || "");
  const [loading, setLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const canEdit =
    role === "OWNER" ||
    (role === "MEMBER" && todo.created_by.username === username);

  // History visibility: Owner sees all, Member sees own only, Viewer sees none
  const canViewHistory =
    role === "OWNER" ||
    (role === "MEMBER" && todo.created_by.username === username);

  const toggleStatus = async () => {
    try {
      setLoading(true);
      await api.patch(`todos/${todo.id}/`, {
        is_completed: !todo.is_completed,
      });
      onChange();
    } catch (err) {
      alert("Failed to update status");
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async () => {
    const payload = { title, description, recurrence_type: recurrenceType };
    if (dueDate) {
      payload.due_date = new Date(dueDate).toISOString();
    } else {
      payload.due_date = null;
    }
    // Handle assigned_to - can be set or unset
    payload.assigned_to = assignedTo ? parseInt(assignedTo, 10) : null;
    
    await api.put(`todos/${todo.id}/`, payload);
    setEditing(false);
    onChange();
  };

  const handleDelete = async () => {
    await api.delete(`todos/${todo.id}/`);
    onChange();
  };

  // Format due date for display
  const formatDueDate = (dateStr) => {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div
      className={`border rounded-lg p-4 mb-3 hover:shadow transition ${
        todo.is_overdue && !todo.is_completed
          ? "bg-red-50 border-red-300"
          : "bg-gray-50"
      }`}
    >
      {editing ? (
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <input
              className="border px-3 py-2 rounded"
              placeholder="Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <input
              className="border px-3 py-2 rounded"
              placeholder="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
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
              <label className="block text-xs text-gray-500 mb-1">Assign To</label>
              <select
                className="border px-3 py-2 rounded w-full text-sm"
                value={assignedTo}
                onChange={(e) => setAssignedTo(e.target.value)}
              >
                {tenantUsers
                  .filter((user) => user.role !== "VIEWER")
                  .map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.username} ({user.role})
                    </option>
                  ))}
              </select>
            </div>
          </div>

          <div className="flex gap-2 mt-2">
            <button
              onClick={handleUpdate}
              className="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700"
            >
              Save
            </button>
            <button
              onClick={() => setEditing(false)}
              className="bg-gray-300 px-3 py-1 rounded hover:bg-gray-400"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="flex items-center gap-2 flex-wrap">
            <h4
              className={`font-semibold ${
                todo.is_completed
                  ? "line-through text-gray-400"
                  : todo.is_overdue
                  ? "text-red-700"
                  : ""
              }`}
            >
              {todo.title}
            </h4>
            {todo.is_overdue && !todo.is_completed && (
              <span className="bg-red-500 text-white text-xs px-2 py-0.5 rounded-full font-medium">
                OVERDUE
              </span>
            )}
            {todo.recurrence_type && todo.recurrence_type !== "NONE" && (
              <span className="bg-purple-100 text-purple-700 text-xs px-2 py-0.5 rounded-full font-medium">
                🔁 {todo.recurrence_type}
              </span>
            )}
            {todo.assigned_to_username && (
              <span className="bg-orange-100 text-orange-700 text-xs px-2 py-0.5 rounded-full font-medium">
                👤 {todo.assigned_to_username}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-600">{todo.description}</p>
          {todo.due_date && (
            <p
              className={`text-xs mt-1 ${
                todo.is_overdue && !todo.is_completed
                  ? "text-red-600 font-medium"
                  : "text-gray-500"
              }`}
            >
              📅 Due: {formatDueDate(todo.due_date)}
            </p>
          )}
        </>
      )}

      {/* 🔐 ROLE BASED CONTROLS */}
      {!editing && (
        <div className="flex gap-3 mt-3 items-center">
          {/* OWNER + MEMBER (own todos only) */}
          {canEdit && (
            <>
              <button
                onClick={() => setEditing(true)}
                className="text-blue-600 text-sm hover:underline"
              >
                Edit
              </button>

              <button
                onClick={toggleStatus}
                disabled={loading}
                className="text-green-600 text-sm hover:underline disabled:opacity-50"
              >
                {todo.is_completed ? "Mark Pending" : "Mark Completed"}
              </button>
            </>
          )}

          {/* OWNER ONLY */}
          {role === "OWNER" && (
            <button
              onClick={handleDelete}
              className="text-red-600 text-sm hover:underline"
            >
              Delete
            </button>
          )}

          {/* VIEWER */}
          {role === "VIEWER" && (
            <span className="text-xs text-gray-400">View only</span>
          )}

          {/* History - OWNER: all todos, MEMBER: own todos only, VIEWER: none */}
          {canViewHistory && (
            <button
              onClick={() => setShowHistory((s) => !s)}
              className="ml-auto text-sm text-gray-600 hover:underline"
            >
              {showHistory ? "Hide history" : "View history"}
            </button>
          )}
        </div>
      )}

      {showHistory && <TodoHistory todoId={todo.id} onClose={() => setShowHistory(false)} />}
    </div>
  );
}

export default TodoItem;
