import { useEffect, useState } from 'react'
import { adminDeleteUser, adminFetchUsers, adminUpdateUser } from '../api/client'
import type { UserProfile } from '../api/types'

export function AdminPage() {
  const [users, setUsers] = useState<UserProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Search filter
  const [searchQuery, setSearchQuery] = useState('')

  // Edit states
  const [editingUser, setEditingUser] = useState<UserProfile | null>(null)
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [phone, setPhone] = useState('')
  const [isPro, setIsPro] = useState(false)
  const [isAdmin, setIsAdmin] = useState(false)
  const [saveLoading, setSaveLoading] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  // Delete states
  const [deleteLoadingId, setDeleteLoadingId] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    async function loadUsers() {
      try {
        const list = await adminFetchUsers()
        if (!cancelled) {
          setUsers(list)
          setLoading(false)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to fetch users')
          setLoading(false)
        }
      }
    }
    loadUsers()
    return () => {
      cancelled = true
    }
  }, [])

  function startEdit(user: UserProfile) {
    setEditingUser(user)
    setFirstName(user.first_name || '')
    setLastName(user.last_name || '')
    setPhone(user.phone || '')
    setIsPro(user.is_pro)
    setIsAdmin(user.is_admin)
    setSaveSuccess(false)
    setError(null)
  }

  function cancelEdit() {
    setEditingUser(null)
  }

  async function handleSaveEdit(e: React.FormEvent) {
    e.preventDefault()
    if (!editingUser) return
    setSaveLoading(true)
    setError(null)
    setSaveSuccess(false)
    try {
      const updated = await adminUpdateUser(editingUser.id, {
        first_name: firstName,
        last_name: lastName,
        phone: phone,
        is_pro: isPro,
        is_admin: isAdmin,
      })
      
      // Update local state list
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)))
      setSaveSuccess(true)
      setTimeout(() => {
        setSaveSuccess(false)
        setEditingUser(null)
      }, 1500)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update user')
    } finally {
      setSaveLoading(false)
    }
  }

  async function handleDelete(user: UserProfile) {
    if (!window.confirm(`Are you sure you want to delete account: ${user.email}?`)) {
      return
    }
    setDeleteLoadingId(user.id)
    setError(null)
    try {
      await adminDeleteUser(user.id)
      setUsers((prev) => prev.filter((u) => u.id !== user.id))
      if (editingUser?.id === user.id) {
        setEditingUser(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete user')
    } finally {
      setDeleteLoadingId(null)
    }
  }

  const filteredUsers = users.filter((u) => {
    const q = searchQuery.toLowerCase().trim()
    if (!q) return true
    return (
      u.email.toLowerCase().includes(q) ||
      u.full_name.toLowerCase().includes(q) ||
      (u.phone && u.phone.includes(q))
    );
  })

  return (
    <div className="page" style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <div className="hero-block" style={{ padding: '3rem 2rem', background: 'linear-gradient(135deg, var(--secondary-accent) 0%, #1f2937 100%)' }}>
        <h1 style={{ color: '#fff', fontSize: '2.5rem', marginBottom: '0.5rem' }}>Admin Dashboard</h1>
        <p className="lede" style={{ color: 'rgba(255,255,255,0.8)', fontSize: '1.05rem', margin: '0 auto' }}>
          Manage platform accounts, subscriptions, and administrative access.
        </p>
      </div>

      {error && <p className="banner error">{error}</p>}

      <div className="grid two" style={{ gridTemplateColumns: editingUser ? '2fr 1fr' : '1fr', gap: '2rem' }}>
        {/* User list card */}
        <section className="card panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
            <h2>Users ({filteredUsers.length})</h2>
            <input
              type="text"
              placeholder="Search by name, email, phone..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                padding: '0.5rem 1rem',
                borderRadius: '8px',
                border: '1px solid var(--border)',
                background: 'var(--bg)',
                width: '100%',
                maxWidth: '300px',
                fontSize: '0.9rem'
              }}
            />
          </div>

          {loading ? (
            <p className="text-center muted">Loading users list...</p>
          ) : filteredUsers.length === 0 ? (
            <p className="text-center muted">No users found.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '600px' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--border)' }}>
                    <th style={{ padding: '0.75rem 0.5rem', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--muted)' }}>ID</th>
                    <th style={{ padding: '0.75rem 0.5rem', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--muted)' }}>User</th>
                    <th style={{ padding: '0.75rem 0.5rem', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--muted)' }}>Phone</th>
                    <th style={{ padding: '0.75rem 0.5rem', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--muted)' }}>Status</th>
                    <th style={{ padding: '0.75rem 0.5rem', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--muted)', textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map((u) => (
                    <tr key={u.id} style={{ borderBottom: '1px solid var(--border)', transition: 'background 0.2s' }}>
                      <td style={{ padding: '1rem 0.5rem', fontSize: '0.9rem', color: 'var(--muted)' }}>{u.id}</td>
                      <td style={{ padding: '1rem 0.5rem' }}>
                        <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>{u.full_name}</div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--muted)' }}>{u.email}</div>
                      </td>
                      <td style={{ padding: '1rem 0.5rem', fontSize: '0.9rem' }}>{u.phone || <span style={{ fontStyle: 'italic', color: 'var(--muted)' }}>None</span>}</td>
                      <td style={{ padding: '1rem 0.5rem' }}>
                        <div style={{ display: 'flex', gap: '0.4rem' }}>
                          {u.is_pro ? (
                            <span className="pro-badge small" style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem' }}>Pro</span>
                          ) : (
                            <span style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem', background: 'var(--border)', color: 'var(--muted)', borderRadius: '4px', textTransform: 'uppercase', fontWeight: 700 }}>Free</span>
                          )}
                          {u.is_admin && (
                            <span style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem', background: '#3b82f6', color: '#fff', borderRadius: '4px', textTransform: 'uppercase', fontWeight: 700 }}>Admin</span>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: '1rem 0.5rem', textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', gap: '0.5rem' }}>
                          <button
                            type="button"
                            className="btn ghost"
                            onClick={() => startEdit(u)}
                            style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="btn ghost"
                            onClick={() => handleDelete(u)}
                            disabled={deleteLoadingId === u.id}
                            style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem', color: 'var(--danger)', borderColor: 'transparent' }}
                          >
                            {deleteLoadingId === u.id ? 'Deleting...' : 'Delete'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Edit user panel */}
        {editingUser && (
          <section className="card panel" style={{ animation: 'fadeIn 0.3s ease-out' }}>
            <h2 style={{ marginBottom: '1.5rem' }}>Edit User</h2>
            <p className="muted small" style={{ marginTop: '-1rem', marginBottom: '1.5rem' }}>
              Updating details for <strong>{editingUser.email}</strong> (ID: {editingUser.id})
            </p>

            <form onSubmit={handleSaveEdit} className="form" style={{ gap: '1rem' }}>
              <label className="field">
                <span>First Name</span>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="First name"
                />
              </label>

              <label className="field">
                <span>Last Name</span>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="Last name"
                />
              </label>

              <label className="field">
                <span>Phone Number</span>
                <input
                  type="text"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="Phone number"
                />
              </label>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem', marginTop: '1rem', marginBottom: '1rem' }}>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={isPro}
                    onChange={(e) => setIsPro(e.target.checked)}
                  />
                  <span>Pro Subscription Status</span>
                </label>

                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={isAdmin}
                    onChange={(e) => setIsAdmin(e.target.checked)}
                  />
                  <span>Administrator Access</span>
                </label>
              </div>

              {saveSuccess && (
                <p
                  className="form-error"
                  style={{
                    backgroundColor: 'rgba(79, 111, 82, 0.1)',
                    color: 'var(--success)',
                    border: '1px solid rgba(79, 111, 82, 0.2)',
                    textAlign: 'center',
                    padding: '0.5rem'
                  }}
                >
                  Saved successfully!
                </p>
              )}

              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
                <button
                  type="submit"
                  className="btn primary block"
                  disabled={saveLoading}
                >
                  {saveLoading ? 'Saving...' : 'Save'}
                </button>
                <button
                  type="button"
                  className="btn ghost block"
                  onClick={cancelEdit}
                  disabled={saveLoading}
                >
                  Cancel
                </button>
              </div>
            </form>
          </section>
        )}
      </div>
    </div>
  )
}
