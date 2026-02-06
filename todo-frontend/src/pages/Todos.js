import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";
import TodoItem from "../components/TodoItem";
import Navbar from "../components/Navbar";
import InviteUsers from "./InviteUsers"; // ✅ FILE EXISTS NOW

const PAGE_SIZE = 5;

function Todos() {
  const [todos, setTodos] = useState([]);
  const [filteredTodos, setFilteredTodos] = useState([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [filter, setFilter] = useState("ALL");
  const [page, setPage] = useState(1);

  const role = localStorage.getItem("role");
  const navigate = useNavigate();

  const fetchTodos = useCallback(async () => {
    try {
      const res = await api.get("todos/");
      setTodos(res.data);
    } catch (err) {
      console.error("Unauthorized, redirecting to login");
      localStorage.clear();
      navigate("/login", { replace: true });
    }
  }, [navigate]);

  useEffect(() => {
    fetchTodos();
  }, [fetchTodos]);

  useEffect(() => {
    let data = [...todos];

    if (filter === "COMPLETED") {
      data = data.filter((t) => t.is_completed);
    }

    if (filter === "PENDING") {
      data = data.filter((t) => !t.is_completed);
    }

    setFilteredTodos(data);
    setPage(1);
  }, [todos, filter]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;

    await api.post("todos/", { title, description });
    setTitle("");
    setDescription("");
    fetchTodos();
  };

  const start = (page - 1) * PAGE_SIZE;
  const paginatedTodos = filteredTodos.slice(start, start + PAGE_SIZE);
  const totalPages = Math.ceil(filteredTodos.length / PAGE_SIZE);

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-2xl mx-auto bg-white p-6 rounded shadow">
        <Navbar />

        <h2 className="text-xl font-semibold mb-4">
          Todos <span className="text-sm text-gray-500">({role})</span>
        </h2>

        {/* ✅ OWNER ONLY */}
        {role === "OWNER" && <InviteUsers />}

        {/* ✅ OWNER + MEMBER */}
        {(role === "OWNER" || role === "MEMBER") && (
          <form onSubmit={handleCreate} className="flex gap-2 mb-4 mt-4">
            <input
              className="flex-1 border px-3 py-2 rounded"
              placeholder="Title"
              value={title}
              required
              onChange={(e) => setTitle(e.target.value)}
            />
            <input
              className="flex-1 border px-3 py-2 rounded"
              placeholder="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <button className="bg-green-600 text-white px-4 rounded hover:bg-green-700">
              Create
            </button>
          </form>
        )}

        <div className="flex gap-2 mb-4">
          {["ALL", "PENDING", "COMPLETED"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded ${
                filter === f ? "bg-blue-600 text-white" : "bg-gray-200"
              }`}
            >
              {f}
            </button>
          ))}
        </div>

        {paginatedTodos.length === 0 ? (
          <p className="text-gray-500 text-sm">No todos found</p>
        ) : (
          paginatedTodos.map((todo) => (
            <TodoItem key={todo.id} todo={todo} onChange={fetchTodos} />
          ))
        )}

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
