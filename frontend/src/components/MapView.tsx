import { useEffect, useMemo } from 'react'
import {
  MapContainer,
  Marker,
  Polyline,
  Popup,
  TileLayer,
  useMap,
} from 'react-leaflet'
import L, { type LatLngBoundsExpression, type LatLngExpression } from 'leaflet'

import markerIcon2xUrl from 'leaflet/dist/images/marker-icon-2x.png'
import markerIconUrl from 'leaflet/dist/images/marker-icon.png'
import markerShadowUrl from 'leaflet/dist/images/marker-shadow.png'

import type { CitiesResponse, PathResult } from '../api/types'

const defaultIcon = L.icon({
  iconRetinaUrl: markerIcon2xUrl,
  iconUrl: markerIconUrl,
  shadowUrl: markerShadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})

L.Marker.prototype.options.icon = defaultIcon

type Point = [number, number]

function FitBounds({
  bounds,
}: {
  bounds: LatLngBoundsExpression | null
}) {
  const map = useMap()
  useEffect(() => {
    if (!bounds) return
    map.fitBounds(bounds, { padding: [30, 30] })
  }, [map, bounds])
  return null
}

export function MapView({
  cities,
  pathResult,
}: {
  cities: CitiesResponse | null
  pathResult: PathResult | null
}) {
  const allPoints = useMemo(() => {
    if (!cities) return []
    return Object.values(cities).map((c) => [c.lat, c.lon] as Point)
  }, [cities])

  const routePoints = useMemo(() => {
    if (!cities || !pathResult) return null
    const pts: Point[] = []
    for (const name of pathResult.path) {
      const city = cities[name]
      if (!city) continue
      pts.push([city.lat, city.lon])
    }
    return pts.length >= 2 ? pts : null
  }, [cities, pathResult])

  const fitBounds = useMemo(() => {
    if (routePoints && routePoints.length >= 2) {
      return L.latLngBounds(routePoints)
    }
    if (allPoints.length >= 2) {
      return L.latLngBounds(allPoints)
    }
    return null
  }, [routePoints, allPoints])

  const center: LatLngExpression = routePoints?.[0] ?? [31.7917, -7.0926]
  const zoom = routePoints ? 6 : 5

  return (
    <div className="map-card">
      <div className="map-head">
        <h2>Map</h2>
        <p className="muted small">
          {pathResult
            ? `Route: ${pathResult.start} → ${pathResult.goal}`
            : 'Select cities to see the route highlighted.'}
        </p>
      </div>

      <div className="map-wrap">
        <MapContainer
          center={center}
          zoom={zoom}
          scrollWheelZoom
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution="&copy; OpenStreetMap contributors"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <FitBounds bounds={fitBounds} />

          {cities
            ? Object.entries(cities).map(([name, c]) => (
                <Marker key={name} position={[c.lat, c.lon]}>
                  <Popup>
                    <strong>{c.name}</strong>
                    <div className="muted small">
                      {c.lat.toFixed(4)}, {c.lon.toFixed(4)}
                    </div>
                  </Popup>
                </Marker>
              ))
            : null}

          {routePoints ? (
            <Polyline
              positions={routePoints as LatLngExpression[]}
              pathOptions={{ color: '#C48A5A', weight: 5, opacity: 0.95 }}
            />
          ) : null}
        </MapContainer>
      </div>
    </div>
  )
}

