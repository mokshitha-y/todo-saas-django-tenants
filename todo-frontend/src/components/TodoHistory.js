import React, { useEffect, useState } from "react";
import api from "../api/axios";

export default function TodoHistory({ todoId, onClose }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!todoId) return;
    setLoading(true);
    api
      .get(`todos/${todoId}/history/`)
      .then((res) => {
        // Handle both paginated and non-paginated responses
        const data = res.data.results || res.data;
        setEntries(Array.isArray(data) ? data : []);
      })
      .catch((err) => setError(err))
      .finally(() => setLoading(false));
  }, [todoId]);

  return (
    <div className="p-4 bg-white border rounded shadow-md mt-3">
      <div className="flex justify-between items-center mb-2">
        <h3 className="font-semibold">Change History</h3>
        <button
          onClick={onClose}
          className="text-sm text-gray-500 hover:underline"
        >
          Close
        </button>
      </div>

      {loading && <div className="text-sm text-gray-500">Loading...</div>}
      {error && (
        <div className="text-sm text-red-500">Failed to load history</div>
      )}

      {!loading && entries.length === 0 && (
        <div className="text-sm text-gray-500">No history found.</div>
      )}

      <ul className="mt-2 space-y-2">
        {entries.map((e) => (
          <li key={e.history_id || `${e.history_date}-${Math.random()}`} className="border p-2 rounded">
            <div className="text-xs text-gray-500">{new Date(e.history_date).toLocaleString()}</div>
            <div className="text-sm font-medium">{e.history_type}</div>
            <div className="text-sm text-gray-700">{e.title}</div>
            <div className="text-xs text-gray-600">Completed: {String(e.is_completed)}</div>
            <div className="text-xs text-gray-600">By: {e.history_user || e.history_user_id || 'system'}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}
