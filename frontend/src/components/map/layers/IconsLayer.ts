/**
 * IconsLayer
 *
 * Handles rendering of map icons and points of interest.
 * Supports sprite loading, positioning, and interactive features.
 */

import * as PIXI from 'pixi.js';
import type { MapIcon, MapLabel, IconCategory, Point } from '../../../types/map';

/**
 * Configuration for the icons layer
 */
export interface IconsLayerConfig {
  /** Default icon scale */
  defaultScale?: number;
  /** Default icon opacity */
  defaultOpacity?: number;
  /** Enable icon interaction */
  interactive?: boolean;
  /** Hover scale multiplier */
  hoverScaleMultiplier?: number;
  /** Animation duration in ms */
  animationDuration?: number;
  /** Show labels by default */
  showLabels?: boolean;
  /** Label font settings */
  labelFont?: {
    family: string;
    size: number;
    color: number;
  };
}

/**
 * Default configuration
 */
const DEFAULT_CONFIG: IconsLayerConfig = {
  defaultScale: 1,
  defaultOpacity: 1,
  interactive: true,
  hoverScaleMultiplier: 1.2,
  animationDuration: 150,
  showLabels: true,
  labelFont: {
    family: 'Arial',
    size: 12,
    color: 0xffffff,
  },
};

/**
 * Default category colors for fallback rendering
 */
const CATEGORY_COLORS: Record<IconCategory, number> = {
  location: 0x4a90d9,
  building: 0x8b4513,
  landmark: 0xffd700,
  resource: 0x32cd32,
  danger: 0xff4444,
  quest: 0x9932cc,
  custom: 0x808080,
};

/**
 * Icon graphics data
 */
interface IconGraphicsData {
  icon: MapIcon;
  container: PIXI.Container;
  sprite: PIXI.Sprite | PIXI.Graphics;
  label?: PIXI.Text;
  originalScale: number;
}

/**
 * IconsLayer class for managing icon rendering
 */
export class IconsLayer {
  /** PixiJS container for this layer */
  public readonly container: PIXI.Container;

  /** Configuration */
  private config: IconsLayerConfig;

  /** Icon graphics data */
  private icons: Map<string, IconGraphicsData> = new Map();

  /** Texture cache */
  private textureCache: Map<string, PIXI.Texture> = new Map();

  /** Currently hovered icon ID */
  private hoveredIconId: string | null = null;

  /** Event callbacks */
  private onIconClick?: (icon: MapIcon, event: PIXI.FederatedPointerEvent) => void;
  private onIconHover?: (icon: MapIcon | null) => void;

  constructor(config: Partial<IconsLayerConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };

