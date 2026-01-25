/**
 * BackgroundLayer
 *
 * Handles rendering of the terrain/background tiles for the map.
 * Uses a tile grid system for efficient rendering of only visible tiles.
 */

import * as PIXI from 'pixi.js';
import type {
  MapTile,
  TerrainType,
  ViewportState,
  Bounds,
} from '../../../types/map';
import { DEFAULT_TERRAIN_COLORS } from '../../../types/map';

/**
 * Configuration for the background layer
 */
export interface BackgroundLayerConfig {
  /** Tile size in pixels */
  tileSize: number;
  /** Map width in world units */
  mapWidth: number;
  /** Map height in world units */
  mapHeight: number;
  /** Default terrain type */
  defaultTerrain?: TerrainType;
  /** Show grid lines */
  showGrid?: boolean;
  /** Grid line color */
  gridColor?: number;
  /** Grid line alpha */
  gridAlpha?: number;
}

/**
 * Default configuration
 */
const DEFAULT_CONFIG: BackgroundLayerConfig = {
  tileSize: 64,
  mapWidth: 2048,
  mapHeight: 2048,
  defaultTerrain: 'grass',
  showGrid: false,
  gridColor: 0x000000,
  gridAlpha: 0.1,
};

/**
 * BackgroundLayer class for managing terrain rendering
 */
export class BackgroundLayer {
  /** PixiJS container for this layer */
  public readonly container: PIXI.Container;

  /** Configuration */
  private config: BackgroundLayerConfig;

  /** Tile graphics cache */
  private tileGraphics: Map<string, PIXI.Graphics> = new Map();

  /** Tile data */
  private tiles: Map<string, MapTile> = new Map();

  /** Grid lines container */
  private gridContainer: PIXI.Container;

  /** Background graphics */
  private background: PIXI.Graphics;

  /** Currently visible tile range */
  private visibleRange: {
    startCol: number;
    endCol: number;
    startRow: number;
    endRow: number;
  } = { startCol: 0, endCol: 0, startRow: 0, endRow: 0 };

  constructor(config: Partial<BackgroundLayerConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };

    // Create main container
    this.container = new PIXI.Container();
    this.container.sortableChildren = true;
    this.container.zIndex = 0;

    // Create background fill
    this.background = new PIXI.Graphics();
    this.background.zIndex = 0;
    this.container.addChild(this.background);

    // Create grid container
    this.gridContainer = new PIXI.Container();
    this.gridContainer.zIndex = 1;
    this.gridContainer.visible = this.config.showGrid ?? false;
    this.container.addChild(this.gridContainer);

