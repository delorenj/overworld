/**
 * ExportDialog Component
 *
 * Modal dialog for exporting maps with configuration options:
 * - Format selection (PNG/SVG)
 * - Resolution selection (1x, 2x, 4x)
 * - Watermark preview for free users
 * - Export history list
 */

import React, { useEffect, useState } from 'react';
import {
  useMapExport,
  ExportFormat,
} from '../../hooks/useMapExport';
import './ExportDialog.css';

interface ExportDialogProps {
  mapId: number;
  mapName: string;
  isPremium: boolean;
  isOpen: boolean;
  onClose: () => void;
}

export const ExportDialog: React.FC<ExportDialogProps> = ({
  mapId,
  mapName,
  isPremium,
  isOpen,
  onClose,
}) => {
  const {
    loading,
    error,
    currentExport,
    exports,
    pollingActive,
    requestExport,
    downloadExport,
    fetchExportHistory,
    clearError,
  } = useMapExport();

  // Form state
  const [format, setFormat] = useState<ExportFormat>('png');
  const [resolution, setResolution] = useState<1 | 2 | 4>(1);

  // Load export history when dialog opens
  useEffect(() => {
    if (isOpen) {
      fetchExportHistory(mapId);
    }
  }, [isOpen, mapId, fetchExportHistory]);

  // Handle export request
  const handleExport = async () => {
    clearError();
    try {
      await requestExport(mapId, {
        format,
        resolution,
        include_watermark: !isPremium, // Free users always get watermark
      });
    } catch (err) {
      // Error is handled in hook
    }
  };

  // Handle download
  const handleDownload = (exportId: number) => {
    downloadExport(exportId);
  };

  // Format file size
  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return 'N/A';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Format date
  const formatDate = (dateString?: string): string => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  // Get status badge class
  const getStatusClass = (status: string): string => {
    switch (status) {
      case 'completed':
        return 'status-completed';
      case 'processing':
      case 'pending':
        return 'status-processing';
      case 'failed':
        return 'status-failed';
      default:
        return '';
    }
  };

  if (!isOpen) return null;

  return (
    <div className="export-dialog-overlay" onClick={onClose}>
      <div className="export-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="export-dialog-header">
          <h2>Export Map: {mapName}</h2>
          <button className="close-button" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="export-dialog-content">
          {/* Export Configuration */}
          <section className="export-config">
            <h3>Export Configuration</h3>

            <div className="form-group">
              <label htmlFor="format">Format</label>
              <select
                id="format"
                value={format}
                onChange={(e) => setFormat(e.target.value as ExportFormat)}
                disabled={loading || pollingActive}
              >
                <option value="png">PNG (Raster Image)</option>
                <option value="svg">SVG (Vector Image)</option>
              </select>
              <small>PNG is best for sharing, SVG for editing</small>
            </div>

            <div className="form-group">
              <label htmlFor="resolution">Resolution</label>
              <select
                id="resolution"
                value={resolution}
                onChange={(e) => setResolution(Number(e.target.value) as 1 | 2 | 4)}
                disabled={loading || pollingActive}
              >
                <option value="1">1x (1024×768)</option>
                <option value="2">2x (2048×1536) - HD</option>
                <option value="4">4x (4096×3072) - Ultra HD</option>
              </select>
              <small>Higher resolution = larger file size</small>
            </div>

            {/* Watermark Notice */}
            {!isPremium && (
              <div className="watermark-notice">
                <strong>Note:</strong> Free tier exports include an "Overworld" watermark.
                Upgrade to premium to remove watermarks.
              </div>
            )}

            {/* Current Export Status */}
            {currentExport && (
              <div className="current-export-status">
                <h4>Current Export</h4>
                <div className={`status-badge ${getStatusClass(currentExport.status)}`}>
                  {currentExport.status.toUpperCase()}
                </div>
                {currentExport.status === 'completed' && currentExport.download_url && (
                  <button
                    className="download-button"
                    onClick={() => handleDownload(currentExport.id)}
                  >
                    Download
                  </button>
                )}
                {currentExport.error_message && (
                  <div className="error-message">{currentExport.error_message}</div>
                )}
              </div>
            )}

            {/* Error Display */}
            {error && <div className="error-message">{error}</div>}

            {/* Export Button */}
            <button
              className="export-button"
              onClick={handleExport}
              disabled={loading || pollingActive}
            >
              {loading || pollingActive ? 'Processing...' : 'Export Map'}
            </button>
          </section>

          {/* Export History */}
          <section className="export-history">
            <h3>Export History</h3>
            {exports.length === 0 ? (
              <p className="no-exports">No previous exports</p>
            ) : (
              <div className="exports-list">
                {exports.map((exp) => (
                  <div key={exp.id} className="export-item">
                    <div className="export-item-header">
                      <span className="export-format">
                        {exp.format.toUpperCase()} ({exp.resolution}x)
                      </span>
                      <span className={`status-badge ${getStatusClass(exp.status)}`}>
                        {exp.status}
                      </span>
                    </div>
                    <div className="export-item-details">
                      <span className="export-date">{formatDate(exp.created_at)}</span>
                      {exp.file_size && (
                        <span className="export-size">{formatFileSize(exp.file_size)}</span>
                      )}
                      {exp.watermarked && (
                        <span className="watermark-badge">Watermarked</span>
                      )}
                    </div>
                    {exp.status === 'completed' && exp.download_url && (
                      <button
                        className="download-button-small"
                        onClick={() => handleDownload(exp.id)}
                      >
                        Download
                      </button>
                    )}
                    {exp.error_message && (
                      <div className="error-message-small">{exp.error_message}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
};
