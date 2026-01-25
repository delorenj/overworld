/**
 * TypeScript types for the interactive map renderer
 *
 * These types define the data structures used by the PixiJS-based
 * map rendering system including tiles, roads, icons, and viewport.
 */

/**
 * 2D point representation
 */
export interface Point {
  x: number;
  y: number;
}

/**
 * Rectangular bounds definition
 */
export interface Bounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Viewport state for pan/zoom operations
 */
export interface ViewportState {
  /** Current x offset (pan) */
  x: number;
  /** Current y offset (pan) */
  y: number;
  /** Current zoom scale (1.0 = 100%) */
  scale: number;
}

/**
 * Viewport constraints for navigation limits
 */
export interface ViewportConstraints {
  minScale: number;
  maxScale: number;
  /** Optional bounds to constrain panning */
  bounds?: Bounds;
}

/**
 * Single tile in the tile grid
 */
export interface MapTile {
  /** Grid column index */
  col: number;
  /** Grid row index */
  row: number;
  /** World x position */
  x: number;
  /** World y position */
  y: number;
  /** Tile width in pixels */
  width: number;
  /** Tile height in pixels */
  height: number;
  /** Terrain type for rendering */
  terrainType?: TerrainType;
  /** Optional texture URL */
  textureUrl?: string;
}

/**
 * Terrain types for background rendering
 */
export type TerrainType =
  | 'grass'
  | 'water'
  | 'mountain'
  | 'desert'
  | 'forest'
  | 'snow'
  | 'plains'
  | 'void';

/**
 * Road style configuration
 */
export interface RoadStyle {
  /** Road color as hex number */
  color: number;
  /** Road width in pixels */
  width: number;
  /** Optional dash pattern [dashLength, gapLength] */
  dashPattern?: [number, number];
  /** Line cap style */
  lineCap?: 'butt' | 'round' | 'square';
  /** Line join style */
  lineJoin?: 'miter' | 'round' | 'bevel';
}

/**
 * Road type definitions
 */
export type RoadType = 'main' | 'secondary' | 'path' | 'trail' | 'river';

/**
 * Road segment definition using spline points
 */
export interface Road {
  /** Unique road identifier */
  id: string;
  /** Road display name */
  name?: string;
  /** Road type for styling */
  type: RoadType;
  /** Spline control points */
  points: Point[];
  /** Optional custom style override */
  style?: Partial<RoadStyle>;
}

/**
 * Icon category for grouping
 */
export type IconCategory =
  | 'location'
  | 'building'
  | 'landmark'
  | 'resource'
  | 'danger'
  | 'quest'
  | 'custom';

/**
 * Map icon definition
 */
export interface MapIcon {
  /** Unique icon identifier */
  id: string;
  /** Icon display name */
  name: string;
  /** Position on map */
  position: Point;
  /** Icon category */
  category: IconCategory;
  /** Sprite texture key or URL */
  sprite: string;
  /** Icon scale (1.0 = original size) */
  scale?: number;
  /** Icon opacity (0-1) */
  opacity?: number;
  /** Whether icon is interactive */
  interactive?: boolean;
  /** Optional metadata for icon */
  metadata?: Record<string, unknown>;
}

/**
 * Label configuration for text on map
 */
export interface MapLabel {
  /** Unique label identifier */
  id: string;
  /** Label text content */
  text: string;
  /** Position on map */
  position: Point;
  /** Font size in pixels */
  fontSize?: number;
  /** Font family */
  fontFamily?: string;
  /** Text color as hex number */
  color?: number;
  /** Text anchor point */
  anchor?: Point;
  /** Optional rotation in radians */
  rotation?: number;
}

/**
 * Complete map data structure
 */
export interface MapData {
  /** Map identifier */
  id: string;
  /** Map display name */
  name: string;
  /** Map dimensions in world units */
  width: number;
  height: number;
  /** Tile size for grid */
  tileSize: number;
  /** Background/terrain tiles */
  tiles?: MapTile[];
  /** Road network */
  roads: Road[];
  /** Map icons */
  icons: MapIcon[];
  /** Map labels */
  labels?: MapLabel[];
  /** Default background color */
  backgroundColor?: number;
}

/**
 * Interaction event types
 */
export type MapInteractionType =
  | 'icon-click'
  | 'icon-hover'
  | 'icon-hover-end'
  | 'tile-click'
  | 'road-click'
  | 'map-click';

/**
 * Map interaction event payload
 */
export interface MapInteractionEvent {
  type: MapInteractionType;
  /** World position of interaction */
  position: Point;
  /** Target element id if applicable */
  targetId?: string;
  /** Target element data */
  target?: MapIcon | MapTile | Road;
  /** Original DOM event */
  originalEvent: MouseEvent | TouchEvent | PointerEvent;
}

/**
 * Map renderer configuration options
 */
export interface MapRendererConfig {
  /** Initial viewport state */
  initialViewport?: Partial<ViewportState>;
  /** Viewport navigation constraints */
  constraints?: ViewportConstraints;
  /** Enable debug rendering */
  debug?: boolean;
  /** Antialias setting */
  antialias?: boolean;
  /** Background color */
  backgroundColor?: number;
  /** Resolution multiplier for HiDPI */
  resolution?: number;
  /** Enable touch support */
  enableTouch?: boolean;
}

/**
 * Layer visibility configuration
 */
export interface LayerVisibility {
  background: boolean;
  roads: boolean;
  icons: boolean;
  labels: boolean;
  debug: boolean;
}

/**
 * Default road styles by type
 */
export const DEFAULT_ROAD_STYLES: Record<RoadType, RoadStyle> = {
  main: {
    color: 0x8b4513,
    width: 8,
    lineCap: 'round',
    lineJoin: 'round',
  },
  secondary: {
    color: 0xa0522d,
    width: 5,
    lineCap: 'round',
    lineJoin: 'round',
  },
  path: {
    color: 0xd2b48c,
    width: 3,
    lineCap: 'round',
    lineJoin: 'round',
  },
  trail: {
    color: 0xdeb887,
    width: 2,
    dashPattern: [8, 4],
    lineCap: 'butt',
    lineJoin: 'round',
  },
  river: {
    color: 0x4169e1,
    width: 6,
    lineCap: 'round',
    lineJoin: 'round',
  },
};

/**
 * Default terrain colors by type
 */
export const DEFAULT_TERRAIN_COLORS: Record<TerrainType, number> = {
  grass: 0x7cba5f,
  water: 0x4a90d9,
  mountain: 0x8b8b8b,
  desert: 0xe8d4a8,
  forest: 0x2d5a27,
  snow: 0xf0f0f0,
  plains: 0xb8d68c,
  void: 0x1a1a2e,
};

/**
 * Default viewport constraints
 */
export const DEFAULT_VIEWPORT_CONSTRAINTS: ViewportConstraints = {
  minScale: 0.25,
  maxScale: 4.0,
};

/**
 * Default map renderer configuration
 */
export const DEFAULT_RENDERER_CONFIG: MapRendererConfig = {
  initialViewport: { x: 0, y: 0, scale: 1 },
  constraints: DEFAULT_VIEWPORT_CONSTRAINTS,
  debug: false,
  antialias: true,
  backgroundColor: 0x1a1a2e,
  resolution: window.devicePixelRatio || 1,
  enableTouch: true,
};