    // Create main container
    this.container = new PIXI.Container();
    this.container.sortableChildren = true;
    this.container.zIndex = 20;
  }

  /**
   * Set icon click handler
   */
  public setOnIconClick(
    callback: (icon: MapIcon, event: PIXI.FederatedPointerEvent) => void
  ): void {
    this.onIconClick = callback;
  }

  /**
   * Set icon hover handler
   */
  public setOnIconHover(callback: (icon: MapIcon | null) => void): void {
    this.onIconHover = callback;
  }

  /**
   * Load a texture from URL
   */
  private async loadTexture(url: string): Promise<PIXI.Texture> {
    if (this.textureCache.has(url)) {
      return this.textureCache.get(url)!;
    }

    try {
      const texture = await PIXI.Assets.load(url);
      this.textureCache.set(url, texture);
      return texture;
    } catch (error) {
      console.warn(`Failed to load texture: ${url}`, error);
      return PIXI.Texture.EMPTY;
    }
  }

  /**
   * Create a fallback icon graphic
   */
  private createFallbackIcon(category: IconCategory): PIXI.Graphics {
    const graphics = new PIXI.Graphics();
    const color = CATEGORY_COLORS[category];
    const size = 24;

    // Draw a circular marker with border
    graphics.lineStyle(2, 0xffffff, 1);
    graphics.beginFill(color);
    graphics.drawCircle(0, 0, size / 2);
    graphics.endFill();

    // Draw inner detail based on category
    graphics.lineStyle(0);
    graphics.beginFill(0xffffff, 0.9);

    switch (category) {
      case 'location':
        // Pin shape
        graphics.drawCircle(0, -2, 4);
        break;
      case 'building':
        // House shape
        graphics.drawRect(-4, -2, 8, 6);
        graphics.moveTo(-5, -2);
        graphics.lineTo(0, -7);
        graphics.lineTo(5, -2);
        graphics.closePath();
        break;
      case 'landmark':
        // Star shape
        this.drawStar(graphics, 0, 0, 5, 6, 3);
        break;
      case 'resource':
        // Diamond shape
        graphics.moveTo(0, -5);
        graphics.lineTo(5, 0);
        graphics.lineTo(0, 5);
        graphics.lineTo(-5, 0);
        graphics.closePath();
        break;
      case 'danger':
        // Warning triangle
        graphics.moveTo(0, -5);
        graphics.lineTo(5, 4);
        graphics.lineTo(-5, 4);
        graphics.closePath();
        break;
      case 'quest':
        // Exclamation mark
        graphics.drawRect(-1.5, -5, 3, 6);
        graphics.drawCircle(0, 4, 1.5);
        break;
      default:
        // Generic dot
        graphics.drawCircle(0, 0, 3);
    }

    graphics.endFill();

    return graphics;
  }

  /**
   * Draw a star shape
   */
  private drawStar(
    graphics: PIXI.Graphics,
    cx: number,
    cy: number,
    spikes: number,
    outerRadius: number,
    innerRadius: number
  ): void {
    let rotation = -Math.PI / 2;
    const step = Math.PI / spikes;

    graphics.moveTo(
      cx + Math.cos(rotation) * outerRadius,
      cy + Math.sin(rotation) * outerRadius
    );

    for (let i = 0; i < spikes; i++) {
      rotation += step;
      graphics.lineTo(
        cx + Math.cos(rotation) * innerRadius,
        cy + Math.sin(rotation) * innerRadius
      );
      rotation += step;
      graphics.lineTo(
        cx + Math.cos(rotation) * outerRadius,
        cy + Math.sin(rotation) * outerRadius
      );
    }

    graphics.closePath();
  }

  /**
   * Create label text for an icon
   */
  private createLabel(icon: MapIcon): PIXI.Text {
    const { labelFont } = this.config;
    const style = new PIXI.TextStyle({
      fontFamily: labelFont?.family ?? 'Arial',
      fontSize: icon.metadata?.fontSize as number ?? labelFont?.size ?? 12,
      fill: labelFont?.color ?? 0xffffff,
      align: 'center',
      stroke: 0x000000,
      strokeThickness: 2,
      dropShadow: true,
      dropShadowColor: 0x000000,
      dropShadowBlur: 2,
      dropShadowDistance: 1,
    });

    const text = new PIXI.Text(icon.name, style);
    text.anchor.set(0.5, 0);
    text.position.set(0, 16); // Position below icon

    return text;
  }

  /**
   * Set up icon interactivity
   */
  private setupInteractivity(
    container: PIXI.Container,
    icon: MapIcon,
    originalScale: number
  ): void {
    if (!this.config.interactive || !icon.interactive) return;

    container.eventMode = 'static';
    container.cursor = 'pointer';

    const hoverScale = originalScale * (this.config.hoverScaleMultiplier ?? 1.2);

    container.on('pointerover', () => {
      this.hoveredIconId = icon.id;
      container.scale.set(hoverScale);
      this.onIconHover?.(icon);
    });

    container.on('pointerout', () => {
      this.hoveredIconId = null;
      container.scale.set(originalScale);
      this.onIconHover?.(null);
    });

    container.on('pointertap', (event: PIXI.FederatedPointerEvent) => {
      this.onIconClick?.(icon, event);
    });
  }

  /**
   * Add an icon to the layer
   */
  public async addIcon(icon: MapIcon): Promise<void> {
    if (this.icons.has(icon.id)) {
      this.removeIcon(icon.id);
    }

    const iconContainer = new PIXI.Container();
    iconContainer.position.set(icon.position.x, icon.position.y);

    const scale = icon.scale ?? this.config.defaultScale ?? 1;
    iconContainer.scale.set(scale);
    iconContainer.alpha = icon.opacity ?? this.config.defaultOpacity ?? 1;

    let sprite: PIXI.Sprite | PIXI.Graphics;

    // Try to load sprite texture
    if (icon.sprite && !icon.sprite.startsWith('fallback:')) {
      try {
        const texture = await this.loadTexture(icon.sprite);
        if (texture !== PIXI.Texture.EMPTY) {
          sprite = new PIXI.Sprite(texture);
          sprite.anchor.set(0.5, 0.5);
        } else {
          sprite = this.createFallbackIcon(icon.category);
        }
      } catch {
        sprite = this.createFallbackIcon(icon.category);
      }
    } else {
      sprite = this.createFallbackIcon(icon.category);
    }

    iconContainer.addChild(sprite);

    // Add label if enabled
    let label: PIXI.Text | undefined;
    if (this.config.showLabels && icon.name) {
      label = this.createLabel(icon);
      iconContainer.addChild(label);
    }

    // Set up interactivity
    this.setupInteractivity(iconContainer, icon, scale);

    // Store icon data
    this.icons.set(icon.id, {
      icon,
      container: iconContainer,
      sprite,
      label,
      originalScale: scale,
    });

    this.container.addChild(iconContainer);
  }

  /**
   * Remove an icon from the layer
   */
  public removeIcon(id: string): void {
    const data = this.icons.get(id);
    if (data) {
      data.container.destroy({ children: true });
      this.icons.delete(id);

      if (this.hoveredIconId === id) {
        this.hoveredIconId = null;
      }
    }
  }

  /**
   * Set all icons for the layer
   */
  public async setIcons(icons: MapIcon[]): Promise<void> {
    this.clearIcons();
    await Promise.all(icons.map((icon) => this.addIcon(icon)));
  }

  /**
   * Clear all icons
   */
  public clearIcons(): void {
    for (const data of this.icons.values()) {
      data.container.destroy({ children: true });
    }
    this.icons.clear();
    this.hoveredIconId = null;
  }

  /**
   * Update an icon's position
   */
  public updateIconPosition(id: string, position: Point): void {
    const data = this.icons.get(id);
    if (data) {
      data.icon.position = position;
      data.container.position.set(position.x, position.y);
    }
  }

  /**
   * Update an icon's properties
   */
  public async updateIcon(id: string, updates: Partial<MapIcon>): Promise<void> {
    const data = this.icons.get(id);
    if (!data) return;

    const updatedIcon = { ...data.icon, ...updates };

    // If sprite changed, recreate the icon
    if (updates.sprite && updates.sprite !== data.icon.sprite) {
      await this.addIcon(updatedIcon);
      return;
    }

    // Update position
    if (updates.position) {
      data.container.position.set(updates.position.x, updates.position.y);
    }

    // Update scale
    if (updates.scale !== undefined) {
      data.originalScale = updates.scale;
      if (this.hoveredIconId !== id) {
        data.container.scale.set(updates.scale);
      }
    }

    // Update opacity
    if (updates.opacity !== undefined) {
      data.container.alpha = updates.opacity;
    }

    // Update label
    if (updates.name !== undefined && data.label) {
      data.label.text = updates.name;
    }

    data.icon = updatedIcon;
  }

  /**
   * Get icon by ID
   */
  public getIcon(id: string): MapIcon | null {
    return this.icons.get(id)?.icon || null;
  }

  /**
   * Get all icons
   */
  public getAllIcons(): MapIcon[] {
    return Array.from(this.icons.values()).map((data) => data.icon);
  }

  /**
   * Find icon at world position
   */
  public getIconAtPosition(x: number, y: number): MapIcon | null {
    // Check in reverse order (top-most first)
    const entries = Array.from(this.icons.entries()).reverse();

    for (const [, data] of entries) {
      const { container, icon } = data;
      const bounds = container.getBounds();

      if (
        x >= bounds.x &&
        x <= bounds.x + bounds.width &&
        y >= bounds.y &&
        y <= bounds.y + bounds.height
      ) {
        return icon;
      }
    }

    return null;
  }

  /**
   * Set label visibility
   */
  public setLabelsVisible(visible: boolean): void {
    for (const data of this.icons.values()) {
      if (data.label) {
        data.label.visible = visible;
      }
    }
  }

  /**
   * Filter icons by category
   */
  public filterByCategory(categories: IconCategory[] | null): void {
    for (const data of this.icons.values()) {
      if (categories === null) {
        data.container.visible = true;
      } else {
        data.container.visible = categories.includes(data.icon.category);
      }
    }
  }

  /**
   * Highlight specific icons
   */
  public highlightIcons(ids: string[]): void {
    for (const [id, data] of this.icons.entries()) {
      const isHighlighted = ids.includes(id);
      data.container.alpha = isHighlighted ? 1 : 0.3;
    }
  }

  /**
   * Clear icon highlights
   */
  public clearHighlights(): void {
    for (const data of this.icons.values()) {
      data.container.alpha = data.icon.opacity ?? this.config.defaultOpacity ?? 1;
    }
  }

  /**
   * Preload textures for icons
   */
  public async preloadTextures(urls: string[]): Promise<void> {
    await Promise.all(urls.map((url) => this.loadTexture(url)));
  }

  /**
   * Update layer configuration
   */
  public updateConfig(config: Partial<IconsLayerConfig>): void {
    this.config = { ...this.config, ...config };

    // Update label visibility
    if (config.showLabels !== undefined) {
      this.setLabelsVisible(config.showLabels);
    }
  }

  /**
   * Destroy the layer and clean up resources
   */
  public destroy(): void {
    this.clearIcons();
    this.textureCache.clear();
    this.container.destroy({ children: true });
  }
}

