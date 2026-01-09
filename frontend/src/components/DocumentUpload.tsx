/**
 * DocumentUpload Component
 *
 * Drag-and-drop file upload component with progress tracking and error handling
 */

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { uploadDocument, validateFile } from '../services/documentApi';
import type { DocumentUploadResponse, UploadStatus } from '../types/document';
import './DocumentUpload.css';

export function DocumentUpload() {
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [uploadedDocument, setUploadedDocument] = useState<DocumentUploadResponse | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const file = acceptedFiles[0];

    // Validate file before upload
    const validation = validateFile(file);
    if (!validation.valid) {
      setUploadStatus('error');
      setErrorMessage(validation.error || 'Invalid file');
      return;
    }

    // Reset state
    setErrorMessage('');
    setUploadedDocument(null);
    setUploadStatus('uploading');
    setUploadProgress(0);

    try {
      const response = await uploadDocument(file, (progress) => {
        setUploadProgress(progress);
      });

      setUploadStatus('success');
      setUploadedDocument(response);
      setUploadProgress(100);
    } catch (error: any) {
      setUploadStatus('error');
      setUploadProgress(0);

      // Extract error message from API response
      if (error.response?.data?.detail) {
        setErrorMessage(error.response.data.detail);
      } else if (error.message) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage('Failed to upload file. Please try again.');
      }
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/markdown': ['.md', '.markdown'],
      'text/plain': ['.txt'],
      'application/pdf': ['.pdf'],
    },
    maxFiles: 1,
    multiple: false,
  });

  const resetUpload = () => {
    setUploadStatus('idle');
    setUploadProgress(0);
    setErrorMessage('');
    setUploadedDocument(null);
  };

  return (
    <div className="document-upload">
      <h2>Upload Document</h2>
      <p className="upload-description">
        Upload a markdown or PDF document to generate your project map
      </p>

      {/* Dropzone Area */}
      <div
        {...getRootProps()}
        className={`dropzone ${isDragActive ? 'dropzone-active' : ''} ${
          uploadStatus === 'uploading' ? 'dropzone-uploading' : ''
        }`}
      >
        <input {...getInputProps()} />
        {uploadStatus === 'idle' && (
          <>
            {isDragActive ? (
              <p className="dropzone-text">Drop the file here...</p>
            ) : (
              <>
                <p className="dropzone-text">
                  Drag and drop a file here, or click to select a file
                </p>
                <p className="dropzone-hint">Supported formats: Markdown (.md, .txt), PDF (.pdf)</p>
                <p className="dropzone-hint">Maximum size: 5 MB (Markdown), 10 MB (PDF)</p>
              </>
            )}
          </>
        )}

        {uploadStatus === 'uploading' && (
          <div className="upload-progress">
            <p className="upload-progress-text">Uploading...</p>
            <div className="progress-bar-container">
              <div className="progress-bar" style={{ width: `${uploadProgress}%` }} />
            </div>
            <p className="upload-progress-percentage">{uploadProgress}%</p>
          </div>
        )}
      </div>

      {/* Error Message */}
      {uploadStatus === 'error' && (
        <div className="upload-message upload-error">
          <svg
            className="message-icon"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div>
            <p className="message-title">Upload Failed</p>
            <p className="message-detail">{errorMessage}</p>
          </div>
          <button onClick={resetUpload} className="btn btn-secondary">
            Try Again
          </button>
        </div>
      )}

      {/* Success Message */}
      {uploadStatus === 'success' && uploadedDocument && (
        <div className="upload-message upload-success">
          <svg
            className="message-icon"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div>
            <p className="message-title">Upload Successful!</p>
            <p className="message-detail">
              <strong>{uploadedDocument.filename}</strong> ({(uploadedDocument.size_bytes / 1024).toFixed(2)} KB)
            </p>
            <p className="message-timestamp">
              Uploaded at {new Date(uploadedDocument.uploaded_at).toLocaleString()}
            </p>
          </div>
          <button onClick={resetUpload} className="btn btn-primary">
            Upload Another
          </button>
        </div>
      )}
    </div>
  );
}
