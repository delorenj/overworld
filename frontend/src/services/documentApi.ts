/**
 * API service for document upload operations
 */

import axios, { AxiosProgressEvent } from 'axios';
import type { DocumentUploadResponse } from '../types/document';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost/api';

/**
 * Upload a document file to the server
 *
 * @param file - File to upload (markdown or PDF)
 * @param onProgress - Optional callback for upload progress
 * @returns Promise with upload response
 */
export async function uploadDocument(
  file: File,
  onProgress?: (progress: number) => void
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await axios.post<DocumentUploadResponse>(
    `${API_BASE_URL}/v1/documents/upload`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent: AxiosProgressEvent) => {
        if (onProgress && progressEvent.total) {
          const percentage = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percentage);
        }
      },
    }
  );

  return response.data;
}

/**
 * Validate file before upload
 *
 * @param file - File to validate
 * @returns Validation result with error message if invalid
 */
export function validateFile(file: File): { valid: boolean; error?: string } {
  const allowedExtensions = ['.md', '.markdown', '.txt', '.pdf'];
  const maxSizesMB = {
    markdown: 5,
    pdf: 10,
  };

  // Check file extension
  const fileName = file.name.toLowerCase();
  const hasValidExtension = allowedExtensions.some((ext) => fileName.endsWith(ext));

  if (!hasValidExtension) {
    return {
      valid: false,
      error: 'Invalid file type. Please upload a Markdown (.md, .txt) or PDF file.',
    };
  }

  // Check file size
  const isPDF = fileName.endsWith('.pdf');
  const maxSize = isPDF ? maxSizesMB.pdf : maxSizesMB.markdown;
  const fileSizeMB = file.size / (1024 * 1024);

  if (fileSizeMB > maxSize) {
    return {
      valid: false,
      error: `File size (${fileSizeMB.toFixed(2)} MB) exceeds maximum allowed size (${maxSize} MB).`,
    };
  }

  return { valid: true };
}
