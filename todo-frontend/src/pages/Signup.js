import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";

function Signup() {
  const [formData, setFormData] = useState({
    organization_name: "",
    username: "",
    email: "",
    first_name: "",
    last_name: "",
    password: "",
    confirmPassword: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [validationErrors, setValidationErrors] = useState({});

  const navigate = useNavigate();

  const validateForm = () => {
    const errors = {};

    if (!formData.organization_name.trim()) {
      errors.organization_name = "Organization name is required";
    }

    if (!formData.username.trim()) {
      errors.username = "Username is required";
    } else if (formData.username.length < 3) {
      errors.username = "Username must be at least 3 characters";
    }

    if (!formData.email.trim()) {
      errors.email = "Email is required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      errors.email = "Invalid email format";
    }

    if (!formData.password) {
      errors.password = "Password is required";
    } else if (formData.password.length < 8) {
      errors.password = "Password must be at least 8 characters";
    }

    if (formData.password !== formData.confirmPassword) {
      errors.confirmPassword = "Passwords do not match";
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
    // Clear validation error for this field
    if (validationErrors[name]) {
      setValidationErrors((prev) => ({
        ...prev,
        [name]: "",
      }));
    }
  };

  const handleSignup = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setError("");
    setLoading(true);

    try {
      const response = await api.post("auth/register/", {
        tenant_name: formData.organization_name,
        username: formData.username,
        email: formData.email,
        first_name: formData.first_name,
        last_name: formData.last_name,
        password: formData.password,
      });

      // Store tokens if provided
      if (response.data.access) {
        // Don't auto-login - require user to login manually
        alert("Account created successfully! Please login with your credentials.");
        navigate("/login");
      } else {
        alert("Account created successfully! Please login.");
        navigate("/login");
      }
    } catch (err) {
      const errorMsg =
        err.response?.data?.error ||
        err.response?.data?.non_field_errors?.[0] ||
        "Signup failed. Please try again.";
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 p-4">
      <form
        onSubmit={handleSignup}
        className="bg-white p-8 rounded-lg shadow-md w-full max-w-md"
        autoComplete="off"
      >
        <h2 className="text-2xl font-bold mb-2 text-center text-gray-800">
          Create Your Account
        </h2>
        <p className="text-gray-600 text-center mb-6">
          Set up a new organization and start managing todos
        </p>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        {/* Organization Name */}
        <div className="mb-4">
          <label className="block text-gray-700 text-sm font-semibold mb-2">
            Organization Name *
          </label>
          <input
            type="text"
            name="organization_name"
            className={`w-full px-3 py-2 border rounded focus:outline-none focus:ring focus:ring-blue-300 ${
              validationErrors.organization_name ? "border-red-500" : ""
            }`}
            placeholder="Your Company Name"
            value={formData.organization_name}
            onChange={handleChange}
            autoComplete="off"
          />
          {validationErrors.organization_name && (
            <p className="text-red-500 text-sm mt-1">
              {validationErrors.organization_name}
            </p>
          )}
        </div>

        {/* Username */}
        <div className="mb-4">
          <label className="block text-gray-700 text-sm font-semibold mb-2">
            Username *
          </label>
          <input
            type="text"
            name="username"
            className={`w-full px-3 py-2 border rounded focus:outline-none focus:ring focus:ring-blue-300 ${
              validationErrors.username ? "border-red-500" : ""
            }`}
            placeholder="Choose a username"
            value={formData.username}
            onChange={handleChange}
            autoComplete="off"
          />
          {validationErrors.username && (
            <p className="text-red-500 text-sm mt-1">
              {validationErrors.username}
            </p>
          )}
        </div>

        {/* Email */}
        <div className="mb-4">
          <label className="block text-gray-700 text-sm font-semibold mb-2">
            Email *
          </label>
          <input
            type="email"
            name="email"
            className={`w-full px-3 py-2 border rounded focus:outline-none focus:ring focus:ring-blue-300 ${
              validationErrors.email ? "border-red-500" : ""
            }`}
            placeholder="your.email@company.com"
            value={formData.email}
            onChange={handleChange}
            autoComplete="off"
          />
          {validationErrors.email && (
            <p className="text-red-500 text-sm mt-1">{validationErrors.email}</p>
          )}
        </div>

        {/* First Name */}
        <div className="mb-4">
          <label className="block text-gray-700 text-sm font-semibold mb-2">
            First Name (Optional)
          </label>
          <input
            type="text"
            name="first_name"
            className="w-full px-3 py-2 border rounded focus:outline-none focus:ring focus:ring-blue-300"
            placeholder="John"
            value={formData.first_name}
            onChange={handleChange}
            autoComplete="off"
          />
        </div>

        {/* Last Name */}
        <div className="mb-4">
          <label className="block text-gray-700 text-sm font-semibold mb-2">
            Last Name (Optional)
          </label>
          <input
            type="text"
            name="last_name"
            className="w-full px-3 py-2 border rounded focus:outline-none focus:ring focus:ring-blue-300"
            placeholder="Doe"
            value={formData.last_name}
            onChange={handleChange}
            autoComplete="off"
          />
        </div>

        {/* Password */}
        <div className="mb-4">
          <label className="block text-gray-700 text-sm font-semibold mb-2">
            Password *
          </label>
          <input
            type="password"
            name="password"
            className={`w-full px-3 py-2 border rounded focus:outline-none focus:ring focus:ring-blue-300 ${
              validationErrors.password ? "border-red-500" : ""
            }`}
            placeholder="At least 8 characters"
            value={formData.password}
            onChange={handleChange}
            autoComplete="new-password"
          />
          {validationErrors.password && (
            <p className="text-red-500 text-sm mt-1">
              {validationErrors.password}
            </p>
          )}
        </div>

        {/* Confirm Password */}
        <div className="mb-6">
          <label className="block text-gray-700 text-sm font-semibold mb-2">
            Confirm Password *
          </label>
          <input
            type="password"
            name="confirmPassword"
            className={`w-full px-3 py-2 border rounded focus:outline-none focus:ring focus:ring-blue-300 ${
              validationErrors.confirmPassword ? "border-red-500" : ""
            }`}
            placeholder="Re-enter your password"
            value={formData.confirmPassword}
            onChange={handleChange}
            autoComplete="new-password"
          />
          {validationErrors.confirmPassword && (
            <p className="text-red-500 text-sm mt-1">
              {validationErrors.confirmPassword}
            </p>
          )}
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-green-600 text-white py-2 rounded font-semibold hover:bg-green-700 transition disabled:opacity-50"
        >
          {loading ? "Creating Account..." : "Create Account"}
        </button>

        <p className="text-sm text-center mt-4 text-gray-600">
          Already have an account?{" "}
          <span
            className="text-blue-600 cursor-pointer hover:underline font-semibold"
            onClick={() => navigate("/login")}
          >
            Login
          </span>
        </p>
      </form>
    </div>
  );
}

export default Signup;
