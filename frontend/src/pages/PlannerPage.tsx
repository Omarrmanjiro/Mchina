import { useEffect, useMemo, useState } from 'react'
import {
  fetchCities,
  fetchPath,
  fetchPublicSearches,
  saveSearch,
} from '../api/client'
import type {
  CitiesResponse,
  MatchDTO,
  PathResult,
  PublicSearchDTO,
} from '../api/types'
import { MapView } from '../components/MapView'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

export function PlannerPage() {
  const { token } = useAuth()
  const [cityNames, setCityNames] = useState<string[]>([])
  const [cities, setCities] = useState<CitiesResponse | null>(null)
  const [citiesError, setCitiesError] = useState<string | null>(null)
  const [start, setStart] = useState('')
  const [goal, setGoal] = useState('')
  const [pathResult, setPathResult] = useState<PathResult | null>(null)
  const [matches, setMatches] = useState<MatchDTO[] | null>(null)
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null)
  const [isPublic, setIsPublic] = useState(true)
  const [comment, setComment] = useState('')

  const [publicWindow, setPublicWindow] = useState<'1h' | '6h' | '1d'>('1h')
  const [publicSearches, setPublicSearches] = useState<PublicSearchDTO[] | null>(
    null,
  )
  const [publicSelectedId, setPublicSelectedId] = useState<number | null>(null)
  const [publicError, setPublicError] = useState<string | null>(null)
  const [publicLoading, setPublicLoading] = useState(false)
  const [pathLoading, setPathLoading] = useState(false)
  const [saveLoading, setSaveLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const data = await fetchCities()
        if (cancelled) return
        setCities(data)
        const names = Object.keys(data).sort()
        setCityNames(names)
        if (names.length >= 2) {
          setStart(names[0] ?? '')
          setGoal(names[1] ?? '')
        }
      } catch (err) {
        if (!cancelled) {
          setCitiesError(
            err instanceof Error ? err.message : 'Could not load cities',
          )
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    setPublicLoading(true)
    setPublicError(null)
    ;(async () => {
      try {
        if (!token) return
        const list = await fetchPublicSearches(token, publicWindow)
        if (!cancelled) {
          setPublicSearches(list)
          setPublicSelectedId(null)
        }
      } catch (err) {
        if (!cancelled) {
          setPublicError(
            err instanceof Error ? err.message : 'Could not load public searches',
          )
        }
      } finally {
        if (!cancelled) setPublicLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [publicWindow, token])

  const canCompute = useMemo(
    () =>
      Boolean(token) &&
      start &&
      goal &&
      start !== goal &&
      cityNames.includes(start) &&
      cityNames.includes(goal),
    [token, start, goal, cityNames],
  )

  async function onFindPath() {
    if (!token || !canCompute) return
    setError(null)
    setMatches(null)
    setSelectedMatchId(null)
    setComment('')
    setPathLoading(true)
    try {
      const result = await fetchPath(token, start, goal)
      setPathResult(result)
    } catch (err) {
      setPathResult(null)
      setError(err instanceof Error ? err.message : 'Could not compute path')
    } finally {
      setPathLoading(false)
    }
  }

  async function onSaveSearch() {
    if (!token || !pathResult) return
    setError(null)
    setSaveLoading(true)
    try {
      const list = await saveSearch(token, {
        start_city: pathResult.start,
        goal_city: pathResult.goal,
        path: pathResult.path,
        distance: pathResult.distance,
        is_public: isPublic,
        comment: comment.trim() || undefined,
      })
      setMatches(list)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save search')
    } finally {
      setSaveLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="hero-block">
        <h1>Plan your trip</h1>
        <p className="lede">
          Pick two cities. We use A* on the road graph, then you can save the
          trip to see others with the same route idea for ridesharing.
        </p>
      </div>

      {citiesError ? (
        <p className="banner error">{citiesError}</p>
      ) : null}

      <MapView cities={cities} pathResult={pathResult} />

      <div className="grid two">
        <section className="card panel">
          <h2>Route</h2>
          <div className="form row-fields">
            <label className="field">
              <span>From</span>
              <select
                value={start}
                onChange={(ev) => setStart(ev.target.value)}
                disabled={cityNames.length === 0}
              >
                {cityNames.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>To</span>
              <select
                value={goal}
                onChange={(ev) => setGoal(ev.target.value)}
                disabled={cityNames.length === 0}
              >
                {cityNames.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="actions">
            <button
              type="button"
              className="btn primary"
              onClick={onFindPath}
              disabled={!canCompute || pathLoading || saveLoading}
            >
              {pathLoading ? 'Computing…' : 'Find best route'}
            </button>
          </div>
          <label className="toggle">
            <input
              type="checkbox"
              checked={isPublic}
              onChange={(e) => setIsPublic(e.target.checked)}
            />{' '}
            Save as public (others can see it)
          </label>
          {error ? <p className="form-error">{error}</p> : null}
        </section>

        <section className="card panel">
          <h2>Result</h2>
          {!pathResult ? (
            <p className="muted">
              Run a search to see the ordered cities, total distance, and nodes
              visited by the algorithm.
            </p>
          ) : (
            <>
              <dl className="stats">
                <div>
                  <dt>Distance</dt>
                  <dd>{pathResult.distance.toFixed(2)} km</dd>
                </div>
                <div>
                  <dt>Stops</dt>
                  <dd>{pathResult.path.length}</dd>
                </div>
              </dl>
              <p className="path-line">{pathResult.path.join(' → ')}</p>
              <details className="visited">
                <summary>Visited order (A*)</summary>
                <ol>
                  {pathResult.visited.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ol>
              </details>
              <label className="field" style={{ marginBottom: '1rem' }}>
                <span>Note for others (optional)</span>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="e.g. Leaving tomorrow at 8am, have space for 2"
                  rows={2}
                />
              </label>
              <button
                type="button"
                className="btn secondary block"
                onClick={onSaveSearch}
                disabled={pathLoading || saveLoading}
              >
                {saveLoading ? 'Saving…' : 'Save trip & find matches'}
              </button>
            </>
          )}
        </section>
      </div>

      {matches ? (
        <section className="card panel matches">
          <h2>People with the same trip</h2>
          {!useAuth().isPro ? (
            <div className="paywall-overlay" style={{ minHeight: '200px' }}>
              <div className="paywall-content" style={{ padding: '1.5rem' }}>
                <h3>Unlock Matches</h3>
                <p>Upgrade to Pro to see other travellers taking this exact trip and connect for ridesharing.</p>
                <Link to="/pricing" className="btn primary block">Learn about Pro</Link>
              </div>
              <div className="paywall-blur">
                <ul className="match-list" style={{ opacity: 0.5 }}>
                  <li className="match-wrapper">
                    <button type="button" className="match">
                      <div className="match-head">
                        <strong>Hidden Traveller</strong>
                        <span className="muted small">Just now</span>
                      </div>
                    </button>
                  </li>
                  <li className="match-wrapper">
                    <button type="button" className="match">
                      <div className="match-head">
                        <strong>Hidden Traveller</strong>
                        <span className="muted small">2 hours ago</span>
                      </div>
                    </button>
                  </li>
                </ul>
              </div>
            </div>
          ) : matches.length === 0 ? (
            <p className="muted">
              No other travellers yet for {pathResult?.start} →{' '}
              {pathResult?.goal}. Try again after more people search this pair.
            </p>
          ) : (
            <ul className="match-list">
              {matches.map((m) => {
                const matchId = `${m.user_full_name}-${m.created_at}`
                const isSelected = selectedMatchId === matchId
                return (
                  <li key={matchId} className="match-wrapper">
                    <button
                      type="button"
                      className={`match ${isSelected ? 'selected' : ''}`}
                      onClick={() =>
                        setSelectedMatchId((prev) => (prev === matchId ? null : matchId))
                      }
                    >
                      <div className="match-head">
                        <strong>{m.user_full_name}</strong>
                        <span className="muted small">
                          {formatDate(m.created_at)}
                        </span>
                      </div>
                      
                      {isSelected && (
                        <div className="match-detail">
                          {m.comment && (
                            <div className="match-comment">"{m.comment}"</div>
                          )}
                          <div className="match-info">
                            <p><strong>Route:</strong> {m.path.join(' → ')}</p>
                            <p><strong>Distance:</strong> {m.distance.toFixed(2)} km</p>
                            {m.user_phone ? (
                              <p><strong>Contact:</strong> <a href={`tel:${m.user_phone}`}>{m.user_phone}</a></p>
                            ) : (
                              <p className="muted small">No phone number shared.</p>
                            )}
                          </div>
                        </div>
                      )}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      ) : null}

      <section className="card panel">
        <div className="public-head">
          <div>
            <h2>Public searches</h2>
            <p className="muted small">
              Browse searches saved as public. Click one to see the traveller
              info.
            </p>
          </div>
          <label className="field">
            <span>Time window</span>
            <select
              value={publicWindow}
              onChange={(e) =>
                setPublicWindow(e.target.value as '1h' | '6h' | '1d')
              }
            >
              <option value="1h">Last 1 hour</option>
              <option value="6h">Last 6 hours</option>
              <option value="1d">Last 1 day</option>
            </select>
          </label>
        </div>

        {publicError ? <p className="form-error">{publicError}</p> : null}
        
        {!useAuth().isPro ? (
          <div className="paywall-overlay">
            <div className="paywall-content">
              <h3>Unlock Public Searches</h3>
              <p>Upgrade to Pro to see where everyone else is traveling and find even more carpool opportunities.</p>
              <Link to="/pricing" className="btn primary block">Learn about Pro</Link>
            </div>
            <div className="paywall-blur">
              <div className="public-grid" style={{ opacity: 0.5 }}>
                 <ul className="public-list">
                    <li className="public-item"><div className="public-item-top"><strong>Casablanca → Rabat</strong></div><div className="muted small">86.2 km</div></li>
                    <li className="public-item"><div className="public-item-top"><strong>Marrakech → Agadir</strong></div><div className="muted small">245.1 km</div></li>
                    <li className="public-item"><div className="public-item-top"><strong>Tangier → Tetouan</strong></div><div className="muted small">55.0 km</div></li>
                 </ul>
              </div>
            </div>
          </div>
        ) : publicLoading ? (
          <p className="muted">Loading…</p>
        ) : publicSearches && publicSearches.length === 0 ? (
          <p className="muted">No public searches in this time window yet.</p>
        ) : publicSearches ? (
          <div className="public-grid">
            <ul className="public-list">
              {publicSearches.map((s) => {
                const selected = publicSelectedId === s.id
                return (
                  <li key={s.id}>
                    <button
                      type="button"
                      className={selected ? 'public-item selected' : 'public-item'}
                      onClick={() =>
                        setPublicSelectedId((prev) => (prev === s.id ? null : s.id))
                      }
                    >
                      <div className="public-item-top">
                        <strong>
                          {s.start_city} → {s.goal_city}
                        </strong>
                        <span className="muted small">{formatDate(s.created_at)}</span>
                      </div>
                      <div className="muted small">
                        {s.distance.toFixed(2)} km · {s.path.length} stops
                      </div>
                    </button>
                  </li>
                )
              })}
            </ul>
            <div className="public-details">
              {publicSelectedId ? (
                (() => {
                  const s = publicSearches.find((x) => x.id === publicSelectedId)
                  if (!s) return <p className="muted">Select a search.</p>
                  return (
                    <div className="card inner">
                      <h2>Traveller info</h2>
                      <p className="muted">
                        {s.user_first_name ?? '—'} {s.user_last_name ?? ''}
                      </p>
                      {s.comment && (
                        <div className="match-comment" style={{ marginTop: '0.5rem', marginBottom: '1rem' }}>
                          "{s.comment}"
                        </div>
                      )}
                      {s.user_phone ? (
                        <p>
                          <a href={`tel:${s.user_phone}`}>{s.user_phone}</a>
                        </p>
                      ) : (
                        <p className="muted">No phone number shared.</p>
                      )}
                      <hr className="sep" />
                      <h2>Route</h2>
                      <p className="path-line">{s.path.join(' → ')}</p>
                    </div>
                  )
                })()
              ) : (
                <p className="muted">Click a public search to see details.</p>
              )}
            </div>
          </div>
        ) : null}
      </section>
    </div>
  )
}