/**
 * LabelsLayer class for standalone text labels
 */
export class LabelsLayer {
  /** PixiJS container for this layer */
  public readonly container: PIXI.Container;

  /** Label graphics data */
  private labels: Map<string, { label: MapLabel; text: PIXI.Text }> = new Map();

  /** Default font settings */
  private defaultFont = {
    family: 'Arial',
    size: 14,
    color: 0xffffff,
  };

  constructor() {
    this.container = new PIXI.Container();
    this.container.sortableChildren = true;
    this.container.zIndex = 25;
  }

  /**
   * Add a label to the layer
   */
  public addLabel(label: MapLabel): void {
    if (this.labels.has(label.id)) {
      this.removeLabel(label.id);
    }

    const style = new PIXI.TextStyle({
      fontFamily: label.fontFamily ?? this.defaultFont.family,
      fontSize: label.fontSize ?? this.defaultFont.size,
      fill: label.color ?? this.defaultFont.color,
      align: 'center',
      stroke: 0x000000,
      strokeThickness: 2,
    });

    const text = new PIXI.Text(label.text, style);
    text.anchor.set(label.anchor?.x ?? 0.5, label.anchor?.y ?? 0.5);
    text.position.set(label.position.x, label.position.y);

    if (label.rotation) {
      text.rotation = label.rotation;
    }

    this.labels.set(label.id, { label, text });
    this.container.addChild(text);
  }

  /**
   * Remove a label from the layer
   */
  public removeLabel(id: string): void {
    const data = this.labels.get(id);
    if (data) {
      data.text.destroy();
      this.labels.delete(id);
    }
  }

  /**
   * Set all labels for the layer
   */
  public setLabels(labels: MapLabel[]): void {
    this.clearLabels();
    for (const label of labels) {
      this.addLabel(label);
    }
  }

  /**
   * Clear all labels
   */
  public clearLabels(): void {
    for (const data of this.labels.values()) {
      data.text.destroy();
    }
    this.labels.clear();
  }

  /**
   * Update a label's text
   */
  public updateLabelText(id: string, text: string): void {
    const data = this.labels.get(id);
    if (data) {
      data.label.text = text;
      data.text.text = text;
    }
  }

  /**
   * Update a label's position
   */
  public updateLabelPosition(id: string, position: Point): void {
    const data = this.labels.get(id);
    if (data) {
      data.label.position = position;
      data.text.position.set(position.x, position.y);
    }
  }

  /**
   * Destroy the layer
   */
  public destroy(): void {
    this.clearLabels();
    this.container.destroy({ children: true });
  }
}
