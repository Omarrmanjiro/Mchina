import { useEffect, useState } from 'react'
import { fetchMe, updateMe } from '../api/client'
import { useAuth } from '../context/AuthContext'

export function ProfilePage() {
  const { token, email } = useAuth()
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [phone, setPhone] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function loadProfile() {
      if (!token) return
      try {
        const user = await fetchMe(token)
        if (!cancelled) {
          setFirstName(user.first_name || '')
          setLastName(user.last_name || '')
          setPhone(user.phone || '')
          setLoading(false)
        }
      } catch (err) {
        if (!cancelled) {
          setError('Failed to load profile')
          setLoading(false)
        }
      }
    }
    loadProfile()
    return () => {
      cancelled = true
    }
  }, [token])

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    if (!token) return
    setSaving(true)
    setError(null)
    setSuccess(false)
    try {
      await updateMe(token, {
        first_name: firstName,
        last_name: lastName,
        phone: phone,
      })
      setSuccess(true)
      // hide success message after a few seconds
      setTimeout(() => setSuccess(false), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update profile')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page narrow">
      <div className="card">
        <div className="text-center">
          <h1>Your Profile</h1>
          <p className="muted">Manage your personal information</p>
        </div>

        {loading ? (
          <p className="text-center muted" style={{ marginTop: '2rem' }}>
            Loading...
          </p>
        ) : (
          <form className="form" onSubmit={handleSave}>
            <label className="field">
              <span>Email Address</span>
              <input type="email" value={email ?? ''} disabled title="Email cannot be changed" />
            </label>
            <div className="row-fields">
              <label className="field">
                <span>First Name</span>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="e.g. John"
                />
              </label>
              <label className="field">
                <span>Last Name</span>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="e.g. Doe"
                />
              </label>
            </div>
            <label className="field">
              <span>Phone Number</span>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="e.g. +212 600 000000"
              />
            </label>

            {error && <p className="form-error">{error}</p>}
            {success && (
              <p
                className="form-error"
                style={{
                  backgroundColor: 'rgba(79, 111, 82, 0.1)',
                  color: 'var(--success)',
                  border: '1px solid rgba(79, 111, 82, 0.2)',
                }}
              >
                Profile updated successfully!
              </p>
            )}

            <div className="actions">
              <button
                type="submit"
                className="btn primary block"
                disabled={saving}
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
