import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import { useEffect, useMemo } from 'react'
import { Circle, GeoJSON, MapContainer, Marker, Pane, Polygon, Polyline, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import type { Area, AreaInfo, HotspotPoint, RegionInfo } from './api'
import { count } from './format'

const GAMBIA_BOUNDS = L.latLngBounds([13.05, -16.85], [13.85, -13.78])
const DOT_COLOR = '#b8451b'

export type Vertex = [number, number]

interface Props {
  area: Area
  regions: RegionInfo[]
  regionShapes: GeoJSON.FeatureCollection | null
  districtShapes: GeoJSON.FeatureCollection | null
  points: HotspotPoint[]
  /** Vertices of a shape being drawn, as [latitude, longitude]. Null when not drawing. */
  drawing: Vertex[] | null
  pickingCentre: boolean
  streets: boolean
  onSelectRegion: (name: string) => void
  onSelectDistrict: (name: string) => void
  onPickCentre: (latitude: number, longitude: number) => void
  onAddVertex: (vertex: Vertex) => void
}

const nameOf = (feature?: GeoJSON.Feature) => feature?.properties?.shapeName as string | undefined

function label(name: string, strong: boolean) {
  return L.divIcon({ className: `map-label${strong ? ' strong' : ''}`, html: name, iconSize: [0, 0] })
}

/** Hotspots drawn on one canvas. They sit above the shapes and ignore the pointer, so shapes stay clickable. */
function Dots({ points }: { points: HotspotPoint[] }) {
  const map = useMap()
  useEffect(() => {
    const renderer = L.canvas({ pane: 'dots', padding: 0.5 })
    const group = L.layerGroup(
      points.map(([latitude, longitude]) =>
        L.circleMarker([latitude, longitude], {
          renderer,
          radius: 2.2,
          stroke: false,
          fillColor: DOT_COLOR,
          fillOpacity: 0.5,
          interactive: false,
        }),
      ),
    ).addTo(map)
    return () => {
      group.remove()
      renderer.remove()
    }
  }, [map, points])
  return null
}

/** Moves the view to the selected area, so choosing a region brings it forward. */
function Focus({ bounds }: { bounds: L.LatLngBounds }) {
  const map = useMap()
  const key = bounds.toBBoxString()
  useEffect(() => {
    map.flyToBounds(bounds, { padding: [36, 36], duration: 0.7, maxZoom: 12 })
    // The bounds object is rebuilt on every render; its string form says whether it really moved.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, key])
  return null
}

function Clicks({ onClick }: { onClick: (latitude: number, longitude: number) => void }) {
  useMapEvents({ click: (event) => onClick(event.latlng.lat, event.latlng.lng) })
  return null
}

export function MapView(props: Props) {
  const { area, regions, regionShapes, districtShapes, points, drawing, pickingCentre, streets } = props

  const regionOfDistrict = useMemo(() => {
    const lookup = new Map<string, string>()
    for (const region of regions) for (const district of region.districts) lookup.set(district.name, region.name)
    return lookup
  }, [regions])

  const selectedDistrict = area.type === 'district' ? area.name : null
  const selectedRegion = area.type === 'region' ? area.name : selectedDistrict ? (regionOfDistrict.get(selectedDistrict) ?? null) : null
  const freeform = area.type === 'circle' || area.type === 'polygon' || drawing !== null
  const info = useMemo(() => {
    const lookup = new Map<string, AreaInfo>()
    for (const region of regions) {
      lookup.set(`region:${region.name}`, region)
      for (const district of region.districts) lookup.set(`district:${district.name}`, district)
    }
    return lookup
  }, [regions])

  const districtsShown = useMemo<GeoJSON.FeatureCollection | null>(() => {
    if (!districtShapes || !selectedRegion) return null
    return {
      type: 'FeatureCollection',
      features: districtShapes.features.filter((f) => regionOfDistrict.get(nameOf(f) ?? '') === selectedRegion),
    }
  }, [districtShapes, selectedRegion, regionOfDistrict])

  const highlighted = useMemo<GeoJSON.Feature | null>(() => {
    const shapes = selectedDistrict ? districtShapes : selectedRegion ? regionShapes : null
    const name = selectedDistrict ?? selectedRegion
    return shapes?.features.find((f) => nameOf(f) === name) ?? null
  }, [selectedDistrict, selectedRegion, districtShapes, regionShapes])

  const bounds = useMemo(() => {
    if (highlighted) return L.geoJSON(highlighted).getBounds()
    if (area.type === 'circle') return L.latLng(area.latitude, area.longitude).toBounds(area.radius_km * 2000)
    if (area.type === 'polygon') return L.latLngBounds(area.coordinates.map(([longitude, latitude]) => [latitude, longitude]))
    return regionShapes ? L.geoJSON(regionShapes).getBounds() : GAMBIA_BOUNDS
  }, [highlighted, area, regionShapes])

  const describe = (kind: 'region' | 'district', name: string) => {
    const facts = info.get(`${kind}:${name}`)
    return facts ? `<strong>${name}</strong><br>About ${count(facts.median_season)} hotspots in a normal season` : name
  }

  const regionStyle = (feature?: GeoJSON.Feature): L.PathOptions => {
    const dimmed = selectedRegion !== null && nameOf(feature) !== selectedRegion
    return {
      className: 'shape',
      color: dimmed ? '#cfcdc2' : '#8e8d83',
      weight: 1,
      fillColor: dimmed ? '#f0efe9' : '#e2e0d6',
      fillOpacity: 1,
    }
  }

  return (
    <MapContainer bounds={GAMBIA_BOUNDS} zoomSnap={0.25} className={`map${freeform ? ' picking' : ''}`} attributionControl={false}>
      {streets && (
        <TileLayer
          className="streets"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        />
      )}
      <Focus bounds={bounds} />

      {regionShapes && (
        // Leaflet fixes a shape layer's styles and handlers when it is created, so the key rebuilds it on change.
        <GeoJSON
          key={`regions-${selectedRegion}-${freeform}-${streets}`}
          data={regionShapes}
          style={(feature) => ({ ...regionStyle(feature), fillOpacity: streets ? 0.55 : 1 })}
          interactive={!freeform}
          onEachFeature={(feature, layer) => {
            const name = nameOf(feature)
            if (!name) return
            layer.bindTooltip(describe('region', name), { sticky: true, className: 'map-tip' })
            layer.on('click', () => props.onSelectRegion(name))
          }}
        />
      )}

      {districtsShown && (
        <GeoJSON
          key={`districts-${selectedRegion}-${selectedDistrict}-${freeform}`}
          data={districtsShown}
          style={() => ({ className: 'shape', color: '#8e8d83', weight: 0.8, fillColor: '#dbd9cd', fillOpacity: streets ? 0.35 : 1 })}
          interactive={!freeform}
          onEachFeature={(feature, layer) => {
            const name = nameOf(feature)
            if (!name) return
            layer.bindTooltip(describe('district', name), { sticky: true, className: 'map-tip' })
            layer.on('click', () => props.onSelectDistrict(name))
          }}
        />
      )}

      <Pane name="dots" style={{ zIndex: 450, pointerEvents: 'none' }}>
        <Dots points={points} />
      </Pane>

      <Pane name="lift" style={{ zIndex: 460, pointerEvents: 'none' }}>
        {highlighted && (
          <GeoJSON
            key={`lift-${selectedRegion}-${selectedDistrict}`}
            data={highlighted}
            interactive={false}
            style={{ className: 'lifted', color: '#1b1b18', weight: 2, fill: false }}
          />
        )}
        {area.type === 'circle' && drawing === null && (
          <Circle
            center={[area.latitude, area.longitude]}
            radius={area.radius_km * 1000}
            interactive={false}
            pathOptions={{ className: 'lifted', color: '#1b1b18', weight: 2, fill: false }}
          />
        )}
        {area.type === 'polygon' && drawing === null && (
          <Polygon
            positions={area.coordinates.map(([longitude, latitude]) => [latitude, longitude] as Vertex)}
            interactive={false}
            pathOptions={{ className: 'lifted', color: '#1b1b18', weight: 2, fill: false }}
          />
        )}
        {drawing && drawing.length > 0 && (
          <Polyline positions={drawing} interactive={false} pathOptions={{ color: '#1b1b18', weight: 2, dashArray: '6 6' }} />
        )}
      </Pane>

      <Pane name="labels" style={{ zIndex: 470, pointerEvents: 'none' }}>
        {!freeform &&
          (selectedRegion
            ? (regions.find((r) => r.name === selectedRegion)?.districts ?? []).map((district) => (
                <Marker
                  key={district.name}
                  position={district.label}
                  icon={label(district.name, district.name === selectedDistrict)}
                  interactive={false}
                />
              ))
            : regions
                // Banjul and Kanifing are a few kilometres wide and their names would cover each other.
                .filter((region) => region.area_km2 > 100)
                .map((region) => <Marker key={region.name} position={region.label} icon={label(region.name, false)} interactive={false} />))}
        {drawing?.map((vertex, index) => (
          <Marker key={index} position={vertex} icon={L.divIcon({ className: 'vertex', iconSize: [10, 10] })} interactive={false} />
        ))}
      </Pane>

      {drawing !== null && <Clicks onClick={(latitude, longitude) => props.onAddVertex([latitude, longitude])} />}
      {pickingCentre && drawing === null && <Clicks onClick={props.onPickCentre} />}
    </MapContainer>
  )
}
