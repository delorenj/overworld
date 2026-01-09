/**
 * TypeScript types for document upload API
 */

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  size_bytes: number;
  r2_url: string;
  uploaded_at: string;
}

export interface UploadError {
  detail: string;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}

export type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';
