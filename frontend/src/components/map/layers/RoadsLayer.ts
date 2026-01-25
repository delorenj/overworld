/**
 * RoadsLayer
 *
 * Handles rendering of roads and paths using spline curves.
 * Supports various road styles including color, width, and dashed lines.
 */

import * as PIXI from 'pixi.js';
import type { Road, RoadStyle, RoadType, Point } from '../../../types/map';
import { DEFAULT_ROAD_STYLES } from '../../../types/map';

/**
 * Configuration for the roads layer
 */
export interface RoadsLayerConfig {
  /** Curve tension for spline smoothing (0-1) */
  curveTension?: number;
  /** Number of segments per spline section */
  curveSegments?: number;
  /** Enable road interaction (hover, click) */
  interactive?: boolean;
  /** Hover highlight color */
  hoverColor?: number;
}

/**
 * Default configuration
 */
const DEFAULT_CONFIG: RoadsLayerConfig = {
  curveTension: 0.5,
  curveSegments: 20,
  interactive: true,
  hoverColor: 0xffff00,
};

/**
 * Road graphics data
 */
interface RoadGraphicsData {
  road: Road;
  graphics: PIXI.Graphics;
  style: RoadStyle;
  smoothedPoints: Point[];
}

/**
 * RoadsLayer class for managing road/path rendering
 */
export class RoadsLayer {
  /** PixiJS container for this layer */
  public readonly container: PIXI.Container;

  /** Configuration */
  private config: RoadsLayerConfig;

  /** Road graphics data */
  private roads: Map<string, RoadGraphicsData> = new Map();

  /** Currently hovered road ID */
  private hoveredRoadId: string | null = null;

  /** Event callbacks */
  private onRoadClick?: (road: Road, event: PIXI.FederatedPointerEvent) => void;
  private onRoadHover?: (road: Road | null) => void;

  constructor(config: Partial<RoadsLayerConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };

