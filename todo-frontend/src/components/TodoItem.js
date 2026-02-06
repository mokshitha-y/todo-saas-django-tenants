import { useState } from "react";
import api from "../api/axios";

function TodoItem({ todo, onChange }) {
  const role = localStorage.getItem("role");
  const username = localStorage.getItem("username");

  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(todo.title);
  const [description, setDescription] = useState(todo.description);
  const [loading, setLoading] = useState(false);

  const canEdit =
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
    await api.put(`todos/${todo.id}/`, { title, description });
    setEditing(false);
    onChange();
  };

  const handleDelete = async () => {
    await api.delete(`todos/${todo.id}/`);
    onChange();
  };

  return (
    <div className="border rounded-lg p-4 mb-3 bg-gray-50 hover:shadow transition">
      {editing ? (
        <div className="flex flex-col gap-2">
          <input
            className="border px-3 py-2 rounded"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <input
            className="border px-3 py-2 rounded"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />

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
          <h4
            className={`font-semibold ${
              todo.is_completed ? "line-through text-gray-400" : ""
            }`}
          >
            {todo.title}
          </h4>
          <p className="text-sm text-gray-600">{todo.description}</p>
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
        </div>
      )}
    </div>
  );
}

export default TodoItem;
