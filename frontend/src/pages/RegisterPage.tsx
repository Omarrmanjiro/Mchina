import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export function RegisterPage() {
  const { isAuthenticated, register, login } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [phone, setPhone] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await register({
        email: email.trim(),
        password,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        phone: phone.trim() || undefined,
      })
      await login(email.trim(), password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page narrow">
      <div className="card text-center">
        <h1 style={{ fontSize: '2rem' }}>Create an account</h1>
        <p className="lede" style={{ margin: '0 auto' }}>
          Save searches and see who else is travelling the same way.
        </p>
        <form className="form" onSubmit={onSubmit} style={{ textAlign: 'left', marginTop: '2rem' }}>
          <div className="form row-fields">
            <label className="field">
              <span>First name</span>
              <input
                value={firstName}
                onChange={(ev) => setFirstName(ev.target.value)}
                autoComplete="given-name"
                required
              />
            </label>
            <label className="field">
              <span>Last name</span>
              <input
                value={lastName}
                onChange={(ev) => setLastName(ev.target.value)}
                autoComplete="family-name"
                required
              />
            </label>
          </div>
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(ev) => setEmail(ev.target.value)}
              autoComplete="email"
              required
            />
          </label>
          <label className="field">
            <span>Phone (optional)</span>
            <input
              type="tel"
              value={phone}
              onChange={(ev) => setPhone(ev.target.value)}
              autoComplete="tel"
              required
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(ev) => setPassword(ev.target.value)}
              autoComplete="new-password"
              required
              minLength={6}
            />
          </label>
          {error ? <p className="form-error">{error}</p> : null}
          <button type="submit" className="btn primary block" disabled={loading}>
            {loading ? 'Creating account…' : 'Sign up'}
          </button>
        </form>
        <p className="muted foot">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  )
}
