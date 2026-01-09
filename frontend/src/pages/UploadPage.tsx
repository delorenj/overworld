/**
 * Upload Page
 *
 * Landing page for document upload
 */

import { DocumentUpload } from '../components/DocumentUpload';
import './UploadPage.css';

export function UploadPage() {
  return (
    <div className="upload-page">
      <header className="page-header">
        <h1 className="page-title">Overworld</h1>
        <p className="page-subtitle">Transform your documentation into interactive maps</p>
      </header>

      <main className="page-content">
        <DocumentUpload />
      </main>

      <footer className="page-footer">
        <p>Powered by AI • Markdown & PDF Support</p>
      </footer>
    </div>
  );
}
