import { Link, NavLink } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from '../context/AuthContext'

export function Layout({ children }: { children: ReactNode }) {
  const { token, email, isPro, logout } = useAuth()

  return (
    <div className="app-shell">
      <header className="top-bar">
        <Link to={token ? '/' : '/login'} className="brand">
          Mchina
        </Link>
        <nav className="nav-actions">
          {token ? (
            <>
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  isActive ? 'nav-link active' : 'nav-link'
                }
              >
                Planner
              </NavLink>
              {!isPro && (
                <NavLink
                  to="/pricing"
                  className={({ isActive }) =>
                    isActive ? 'nav-link active' : 'nav-link'
                  }
                >
                  Pricing
                </NavLink>
              )}
              <Link to="/profile" className="user-chip" title="Edit Profile">
                {email}
              </Link>
              {isPro && <span className="pro-badge small">PRO</span>}
              <button type="button" className="btn ghost" onClick={logout} style={{ padding: '0.4rem 0.8rem' }}>
                Log out
              </button>
            </>
          ) : (
            <>
              <NavLink
                to="/login"
                className={({ isActive }) =>
                  isActive ? 'nav-link active' : 'nav-link'
                }
              >
                Log in
              </NavLink>
              <NavLink
                to="/register"
                className={({ isActive }) =>
                  isActive ? 'nav-link cta active' : 'nav-link cta'
                }
              >
                Sign up
              </NavLink>
            </>
          )}
        </nav>
      </header>
      <main className="main">{children}</main>
    </div>
  )
}
