# Overworld MCP App Implementation Plan

This document outlines the changes required to expose Overworld features as a **Model Context Protocol (MCP) App**. This will allow AI agents (like Claude) to interactively generate and view maps directly within their interface.

## 1. Architecture Overview

We will introduce a new, lightweight service (`mcp-server`) responsible for handling MCP protocol requests. This service will act as an adapter between the MCP Host (the AI agent's client) and the Overworld core services.

### Components

*   **MCP Server (`/mcp-server`)**: A new Node.js/TypeScript service implementing the MCP specification (SSE transport). It exposes Tools and UI Resources.
*   **Frontend MCP View**: A simplified, standalone build of the frontend that renders *only* the map component, optimized for embedding in an iframe.
*   **Overworld Backend**: The existing FastAPI backend, which will need a new endpoint to serve raw map data.

## 2. New Service: `mcp-server`

**Location:** `mcp-server/` (new directory)
**Tech Stack:** Node.js, TypeScript, `@modelcontextprotocol/ext-apps-sdk`

### Responsibilities
1.  **Transport**: Serve SSE (Server-Sent Events) for MCP communication.
2.  **Tools**: Expose functions for the LLM to call:
    *   `upload_document`: Accepts file content/metadata.
    *   `create_map`: Triggers the map generation job.
    *   `get_map_status`: Checks job progress.
3.  **Resources**: Define `ui://` resources that point to the frontend view.
    *   `ui://overworld/map/{map_id}`: The interactive map view.

### API Definition (Draft)

```typescript
// Tool: Create Map
{
  name: "create_map",
  description: "Generate a map from a document.",
  inputSchema: {
    type: "object",
    properties: {
      document_id: { type: "string" },
      theme: { type: "string" }
    }
  }
}

// Resource: Map UI
// Returns a resource pointing to the hosted frontend view
// content: { type: "resource", uri: "ui://overworld/map/{map_id}", mimeType: "text/html" }
```

## 3. Frontend Changes

We need to reuse the existing `MapRenderer` component but serve it without the full application shell (sidebar, navigation, auth guards).

### Action Items
1.  **New Entry Point**: Create `frontend/src/mcp-entry.tsx`.
    *   This entry point will mount a specific route (e.g., `/mcp/map/:id`) that renders *only* the `MapRenderer`.
    *   It should handle `window.addEventListener('message', ...)` to receive updates from the MCP Host if necessary (or just fetch data by ID).
2.  **Vite Configuration**: Update `vite.config.ts` to support multi-page app (MPA) build or simply handle the routing within the existing SPA but ensure CSS is isolated/clean for the iframe.
3.  **Data Fetching**: The `MapRenderer` wrapper in the MCP view must fetch `MapData` from the backend using the ID provided in the URL.

## 4. Backend Changes

The FastAPI backend needs to support the specific data requirements of the MCP App.

### Action Items
1.  **New Endpoint**: `GET /api/v1/maps/{map_id}/data`
    *   **Purpose**: Return the raw `MapData` JSON structure (Tiles, Roads, Icons) required by the `MapRenderer`.
    *   **Current State**: Missing. The frontend currently uses sample data or internal hooks.
2.  **CORS Configuration**: Ensure the `mcp-server` (if running on a separate port) is allowed to call these API endpoints.

## 5. Implementation Steps

### Phase 1: Backend Preparation
1.  Implement `GET /api/v1/maps/{map_id}/data` in `backend/app/api/v1/routers/maps.py` (create if needed).
    *   This endpoint should query the database for the generated map and serialize it to the `MapData` schema expected by the frontend.

### Phase 2: Frontend Adaptation
1.  Create `frontend/src/pages/McpMapPage.tsx`.
    *   Simplified page component that accepts `mapId` from URL params.
    *   Uses `useMapData` hook to fetch from the new backend endpoint.
    *   Renders `MapRenderer` full-screen.
2.  Add route `/mcp/map/:mapId` to `frontend/src/main.tsx` (or new entry point).

### Phase 3: MCP Server Construction
1.  Initialize `mcp-server` project with `@modelcontextprotocol/ext-apps-sdk`.
2.  Implement SSE transport.
3.  Implement `create_map` tool (calls Backend `POST /api/v1/maps/generate`).
4.  Implement `ui://` resource handling to point to `https://overworld.app/mcp/map/{id}`.

### Phase 4: Integration & Status Function
1.  Implement the "Status Function" requirement.
    *   The MCP App can listen to the job status.
    *   When the map is ready, the Tool result returns the `ui://` resource.
    *   The Map View should ideally show a marker or specific view state based on the request.

## 6. Docker & Deployment
1.  Add `mcp-server` to `compose.yml`.
2.  Ensure it has network access to `backend` and `postgres` (if needed, though it should prefer HTTP API).
