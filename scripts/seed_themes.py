"""Seed default themes into the database."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.theme import Theme


DEFAULT_THEMES = [
    {
        "name": "Light Mode",
        "slug": "light-mode",
        "description": "Clean and bright theme for daytime use",
        "is_premium": False,
        "is_active": True,
        "asset_manifest": {
            "version": "1.0",
            "palette": {
                "primary": "#3B82F6",
                "secondary": "#8B5CF6",
                "background": "#FFFFFF",
                "surface": "#F8FAFC",
                "text": "#0F172A",
                "text_secondary": "#64748B",
                "accent": "#F59E0B",
                "success": "#10B981",
                "warning": "#F59E0B",
                "error": "#EF4444",
            },
            "typography": {
                "heading_font": "Inter",
                "body_font": "Inter",
                "mono_font": "JetBrains Mono",
            },
            "icons": {
                "milestone": "r2://overworld/themes/light-mode/icons/milestone.svg",
                "region": "r2://overworld/themes/light-mode/icons/region.svg",
                "road": "r2://overworld/themes/light-mode/icons/road.svg",
            },
            "backgrounds": ["r2://overworld/themes/light-mode/backgrounds/default.png"],
            "effects": {
                "drop_shadow": True,
                "gradient_overlays": False,
                "particle_effects": False,
            },
        },
    },
    {
        "name": "Dark Mode",
        "slug": "dark-mode",
        "description": "Easy on the eyes for late-night planning",
        "is_premium": False,
        "is_active": True,
        "asset_manifest": {
            "version": "1.0",
            "palette": {
                "primary": "#60A5FA",
                "secondary": "#A78BFA",
                "background": "#0F172A",
                "surface": "#1E293B",
                "text": "#F1F5F9",
                "text_secondary": "#94A3B8",
                "accent": "#FBBF24",
                "success": "#34D399",
                "warning": "#FBBF24",
                "error": "#F87171",
            },
            "typography": {
                "heading_font": "Inter",
                "body_font": "Inter",
                "mono_font": "JetBrains Mono",
            },
            "icons": {
                "milestone": "r2://overworld/themes/dark-mode/icons/milestone.svg",
                "region": "r2://overworld/themes/dark-mode/icons/region.svg",
                "road": "r2://overworld/themes/dark-mode/icons/road.svg",
            },
            "backgrounds": ["r2://overworld/themes/dark-mode/backgrounds/default.png"],
            "effects": {
                "drop_shadow": True,
                "gradient_overlays": True,
                "particle_effects": False,
            },
        },
    },
    {
        "name": "Neon Cyberpunk",
        "slug": "neon-cyberpunk",
        "description": "Vibrant neon colors for a futuristic vibe",
        "is_premium": True,
        "is_active": True,
        "asset_manifest": {
            "version": "1.0",
            "palette": {
                "primary": "#FF00FF",
                "secondary": "#00FFFF",
                "background": "#0A0015",
                "surface": "#1A0530",
                "text": "#FFFFFF",
                "text_secondary": "#C084FC",
                "accent": "#FFFF00",
                "success": "#00FF00",
                "warning": "#FFAA00",
                "error": "#FF0055",
            },
            "typography": {
                "heading_font": "Orbitron",
                "body_font": "Rajdhani",
                "mono_font": "Fira Code",
            },
            "icons": {
                "milestone": "r2://overworld/themes/neon-cyberpunk/icons/milestone.svg",
                "region": "r2://overworld/themes/neon-cyberpunk/icons/region.svg",
                "road": "r2://overworld/themes/neon-cyberpunk/icons/road.svg",
            },
            "backgrounds": ["r2://overworld/themes/neon-cyberpunk/backgrounds/default.png"],
            "effects": {
                "drop_shadow": True,
                "gradient_overlays": True,
                "particle_effects": True,
            },
        },
    },
    {
        "name": "Forest Green",
        "slug": "forest-green",
        "description": "Natural and calming earth tones",
        "is_premium": True,
        "is_active": True,
        "asset_manifest": {
            "version": "1.0",
            "palette": {
                "primary": "#10B981",
                "secondary": "#059669",
                "background": "#F0FDF4",
                "surface": "#ECFDF5",
                "text": "#064E3B",
                "text_secondary": "#047857",
                "accent": "#FBBF24",
                "success": "#10B981",
                "warning": "#F59E0B",
                "error": "#DC2626",
            },
            "typography": {
                "heading_font": "Merriweather",
                "body_font": "Open Sans",
                "mono_font": "Source Code Pro",
            },
            "icons": {
                "milestone": "r2://overworld/themes/forest-green/icons/milestone.svg",
                "region": "r2://overworld/themes/forest-green/icons/region.svg",
                "road": "r2://overworld/themes/forest-green/icons/road.svg",
            },
            "backgrounds": ["r2://overworld/themes/forest-green/backgrounds/default.png"],
            "effects": {
                "drop_shadow": True,
                "gradient_overlays": False,
                "particle_effects": False,
            },
        },
    },
    {
        "name": "Ocean Blue",
        "slug": "ocean-blue",
        "description": "Calm and professional blue palette",
        "is_premium": True,
        "is_active": True,
        "asset_manifest": {
            "version": "1.0",
            "palette": {
                "primary": "#0EA5E9",
                "secondary": "#0284C7",
                "background": "#F0F9FF",
                "surface": "#E0F2FE",
                "text": "#0C4A6E",
                "text_secondary": "#075985",
                "accent": "#F59E0B",
                "success": "#10B981",
                "warning": "#F59E0B",
                "error": "#DC2626",
            },
            "typography": {
                "heading_font": "Poppins",
                "body_font": "Lato",
                "mono_font": "Roboto Mono",
            },
            "icons": {
                "milestone": "r2://overworld/themes/ocean-blue/icons/milestone.svg",
                "region": "r2://overworld/themes/ocean-blue/icons/region.svg",
                "road": "r2://overworld/themes/ocean-blue/icons/road.svg",
            },
            "backgrounds": ["r2://overworld/themes/ocean-blue/backgrounds/default.png"],
            "effects": {
                "drop_shadow": True,
                "gradient_overlays": False,
                "particle_effects": False,
            },
        },
    },
]


async def seed_themes():
    """Seed default themes into the database."""
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        for theme_data in DEFAULT_THEMES:
            # Check if theme exists
            stmt = select(Theme).where(Theme.slug == theme_data["slug"])
            result = await session.execute(stmt)
            existing_theme = result.scalar_one_or_none()

            if existing_theme:
                print(f"Theme '{theme_data['name']}' already exists, skipping")
                continue

            # Create theme
            theme = Theme(**theme_data)
            session.add(theme)
            print(f"Created theme: {theme_data['name']}")

        await session.commit()
        print(f"\nSeeded {len(DEFAULT_THEMES)} themes successfully!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_themes())
