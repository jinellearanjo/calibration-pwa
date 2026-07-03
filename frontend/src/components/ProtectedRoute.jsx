import { useState, useEffect } from "react";
import { Navigate } from "react-router-dom";
import { supabase } from "../auth";

/**
 * ProtectedRoute component.
 * Wraps routes that require authentication. Redirects unauthenticated
 * users to the login page. Shows nothing while the session is being checked
 * to avoid a flash of the login page for authenticated users.
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - The protected page component to render.
 */
function ProtectedRoute({ children }) {
  const [session, setSession] = useState(undefined);

  useEffect(() => {
    // Check for an existing session on mount.
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
    });

    // Listen for login and logout events so the route updates automatically.
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session);
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  // Still checking — render nothing to avoid a flash.
  if (session === undefined) return null;

  // No session — redirect to login.
  if (!session) return <Navigate to="/login" replace />;

  // Authenticated — render the child page.
  return children;
}

export default ProtectedRoute;