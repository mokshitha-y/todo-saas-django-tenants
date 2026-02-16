import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000/api/";

function AcceptInvitation() {
  const { token } = useParams();
  
  const [invitation, setInvitation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const validateToken = async () => {
      try {
        const response = await axios.get(`${API_BASE}customers/invitations/${token}/`);
        setInvitation(response.data);
        setError("");
      } catch (err) {
        setError(err.response?.data?.error || "Invalid or expired invitation link");
      } finally {
        setLoading(false);
      }
    };

    if (token) {
      validateToken();
    }
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="bg-white p-8 rounded-lg shadow-md text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Validating invitation...</p>
        </div>
      </div>
    );
  }

  // Invitation was already processed (user created via Keycloak flow)
  if (invitation?.status === "ACCEPTED") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="bg-white p-8 rounded-lg shadow-md max-w-md w-full text-center">
          <div className="text-green-500 mb-4">
            <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-800 mb-2">Your Account is Ready!</h1>
          <p className="text-gray-600 mb-4">
            You have been invited to join <strong>{invitation?.organization}</strong>
          </p>
          
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 text-left">
            <h3 className="font-semibold text-blue-800 mb-2">Check Your Email</h3>
            <p className="text-sm text-blue-700">
              We sent a password setup link to <strong>{invitation?.email}</strong>.
              Click that link to set your password and complete your account setup.
            </p>
          </div>

          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-6 text-left">
            <h3 className="font-semibold text-gray-700 mb-2">Did not receive the email?</h3>
            <p className="text-sm text-gray-600">
              Go to the login page and click <strong>Forgot Password</strong> with your email address
              to receive a new password reset link.
            </p>
          </div>

          <Link
            to="/login"
            className="w-full block bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition text-center"
          >
            Go to Login
          </Link>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="bg-white p-8 rounded-lg shadow-md max-w-md w-full text-center">
          <div className="text-red-500 mb-4">
            <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-800 mb-2">Invitation Issue</h1>
          <p className="text-gray-600 mb-6">{error}</p>
          
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-6 text-left">
            <p className="text-sm text-gray-600">
              If you were expecting an invitation, please contact the organization owner
              or try using <strong>Forgot Password</strong> on the login page.
            </p>
          </div>

          <Link
            to="/login"
            className="text-blue-600 hover:underline"
          >
            Go to Login
          </Link>
        </div>
      </div>
    );
  }

  // Valid pending invitation (rare with new flow)
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="bg-white p-8 rounded-lg shadow-md max-w-md w-full text-center">
        <div className="text-blue-500 mb-4">
          <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-gray-800 mb-2">Check Your Email</h1>
        <p className="text-gray-600 mb-4">
          You have been invited to join <strong>{invitation?.organization}</strong>
          {invitation?.role && <> as a <strong>{invitation?.role}</strong></>}.
        </p>
        
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 text-left">
          <p className="text-sm text-blue-700">
            Look for an email from our authentication system with a link to set your password.
            Once you set your password, you can log in normally.
          </p>
        </div>

        <Link
          to="/login"
          className="text-blue-600 hover:underline"
        >
          Go to Login
        </Link>
      </div>
    </div>
  );
}

export default AcceptInvitation;