    // Create main container
    this.container = new PIXI.Container();
    this.container.sortableChildren = true;
    this.container.zIndex = 10;
  }

  /**
   * Set road click handler
   */
  public setOnRoadClick(
    callback: (road: Road, event: PIXI.FederatedPointerEvent) => void
  ): void {
    this.onRoadClick = callback;
  }

  /**
   * Set road hover handler
   */
  public setOnRoadHover(callback: (road: Road | null) => void): void {
    this.onRoadHover = callback;
  }

  /**
   * Catmull-Rom spline interpolation
   * Creates smooth curves through control points
   */
  private catmullRomSpline(
    points: Point[],
    tension: number,
    segments: number
  ): Point[] {
    if (points.length < 2) return points;

    const result: Point[] = [];

    // Add extra control points at start and end
    const extendedPoints = [
      points[0],
      ...points,
      points[points.length - 1],
    ];

    for (let i = 1; i < extendedPoints.length - 2; i++) {
      const p0 = extendedPoints[i - 1];
      const p1 = extendedPoints[i];
      const p2 = extendedPoints[i + 1];
      const p3 = extendedPoints[i + 2];

      for (let t = 0; t < segments; t++) {
        const s = t / segments;
        const s2 = s * s;
        const s3 = s2 * s;

        // Catmull-Rom basis functions
        const h1 = -tension * s3 + 2 * tension * s2 - tension * s;
        const h2 = (2 - tension) * s3 + (tension - 3) * s2 + 1;
        const h3 = (tension - 2) * s3 + (3 - 2 * tension) * s2 + tension * s;
        const h4 = tension * s3 - tension * s2;

        result.push({
          x: h1 * p0.x + h2 * p1.x + h3 * p2.x + h4 * p3.x,
          y: h1 * p0.y + h2 * p1.y + h3 * p2.y + h4 * p3.y,
        });
      }
    }

    // Add the last point
    result.push(points[points.length - 1]);

    return result;
  }

  /**
   * Draw a road with the given style
   */
  private drawRoad(
    graphics: PIXI.Graphics,
    points: Point[],
    style: RoadStyle,
    isHighlighted: boolean = false
  ): void {
    if (points.length < 2) return;

    graphics.clear();

    const color = isHighlighted ? this.config.hoverColor ?? 0xffff00 : style.color;
    const width = isHighlighted ? style.width * 1.3 : style.width;

    // Set line style
    graphics.lineStyle({
      width,
      color,
      cap: style.lineCap === 'round' ? PIXI.LINE_CAP.ROUND :
           style.lineCap === 'square' ? PIXI.LINE_CAP.SQUARE :
           PIXI.LINE_CAP.BUTT,
      join: style.lineJoin === 'round' ? PIXI.LINE_JOIN.ROUND :
            style.lineJoin === 'bevel' ? PIXI.LINE_JOIN.BEVEL :
            PIXI.LINE_JOIN.MITER,
    });

    // Handle dashed lines
    if (style.dashPattern && !isHighlighted) {
      this.drawDashedLine(graphics, points, style);
    } else {
      // Draw solid line
      graphics.moveTo(points[0].x, points[0].y);
      for (let i = 1; i < points.length; i++) {
        graphics.lineTo(points[i].x, points[i].y);
      }
    }
  }

  /**
   * Draw a dashed line along points
   */
  private drawDashedLine(
    graphics: PIXI.Graphics,
    points: Point[],
    style: RoadStyle
  ): void {
    if (!style.dashPattern) return;

    const [dashLength, gapLength] = style.dashPattern;
    let currentLength = 0;
    let isDash = true;

    for (let i = 0; i < points.length - 1; i++) {
      const p1 = points[i];
      const p2 = points[i + 1];

      const dx = p2.x - p1.x;
      const dy = p2.y - p1.y;
      const segmentLength = Math.sqrt(dx * dx + dy * dy);

      if (segmentLength === 0) continue;

      const dirX = dx / segmentLength;
      const dirY = dy / segmentLength;

      let traveled = 0;

      while (traveled < segmentLength) {
        const patternLength = isDash ? dashLength : gapLength;
        const remaining = patternLength - currentLength;
        const available = segmentLength - traveled;
        const step = Math.min(remaining, available);

        const startX = p1.x + dirX * traveled;
        const startY = p1.y + dirY * traveled;
        const endX = startX + dirX * step;
        const endY = startY + dirY * step;

        if (isDash) {
          graphics.moveTo(startX, startY);
          graphics.lineTo(endX, endY);
        }

        traveled += step;
        currentLength += step;

        if (currentLength >= patternLength) {
          currentLength = 0;
          isDash = !isDash;
        }
      }
    }
  }

  /**
   * Get road style from type and custom overrides
   */
  private getRoadStyle(type: RoadType, customStyle?: Partial<RoadStyle>): RoadStyle {
    const baseStyle = DEFAULT_ROAD_STYLES[type];
    return customStyle ? { ...baseStyle, ...customStyle } : baseStyle;
  }

  /**
   * Create interactive hit area for a road
   */
  private createHitArea(points: Point[], width: number): PIXI.Polygon {
    if (points.length < 2) {
      return new PIXI.Polygon([]);
    }

    const halfWidth = width * 2; // Wider hit area for easier clicking
    const topPoints: Point[] = [];
    const bottomPoints: Point[] = [];

    for (let i = 0; i < points.length; i++) {
      const p = points[i];
      let perpX: number, perpY: number;

      if (i === 0) {
        // First point
        const next = points[i + 1];
        const dx = next.x - p.x;
        const dy = next.y - p.y;
        const len = Math.sqrt(dx * dx + dy * dy) || 1;
        perpX = -dy / len;
        perpY = dx / len;
      } else if (i === points.length - 1) {
        // Last point
        const prev = points[i - 1];
        const dx = p.x - prev.x;
        const dy = p.y - prev.y;
        const len = Math.sqrt(dx * dx + dy * dy) || 1;
        perpX = -dy / len;
        perpY = dx / len;
      } else {
        // Middle points - average of adjacent segments
        const prev = points[i - 1];
        const next = points[i + 1];
        const dx1 = p.x - prev.x;
        const dy1 = p.y - prev.y;
        const dx2 = next.x - p.x;
        const dy2 = next.y - p.y;
        const len1 = Math.sqrt(dx1 * dx1 + dy1 * dy1) || 1;
        const len2 = Math.sqrt(dx2 * dx2 + dy2 * dy2) || 1;
        perpX = (-dy1 / len1 - dy2 / len2) / 2;
        perpY = (dx1 / len1 + dx2 / len2) / 2;
        const perpLen = Math.sqrt(perpX * perpX + perpY * perpY) || 1;
        perpX /= perpLen;
        perpY /= perpLen;
      }

      topPoints.push({
        x: p.x + perpX * halfWidth,
        y: p.y + perpY * halfWidth,
      });
      bottomPoints.unshift({
        x: p.x - perpX * halfWidth,
        y: p.y - perpY * halfWidth,
      });
    }

    const allPoints = [...topPoints, ...bottomPoints];
    const flatPoints = allPoints.flatMap((p) => [p.x, p.y]);
    return new PIXI.Polygon(flatPoints);
  }

  /**
   * Add a road to the layer
   */
  public addRoad(road: Road): void {
    if (this.roads.has(road.id)) {
      this.removeRoad(road.id);
    }

    const style = this.getRoadStyle(road.type, road.style);
    const smoothedPoints = this.catmullRomSpline(
      road.points,
      this.config.curveTension ?? 0.5,
      this.config.curveSegments ?? 20
    );

    const graphics = new PIXI.Graphics();
    this.drawRoad(graphics, smoothedPoints, style);

    // Set up interactivity
    if (this.config.interactive) {
      graphics.eventMode = 'static';
      graphics.cursor = 'pointer';
      graphics.hitArea = this.createHitArea(smoothedPoints, style.width);

      graphics.on('pointerover', () => {
        this.hoveredRoadId = road.id;
        this.drawRoad(graphics, smoothedPoints, style, true);
        this.onRoadHover?.(road);
      });

      graphics.on('pointerout', () => {
        this.hoveredRoadId = null;
        this.drawRoad(graphics, smoothedPoints, style, false);
        this.onRoadHover?.(null);
      });

      graphics.on('pointertap', (event: PIXI.FederatedPointerEvent) => {
        this.onRoadClick?.(road, event);
      });
    }

    this.roads.set(road.id, {
      road,
      graphics,
      style,
      smoothedPoints,
    });

    this.container.addChild(graphics);
  }

  /**
   * Remove a road from the layer
   */
  public removeRoad(id: string): void {
    const data = this.roads.get(id);
    if (data) {
      data.graphics.destroy();
      this.roads.delete(id);
    }
  }

  /**
   * Set all roads for the layer
   */
  public setRoads(roads: Road[]): void {
    this.clearRoads();
    for (const road of roads) {
      this.addRoad(road);
    }
  }

  /**
   * Clear all roads
   */
  public clearRoads(): void {
    for (const data of this.roads.values()) {
      data.graphics.destroy();
    }
    this.roads.clear();
    this.hoveredRoadId = null;
  }

  /**
   * Update a road's points
   */
  public updateRoadPoints(id: string, points: Point[]): void {
    const data = this.roads.get(id);
    if (!data) return;

    data.road.points = points;
    data.smoothedPoints = this.catmullRomSpline(
      points,
      this.config.curveTension ?? 0.5,
      this.config.curveSegments ?? 20
    );

    this.drawRoad(
      data.graphics,
      data.smoothedPoints,
      data.style,
      this.hoveredRoadId === id
    );

    if (this.config.interactive) {
      data.graphics.hitArea = this.createHitArea(data.smoothedPoints, data.style.width);
    }
  }

  /**
   * Update a road's style
   */
  public updateRoadStyle(id: string, style: Partial<RoadStyle>): void {
    const data = this.roads.get(id);
    if (!data) return;

    data.style = { ...data.style, ...style };
    data.road.style = { ...data.road.style, ...style };

    this.drawRoad(
      data.graphics,
      data.smoothedPoints,
      data.style,
      this.hoveredRoadId === id
    );

    if (this.config.interactive) {
      data.graphics.hitArea = this.createHitArea(data.smoothedPoints, data.style.width);
    }
  }

  /**
   * Get road by ID
   */
  public getRoad(id: string): Road | null {
    return this.roads.get(id)?.road || null;
  }

  /**
   * Get all roads
   */
  public getAllRoads(): Road[] {
    return Array.from(this.roads.values()).map((data) => data.road);
  }

  /**
   * Find road at world position
   */
  public getRoadAtPosition(x: number, y: number): Road | null {
    // Check in reverse order (top-most first)
    const entries = Array.from(this.roads.entries()).reverse();

    for (const [, data] of entries) {
      const { smoothedPoints, style } = data;
      const threshold = style.width * 2;

      // Check distance to each segment
      for (let i = 0; i < smoothedPoints.length - 1; i++) {
        const p1 = smoothedPoints[i];
        const p2 = smoothedPoints[i + 1];

        const distance = this.pointToSegmentDistance(x, y, p1, p2);
        if (distance <= threshold) {
          return data.road;
        }
      }
    }

    return null;
  }

  /**
   * Calculate distance from point to line segment
   */
  private pointToSegmentDistance(
    px: number,
    py: number,
    p1: Point,
    p2: Point
  ): number {
    const dx = p2.x - p1.x;
    const dy = p2.y - p1.y;
    const lengthSq = dx * dx + dy * dy;

    if (lengthSq === 0) {
      // Segment is a point
      return Math.sqrt((px - p1.x) ** 2 + (py - p1.y) ** 2);
    }

    // Project point onto segment
    let t = ((px - p1.x) * dx + (py - p1.y) * dy) / lengthSq;
    t = Math.max(0, Math.min(1, t));

    const projX = p1.x + t * dx;
    const projY = p1.y + t * dy;

    return Math.sqrt((px - projX) ** 2 + (py - projY) ** 2);
  }

  /**
   * Update layer configuration
   */
  public updateConfig(config: Partial<RoadsLayerConfig>): void {
    this.config = { ...this.config, ...config };
    // Re-render all roads with new config
    const roads = this.getAllRoads();
    this.setRoads(roads);
  }

  /**
   * Destroy the layer and clean up resources
   */
  public destroy(): void {
    this.clearRoads();
    this.container.destroy({ children: true });
  }
}
