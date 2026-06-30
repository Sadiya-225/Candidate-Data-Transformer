#!/usr/bin/env python
"""Run the web server for the Candidate Data Transformer."""

import sys
from transformer.web_server import app

if __name__ == "__main__":
    print("=" * 70)
    print("Candidate Data Transformer - API Server")
    print("=" * 70)
    print()
    print("Backend API Starting...")
    print("  • API Server: http://localhost:5000")
    print("  • React Frontend: http://localhost:3000")
    print()
    print("Next Steps:")
    print("  1. Keep this terminal open for the backend")
    print("  2. Open a new terminal and run: cd frontend && npm start")
    print("  3. Your browser will open at http://localhost:3000")
    print()
    print("Features:")
    print("  • Drag & drop file upload (CSV, JSON, PDF, DOCX, TXT)")
    print("  • Config selection with live preview")
    print("  • Multiple result views (JSON, Cards, Statistics)")
    print("  • Download transformed data as JSON")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 70)
    print()

    app.run(debug=False, host="0.0.0.0", port=5000, use_reloader=False)