    // Draw initial background
    this.drawBackground();
  }

  /**
   * Draw the base background rectangle
   */
  private drawBackground(): void {
    const { mapWidth, mapHeight, defaultTerrain } = this.config;
    const color = DEFAULT_TERRAIN_COLORS[defaultTerrain ?? 'grass'];

    this.background.clear();
    this.background.beginFill(color);
    this.background.drawRect(0, 0, mapWidth, mapHeight);
    this.background.endFill();
  }

  /**
   * Generate tile key from coordinates
   */
  private getTileKey(col: number, row: number): string {
    return `${col},${row}`;
  }

  /**
   * Set tile data for the map
   */
  public setTiles(tiles: MapTile[]): void {
    this.tiles.clear();
    this.clearTileGraphics();

    for (const tile of tiles) {
      const key = this.getTileKey(tile.col, tile.row);
      this.tiles.set(key, tile);
    }
  }

  /**
   * Clear all tile graphics
   */
  private clearTileGraphics(): void {
    for (const graphic of this.tileGraphics.values()) {
      graphic.destroy();
    }
    this.tileGraphics.clear();
  }

  /**
   * Update visible tiles based on viewport
   */
  public updateVisibleTiles(
    viewport: ViewportState,
    containerWidth: number,
    containerHeight: number
  ): void {
    const { tileSize } = this.config;

    // Calculate visible world bounds
    const worldLeft = -viewport.x / viewport.scale;
    const worldTop = -viewport.y / viewport.scale;
    const worldRight = worldLeft + containerWidth / viewport.scale;
    const worldBottom = worldTop + containerHeight / viewport.scale;

    // Calculate tile range with buffer
    const buffer = 1;
    const startCol = Math.max(0, Math.floor(worldLeft / tileSize) - buffer);
    const endCol = Math.ceil(worldRight / tileSize) + buffer;
    const startRow = Math.max(0, Math.floor(worldTop / tileSize) - buffer);
    const endRow = Math.ceil(worldBottom / tileSize) + buffer;

    // Check if range changed
    if (
      startCol === this.visibleRange.startCol &&
      endCol === this.visibleRange.endCol &&
      startRow === this.visibleRange.startRow &&
      endRow === this.visibleRange.endRow
    ) {
      return;
    }

    this.visibleRange = { startCol, endCol, startRow, endRow };

    // Remove tiles outside visible range
    for (const [key, graphic] of this.tileGraphics.entries()) {
      const [col, row] = key.split(',').map(Number);
      if (
        col < startCol ||
        col > endCol ||
        row < startRow ||
        row > endRow
      ) {
        graphic.destroy();
        this.tileGraphics.delete(key);
      }
    }

    // Add tiles in visible range
    for (let col = startCol; col <= endCol; col++) {
      for (let row = startRow; row <= endRow; row++) {
        const key = this.getTileKey(col, row);
        if (!this.tileGraphics.has(key)) {
          this.createTileGraphic(col, row);
        }
      }
    }
  }

  /**
   * Create graphic for a single tile
   */
  private createTileGraphic(col: number, row: number): void {
    const { tileSize } = this.config;
    const key = this.getTileKey(col, row);
    const tile = this.tiles.get(key);

    const graphic = new PIXI.Graphics();
    graphic.zIndex = 2;

    // Get tile position
    const x = col * tileSize;
    const y = row * tileSize;

    // Draw tile if it has custom terrain
    if (tile && tile.terrainType) {
      const color = DEFAULT_TERRAIN_COLORS[tile.terrainType];
      graphic.beginFill(color);
      graphic.drawRect(x, y, tileSize, tileSize);
      graphic.endFill();
    }

    this.tileGraphics.set(key, graphic);
    this.container.addChild(graphic);
  }

  /**
   * Draw grid lines
   */
  public drawGrid(): void {
    const { mapWidth, mapHeight, tileSize, gridColor, gridAlpha } = this.config;

    this.gridContainer.removeChildren();

    const gridGraphics = new PIXI.Graphics();
    gridGraphics.lineStyle(1, gridColor ?? 0x000000, gridAlpha ?? 0.1);

    // Vertical lines
    for (let x = 0; x <= mapWidth; x += tileSize) {
      gridGraphics.moveTo(x, 0);
      gridGraphics.lineTo(x, mapHeight);
    }

    // Horizontal lines
    for (let y = 0; y <= mapHeight; y += tileSize) {
      gridGraphics.moveTo(0, y);
      gridGraphics.lineTo(mapWidth, y);
    }

    this.gridContainer.addChild(gridGraphics);
  }

  /**
   * Toggle grid visibility
   */
  public setGridVisible(visible: boolean): void {
    this.gridContainer.visible = visible;
    if (visible && this.gridContainer.children.length === 0) {
      this.drawGrid();
    }
  }

  /**
   * Update layer configuration
   */
  public updateConfig(config: Partial<BackgroundLayerConfig>): void {
    this.config = { ...this.config, ...config };
    this.drawBackground();

    if (this.config.showGrid) {
      this.drawGrid();
    }
  }

  /**
   * Get map bounds
   */
  public getBounds(): Bounds {
    return {
      x: 0,
      y: 0,
      width: this.config.mapWidth,
      height: this.config.mapHeight,
    };
  }

  /**
   * Get tile at world position
   */
  public getTileAtPosition(x: number, y: number): MapTile | null {
    const { tileSize } = this.config;
    const col = Math.floor(x / tileSize);
    const row = Math.floor(y / tileSize);
    const key = this.getTileKey(col, row);
    return this.tiles.get(key) || null;
  }

  /**
   * Set terrain for a specific tile
   */
  public setTileTerrain(col: number, row: number, terrainType: TerrainType): void {
    const key = this.getTileKey(col, row);
    const { tileSize } = this.config;

    const tile: MapTile = {
      col,
      row,
      x: col * tileSize,
      y: row * tileSize,
      width: tileSize,
      height: tileSize,
      terrainType,
    };

    this.tiles.set(key, tile);

    // Update graphic if it exists
    const graphic = this.tileGraphics.get(key);
    if (graphic) {
      graphic.destroy();
      this.tileGraphics.delete(key);
      this.createTileGraphic(col, row);
    }
  }

  /**
   * Destroy the layer and clean up resources
   */
  public destroy(): void {
    this.clearTileGraphics();
    this.tiles.clear();
    this.container.destroy({ children: true });
  }
}
