"""
Documentation API for serving project documentation files.

This module provides endpoints to access and browse the project's documentation
files stored in the docs/ directory, including development notes, architecture
guides, and implementation summaries.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
import markdown
import json

from polymer_extractor.utils.logging import Logger

router = APIRouter()
logger = Logger()

# Get the project root directory (where docs/ is located)
PROJECT_ROOT = Path(__file__).parent.parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"


@router.get("/docs", summary="List available documentation files")
def list_documentation_files() -> Dict[str, Any]:
    """
    List all available documentation files in the docs directory.
    
    Returns
    -------
    Dict[str, Any]
        Dictionary containing list of documentation files with metadata
        
    Examples
    --------
    >>> # GET /api/docs
    >>> {
    >>>     "files": [
    >>>         {
    >>>             "name": "development_notes.md",
    >>>             "title": "Development Team Notes",
    >>>             "size": 15234,
    >>>             "modified": "2025-08-22T10:30:00Z"
    >>>         }
    >>>     ],
    >>>     "total_files": 4
    >>> }
    """
    try:
        if not DOCS_DIR.exists():
            raise HTTPException(status_code=404, detail="Documentation directory not found")
        
        files = []
        for file_path in DOCS_DIR.iterdir():
            if file_path.is_file() and file_path.suffix in ['.md', '.txt', '.rst']:
                # Extract title from first line if it's a markdown heading
                title = file_path.stem.replace('_', ' ').title()
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        first_line = f.readline().strip()
                        if first_line.startswith('#'):
                            title = first_line.lstrip('#').strip()
                except Exception:
                    pass  # Use default title if can't read file
                
                stat = file_path.stat()
                files.append({
                    "name": file_path.name,
                    "title": title,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "type": file_path.suffix.lstrip('.'),
                    "url": f"/api/docs/{file_path.name}"
                })
        
        # Sort by name
        files.sort(key=lambda x: x['name'])
        
        return {
            "files": files,
            "total_files": len(files),
            "docs_directory": str(DOCS_DIR),
            "base_url": "/api/docs"
        }
        
    except Exception as e:
        logger.error(f"Error listing documentation files: {str(e)}", source="documentation_api")
        raise HTTPException(status_code=500, detail=f"Error accessing documentation: {str(e)}")


@router.get("/docs/{filename}", summary="Get specific documentation file")
def get_documentation_file(filename: str, format: Optional[str] = "markdown") -> Dict[str, Any]:
    """
    Retrieve a specific documentation file.
    
    Parameters
    ----------
    filename : str
        Name of the documentation file to retrieve
    format : str, optional
        Output format: 'markdown', 'html', or 'raw' (default: 'markdown')
        
    Returns
    -------
    Dict[str, Any]
        Dictionary containing the file content and metadata
        
    Raises
    ------
    HTTPException
        If file not found or access error occurs
        
    Examples
    --------
    >>> # GET /api/docs/development_notes.md?format=html
    >>> {
    >>>     "filename": "development_notes.md",
    >>>     "title": "Development Team Notes",
    >>>     "content": "<h1>Development Team Notes</h1>...",
    >>>     "format": "html",
    >>>     "size": 15234
    >>> }
    """
    try:
        # Validate filename to prevent directory traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        file_path = DOCS_DIR / filename
        
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail=f"Documentation file '{filename}' not found")
        
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract title from first line if it's a markdown heading
        title = filename.replace('_', ' ').replace('.md', '').title()
        lines = content.split('\n')
        if lines and lines[0].strip().startswith('#'):
            title = lines[0].lstrip('#').strip()
        
        # Convert content based on requested format
        if format.lower() == "html" and filename.endswith('.md'):
            # Convert Markdown to HTML
            html_content = markdown.markdown(content, extensions=['tables', 'fenced_code', 'toc'])
            processed_content = html_content
        elif format.lower() == "raw":
            processed_content = content
        else:
            # Default to markdown format
            processed_content = content
        
        stat = file_path.stat()
        
        return {
            "filename": filename,
            "title": title,
            "content": processed_content,
            "format": format.lower(),
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "type": file_path.suffix.lstrip('.'),
            "raw_url": f"/api/docs/{filename}?format=raw",
            "html_url": f"/api/docs/{filename}?format=html"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading documentation file '{filename}': {str(e)}", source="documentation_api")
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")


@router.get("/docs-ui", response_class=HTMLResponse, summary="Documentation browser interface")
def documentation_browser(request: Request) -> HTMLResponse:
    """
    Serve a simple HTML interface for browsing documentation files.
    
    Returns
    -------
    HTMLResponse
        HTML page with documentation browser interface
        
    Notes
    -----
    This provides a simple web interface to browse and view documentation
    files without requiring external dependencies or complex frontend frameworks.
    """
    
    # Generate the HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Polymer NLP Extractor - Documentation</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                line-height: 1.6;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            .header {{
                background: #2c3e50;
                color: white;
                padding: 20px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 2rem;
            }}
            .nav {{
                background: #34495e;
                padding: 10px 20px;
                border-bottom: 1px solid #ddd;
            }}
            .nav a {{
                color: #ecf0f1;
                text-decoration: none;
                margin-right: 20px;
                padding: 5px 10px;
                border-radius: 4px;
            }}
            .nav a:hover {{
                background: #2c3e50;
            }}
            .content {{
                padding: 20px;
                min-height: 500px;
            }}
            .doc-list {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }}
            .doc-card {{
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 15px;
                background: #f9f9f9;
                transition: box-shadow 0.2s;
            }}
            .doc-card:hover {{
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }}
            .doc-card h3 {{
                margin: 0 0 10px 0;
                color: #2c3e50;
            }}
            .doc-card p {{
                margin: 5px 0;
                color: #666;
                font-size: 0.9rem;
            }}
            .doc-card .actions {{
                margin-top: 10px;
            }}
            .doc-card .actions a {{
                background: #3498db;
                color: white;
                padding: 5px 10px;
                text-decoration: none;
                border-radius: 4px;
                font-size: 0.8rem;
                margin-right: 5px;
            }}
            .doc-card .actions a:hover {{
                background: #2980b9;
            }}
            .doc-viewer {{
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 20px;
                overflow: hidden;
            }}
            .doc-viewer .toolbar {{
                background: #f0f0f0;
                padding: 10px;
                border-bottom: 1px solid #ddd;
            }}
            .doc-viewer .content {{
                padding: 20px;
                background: white;
                max-height: 600px;
                overflow-y: auto;
            }}
            .loading {{
                text-align: center;
                padding: 40px;
                color: #666;
            }}
            .error {{
                color: #e74c3c;
                background: #fdf2f2;
                padding: 10px;
                border: 1px solid #e74c3c;
                border-radius: 4px;
                margin: 10px 0;
            }}
            pre {{
                background: #f4f4f4;
                padding: 15px;
                border-radius: 4px;
                overflow-x: auto;
            }}
            code {{
                background: #f4f4f4;
                padding: 2px 4px;
                border-radius: 2px;
                font-family: 'Courier New', monospace;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📚 Polymer NLP Extractor</h1>
                <p>Project Documentation & Developer Resources</p>
            </div>
            
            <div class="nav">
                <a href="/docs" target="_blank">🔧 API Documentation</a>
                <a href="/api/docs" target="_blank">📋 Files List (JSON)</a>
                <a href="/" target="_blank">🏠 API Root</a>
                <a href="/api/setup/health" target="_blank">❤️ Health Check</a>
            </div>
            
            <div class="content">
                <h2>📖 Available Documentation</h2>
                <p>Browse and view the project's documentation files. Click on any file to view its content.</p>
                
                <div id="doc-list" class="doc-list">
                    <div class="loading">Loading documentation files...</div>
                </div>
                
                <div id="doc-viewer" class="doc-viewer" style="display: none;">
                    <div class="toolbar">
                        <strong id="doc-title">Document Title</strong>
                        <span style="float: right;">
                            <a href="#" id="view-raw">Raw</a> | 
                            <a href="#" id="view-html">HTML</a> |
                            <a href="#" onclick="closeViewer()">Close</a>
                        </span>
                    </div>
                    <div id="doc-content" class="content">
                        Document content will appear here...
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            let currentDoc = null;
            
            // Load documentation files list
            async function loadDocsList() {{
                try {{
                    const response = await fetch('/api/docs');
                    const data = await response.json();
                    
                    if (data.files && data.files.length > 0) {{
                        renderDocsList(data.files);
                    }} else {{
                        document.getElementById('doc-list').innerHTML = '<p>No documentation files found.</p>';
                    }}
                }} catch (error) {{
                    console.error('Error loading docs:', error);
                    document.getElementById('doc-list').innerHTML = 
                        '<div class="error">Error loading documentation files: ' + error.message + '</div>';
                }}
            }}
            
            // Render the documentation files list
            function renderDocsList(files) {{
                const docList = document.getElementById('doc-list');
                docList.innerHTML = files.map(file => {{
                    const sizeKB = Math.round(file.size / 1024);
                    const modified = new Date(file.modified * 1000).toLocaleDateString();
                    
                    return `
                        <div class="doc-card">
                            <h3>${{file.title}}</h3>
                            <p><strong>File:</strong> ${{file.name}}</p>
                            <p><strong>Size:</strong> ${{sizeKB}} KB | <strong>Modified:</strong> ${{modified}}</p>
                            <div class="actions">
                                <a href="#" onclick="viewDoc('${{file.name}}', 'html')">View HTML</a>
                                <a href="#" onclick="viewDoc('${{file.name}}', 'markdown')">View Markdown</a>
                                <a href="/api/docs/${{file.name}}?format=raw" target="_blank">Download</a>
                            </div>
                        </div>
                    `;
                }}).join('');
            }}
            
            // View a specific document
            async function viewDoc(filename, format = 'html') {{
                try {{
                    document.getElementById('doc-viewer').style.display = 'block';
                    document.getElementById('doc-content').innerHTML = '<div class="loading">Loading document...</div>';
                    
                    const response = await fetch(`/api/docs/${{filename}}?format=${{format}}`);
                    const data = await response.json();
                    
                    document.getElementById('doc-title').textContent = data.title;
                    
                    if (format === 'html') {{
                        document.getElementById('doc-content').innerHTML = data.content;
                    }} else {{
                        document.getElementById('doc-content').innerHTML = `<pre>${{escapeHtml(data.content)}}</pre>`;
                    }}
                    
                    // Update toolbar links
                    document.getElementById('view-raw').href = `/api/docs/${{filename}}?format=raw`;
                    document.getElementById('view-html').onclick = () => viewDoc(filename, 'html');
                    
                    currentDoc = data;
                    
                    // Scroll to viewer
                    document.getElementById('doc-viewer').scrollIntoView({{ behavior: 'smooth' }});
                    
                }} catch (error) {{
                    console.error('Error loading document:', error);
                    document.getElementById('doc-content').innerHTML = 
                        '<div class="error">Error loading document: ' + error.message + '</div>';
                }}
            }}
            
            // Close document viewer
            function closeViewer() {{
                document.getElementById('doc-viewer').style.display = 'none';
                currentDoc = null;
            }}
            
            // Utility function to escape HTML
            function escapeHtml(text) {{
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }}
            
            // Load docs list on page load
            document.addEventListener('DOMContentLoaded', loadDocsList);
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)
