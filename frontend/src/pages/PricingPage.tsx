import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { subscribe } from '../api/client'

export function PricingPage() {
  const { isAuthenticated, isPro, upgradeToProLocally } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: '/pricing' }} />
  }

  if (isPro) {
    return (
      <div className="page narrow">
        <div className="card text-center" style={{ padding: '3rem 2rem' }}>
          <div className="pro-badge large">Pro Active</div>
          <h1 style={{ marginTop: '1rem' }}>You're all set!</h1>
          <p className="muted">You have full access to public searches.</p>
          <button className="btn primary block" onClick={() => navigate('/')} style={{ marginTop: '2rem' }}>
            Go to Planner
          </button>
        </div>
      </div>
    )
  }

  async function handleSubscribe() {
    if (!isAuthenticated) return
    setLoading(true)
    setError(null)
    try {
      await subscribe()
      upgradeToProLocally()
      // Optional: navigate back to planner immediately or let them see the success state
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Subscription failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="hero-block text-center" style={{ marginBottom: '2rem' }}>
        <h1>Upgrade to Mchina Pro</h1>
        <p className="lede">
          Unlock the full power of crowdsourced travel routes.
        </p>
      </div>

      <div className="grid two pricing-grid">
        {/* Free Tier */}
        <div className="card panel pricing-card">
          <h2>Free</h2>
          <div className="price">
            <span className="amount">0</span>
            <span className="currency">MAD</span>
            <span className="period">/ forever</span>
          </div>
          <ul className="feature-list">
            <li><span className="check">✓</span> Plan unlimited routes with A*</li>
            <li><span className="check">✓</span> See exact distance & stops</li>
            <li><span className="check">✓</span> Find personal matches for your trips</li>
            <li className="muted"><span className="cross">✕</span> Browse all public searches</li>
            <li className="muted"><span className="cross">✕</span> View contact info of public trips</li>
          </ul>
          <button className="btn ghost block" disabled>
            Current Plan
          </button>
        </div>

        {/* Pro Tier */}
        <div className="card panel pricing-card pro">
          <div className="pro-glow"></div>
          <h2>Pro</h2>
          <div className="price">
            <span className="amount">49</span>
            <span className="currency">MAD</span>
            <span className="period">/ month</span>
          </div>
          <ul className="feature-list">
            <li><span className="check">✓</span> Everything in Free</li>
            <li><span className="check">✓</span> <strong>Browse all public searches</strong></li>
            <li><span className="check">✓</span> <strong>View contact info of public trips</strong></li>
            <li><span className="check">✓</span> Priority matching</li>
          </ul>
          {error && <p className="form-error" style={{ marginBottom: '1rem' }}>{error}</p>}
          <button 
            className="btn primary block" 
            onClick={handleSubscribe} 
            disabled={loading}
          >
            {loading ? 'Processing...' : 'Subscribe Now'}
          </button>
        </div>
      </div>
    </div>
  )
}
