import { useNavigate } from "react-router-dom";

function Navbar() {
  const role = localStorage.getItem("role");
  const username = localStorage.getItem("username");
  const navigate = useNavigate();

  const logout = () => {
    localStorage.clear();
    navigate("/");
    window.location.reload();
  };

  return (
    <div className="flex justify-between items-center px-6 py-3 bg-gray-900 text-white rounded mb-6">
      <div className="text-lg font-semibold">Todo SaaS</div>

      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-300">
          {username} ({role})
        </span>
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
