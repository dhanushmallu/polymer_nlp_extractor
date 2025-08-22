# polymer_extractor/services/grobid_service.py

"""
GROBID Service for Polymer NLP Extractor.

Provides comprehensive document processing capabilities using GROBID server:
- Document format validation and conversion
- TEI XML extraction and cleaning
- Metadata extraction and storage
- Integration with BucketClient for persistent storage

Key Features:
- Supports PDF, XML, and HTML input formats
- Automatic document conversion to PDF
- GROBID TEI XML extraction
- Metadata extraction from scientific papers
- Local file storage with optional cloud backup
- Non-blocking storage operations
- Comprehensive error handling and logging

Dependencies:
- GROBID server (managed externally via server_manager)
- WeasyPrint (for HTML to PDF conversion)
- ReportLab (for XML to PDF conversion)
- BucketClient for storage operations

Note: Server management is handled by the central server_manager.
      This service focuses on document processing operations only.
"""

import os
import subprocess
import time
import requests
from pathlib import Path
from typing import Union, Dict, Any, Optional
from datetime import datetime
import xml.etree.ElementTree as ET

# Optional dependencies for document conversion
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from lxml import etree
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from polymer_extractor.storage.database_manager import DatabaseManager
from polymer_extractor.storage.bucket_client import BucketClient
from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils.paths import WORKSPACE_DIR, EXTRACTED_XML_DIR, get_storage_path, get_local_path
from polymer_extractor.utils.paths import path_resolver

logger = Logger()


class GrobidService:
    """
    High-level service for GROBID document processing operations.

    Manages the complete workflow from document ingestion to metadata storage,
    with built-in resilience and non-blocking storage operations.
    
    Note: Server management is handled by the central server_manager.
          This service focuses on document processing operations only.
    """

    def __init__(self, server_url: str = None):
        """
        Initialize GROBID service with optional custom server URL.

        Parameters
        ----------
        server_url : str, optional
            GROBID server URL. If not provided, will be constructed from environment variables.
            Defaults to "http://{GROBID_HOST}:{GROBID_PORT}" from env or "http://localhost:8070".
        """
        if server_url is None:
            # Build URL from environment variables
            grobid_host = os.getenv("GROBID_HOST", "localhost")
            grobid_port = os.getenv("GROBID_PORT", "8070")
            server_url = f"http://{grobid_host}:{grobid_port}"
            
        self.grobid_server_url = server_url
        self.supported_formats = {'.pdf', '.xml', '.html', '.htm'}

        # Initialize storage services
        self.db_manager = DatabaseManager()
        self.bucket_client = BucketClient()

        logger.info(f"GROBID Service initialized with server: {server_url}", source="GrobidService")

    # === DOCUMENT PROCESSING ===

    def check_server_status(self) -> bool:
        """
        Check if GROBID server is running and responsive.

        Returns
        -------
        bool
            True if server is responsive.

        Raises
        ------
        RuntimeError
            If server is not responding.
        """
        try:
            response = requests.get(f"{self.grobid_server_url}/api/isalive", timeout=5)
            if response.status_code == 200:
                return True
            else:
                raise RuntimeError(f"GROBID server returned status {response.status_code}")
        except Exception as e:
            raise RuntimeError(f"GROBID server is not responding: {str(e)}")

    # === DOCUMENT PROCESSING ===

    def process_document(self, file_path: Union[str, Path], filename_stem: str = None, original_filename: str = None) -> Dict[str, Any]:
        """
        Executes the complete document processing workflow with proper filename handling.

        Workflow:
        1. Validate and convert document to PDF if necessary
        2. Extract TEI XML using GROBID
        3. Extract metadata from TEI
        4. Clean TEI XML
        5. Save processed files locally
        6. Attempt storage operations (non-blocking)

        Parameters
        ----------
        file_path : str or Path
            Path to the document file.
        filename_stem : str, optional
            Custom filename stem to use for output files.
        original_filename : str, optional
            Original filename for metadata tracking.

        Returns
        -------
        Dict[str, Any]
            Processing results including paths, metadata, and storage status.

        Raises
        ------
        ValueError
            If document type is not supported.
        RuntimeError
            If core processing steps fail.
        """
        file_path = Path(file_path)
        
        # Resolve path to local filesystem for processing
        local_file_path = Path(path_resolver.to_local_path(file_path))
        
        original_filename = original_filename or local_file_path.name
        output_stem = filename_stem or Path(original_filename).stem

        logger.info(f"Starting document processing workflow for: {original_filename}", source="GrobidService")

        result = {
            'original_file': original_filename,
            'pdf_file': None,
            'tei_content': None,
            'cleaned_tei_content': None,
            'metadata': {},
            'local_tei_path': None,
            'storage_success': False,
            'storage_errors': []
        }

        try:
            # Step 1: Validate and convert to PDF
            pdf_path = self._validate_and_convert_document(local_file_path, output_stem)
            result['pdf_file'] = pdf_path.name  # Use the properly named PDF

            # Step 2: Extract TEI XML with GROBID
            tei_content = self._extract_with_grobid(pdf_path)
            result['tei_content'] = tei_content

            # Step 3: Extract metadata
            metadata = self._extract_metadata(tei_content)
            metadata.update({
                "file_name": original_filename,  # Use original filename
                "grobid_version": self._extract_grobid_version(tei_content),
                "processed_on": datetime.now().isoformat() + "Z"
            })
            result['metadata'] = metadata

            # Step 4: Clean TEI XML
            cleaned_tei = self._clean_tei(tei_content)
            result['cleaned_tei_content'] = cleaned_tei

            # Step 5: Save locally (always succeeds)
            local_tei_path = self._save_tei_locally(cleaned_tei, output_stem)
            result['local_tei_path'] = str(local_tei_path)
            
            # Generate storage paths for API responses
            result['storage_tei_path'] = path_resolver.to_storage_path(local_tei_path, "extracted_xml")
            result['storage_pdf_path'] = path_resolver.to_storage_path(pdf_path, "raw_documents")

            logger.info(f"Core processing completed for: {original_filename}", source="GrobidService")

            # Step 6: Attempt storage (non-blocking)
            try:
                self._store_files_and_metadata(pdf_path, local_tei_path, metadata)
                result['storage_success'] = True
                logger.info(f"Storage completed for: {original_filename}", source="GrobidService")
            except Exception as storage_error:
                result['storage_errors'].append(str(storage_error))
                logger.warning(f"Storage failed but processing succeeded for: {original_filename}",
                               source="GrobidService", error=storage_error)

            return result

        except Exception as e:
            logger.error(f"Document processing failed for: {original_filename}", source="GrobidService", error=e)
            raise

    def _validate_and_convert_document(self, file_path: Path, output_stem: str = None) -> Path:
        """
        Validates document type and converts non-PDF documents to PDF with proper naming.

        Parameters
        ----------
        file_path : Path
            Path to input document.
        output_stem : str, optional
            Desired output filename stem.

        Returns
        -------
        Path
            Path to validated/converted PDF document.
        """
        file_ext = file_path.suffix.lower()
        output_stem = output_stem or file_path.stem

        if file_ext not in self.supported_formats:
            raise ValueError(f"Unsupported document type: {file_ext}. "
                             f"Supported formats: {', '.join(self.supported_formats)}")

        if file_ext == '.pdf':
            # Rename PDF to use proper output stem if needed
            if file_path.stem != output_stem:
                new_pdf_path = file_path.parent / f"{output_stem}.pdf"
                file_path.rename(new_pdf_path)
                logger.info(f"Renamed PDF to: {new_pdf_path.name}", source="GrobidService")
                return new_pdf_path
            return file_path

        logger.info(f"Converting {file_ext} document to PDF: {output_stem}", source="GrobidService")

        if file_ext in ['.html', '.htm']:
            return self._convert_html_to_pdf(file_path, output_stem)
        elif file_ext == '.xml':
            return self._convert_xml_to_pdf(file_path, output_stem)

        raise ValueError(f"Conversion not implemented for {file_ext}")

    def _convert_html_to_pdf(self, html_path: Path, output_stem: str) -> Path:
        """
        Converts HTML document to PDF with proper naming.
        """
        if not WEASYPRINT_AVAILABLE:
            raise RuntimeError("WeasyPrint is not available. Cannot convert HTML to PDF.")

        try:
            output_path = html_path.parent / f"{output_stem}.pdf"

            # Read HTML content
            html_content = html_path.read_text(encoding='utf-8')

            # Convert to PDF
            HTML(string=html_content, base_url=str(html_path.parent)).write_pdf(str(output_path))

            logger.info(f"Successfully converted HTML to PDF: {output_path.name}", source="GrobidService")
            return output_path

        except Exception as e:
            logger.error(f"Failed to convert HTML to PDF: {str(e)}", source="GrobidService")
            raise RuntimeError(f"HTML to PDF conversion failed: {str(e)}") from e

    def _convert_xml_to_pdf(self, xml_path: Path, output_stem: str) -> Path:
        """
        Converts XML document to PDF with proper naming.
        """
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError("ReportLab is not available. Cannot convert XML to PDF.")

        try:
            output_path = xml_path.parent / f"{output_stem}.pdf"

            # Read XML content and extract text
            xml_content = xml_path.read_text(encoding='utf-8')

            # Parse XML to extract text content
            try:
                root = etree.fromstring(xml_content.encode('utf-8'))
                text_content = etree.tostring(root, method="text", encoding="unicode")
            except etree.XMLSyntaxError:
                # If parsing fails, use raw content
                text_content = xml_content

            # Create PDF
            doc = SimpleDocTemplate(str(output_path), pagesize=letter)
            styles = getSampleStyleSheet()
            story = []

            # Split content into paragraphs
            for paragraph in text_content.split('\n\n'):
                if paragraph.strip():
                    story.append(Paragraph(paragraph.strip(), styles['Normal']))

            doc.build(story)

            logger.info(f"Successfully converted XML to PDF: {output_path.name}", source="GrobidService")
            return output_path

        except Exception as e:
            logger.error(f"Failed to convert XML to PDF: {str(e)}", source="GrobidService")
            raise RuntimeError(f"XML to PDF conversion failed: {str(e)}") from e

    def _extract_with_grobid(self, pdf_path: Path) -> str:
        """
        Extract TEI XML from PDF using GROBID server.

        Parameters
        ----------
        pdf_path : Path
            Path to PDF file.

        Returns
        -------
        str
            Extracted TEI XML content.
        """
        try:
            self.check_server_status()
        except RuntimeError as e:
            raise RuntimeError(f"GROBID server not available: {e}")

        try:
            with open(pdf_path, 'rb') as pdf_file:
                files = {'input': pdf_file}
                response = requests.post(
                    f"{self.grobid_server_url}/api/processFulltextDocument",
                    files=files,
                    timeout=120  # 2-minute timeout for processing
                )

            if response.status_code != 200:
                raise RuntimeError(f"GROBID processing failed with status {response.status_code}: {response.text}")

            tei_content = response.text
            if not tei_content.strip():
                raise RuntimeError("GROBID returned empty content")

            logger.info(f"Successfully extracted TEI XML from: {pdf_path.name}", source="GrobidService")
            return tei_content

        except Exception as e:
            logger.error(f"GROBID extraction failed for: {pdf_path.name}", source="GrobidService", error=e)
            raise

    def _extract_metadata(self, tei_content: str) -> Dict[str, Any]:
        """
        Extract metadata from TEI XML content.

        Parameters
        ----------
        tei_content : str
            TEI XML content.

        Returns
        -------
        Dict[str, Any]
            Extracted metadata dictionary.
        """
        metadata = {
            "doi": None,
            "title": None,
            "authors": None,
            "journal": None,
            "published_on": None
        }

        try:
            root = ET.fromstring(tei_content)

            # Define namespaces
            ns = {'tei': 'http://www.tei-c.org/ns/1.0'}

            # Extract title
            title_elem = root.find('.//tei:titleStmt/tei:title', ns)
            if title_elem is not None and title_elem.text:
                metadata["title"] = title_elem.text.strip()

            # Extract authors
            authors = []
            for author in root.findall('.//tei:sourceDesc//tei:author', ns):
                author_parts = []

                # Get forename and surname
                forename = author.find('.//tei:forename', ns)
                surname = author.find('.//tei:surname', ns)

                if forename is not None and forename.text:
                    author_parts.append(forename.text.strip())
                if surname is not None and surname.text:
                    author_parts.append(surname.text.strip())

                if author_parts:
                    authors.append(" ".join(author_parts))

            if authors:
                metadata["authors"] = ", ".join(authors)

            # Extract journal information
            journal_elem = root.find('.//tei:sourceDesc//tei:title[@level="j"]', ns)
            if journal_elem is not None and journal_elem.text:
                metadata["journal"] = journal_elem.text.strip()

            # Extract DOI
            doi_elem = root.find('.//tei:idno[@type="DOI"]', ns)
            if doi_elem is not None and doi_elem.text:
                metadata["doi"] = doi_elem.text.strip()

            # Extract publication date
            date_elem = root.find('.//tei:sourceDesc//tei:date', ns)
            if date_elem is not None:
                date_text = date_elem.get('when') or date_elem.text
                if date_text:
                    metadata["published_on"] = date_text.strip()

            logger.debug("Metadata extraction completed", source="GrobidService")
            return metadata

        except Exception as e:
            logger.warning(f"Metadata extraction failed, returning empty metadata", source="GrobidService", error=e)
            return metadata

    def _extract_grobid_version(self, tei_content: str) -> str:
        """
        Extract GROBID version from TEI XML.

        Parameters
        ----------
        tei_content : str
            TEI XML content.

        Returns
        -------
        str
            GROBID version string.
        """
        try:
            root = ET.fromstring(tei_content)

            # Look for application element with GROBID information
            app_elem = root.find('.//{http://www.tei-c.org/ns/1.0}application[@ident="GROBID"]')
            if app_elem is not None:
                version = app_elem.get('version')
                if version:
                    return version

            # Fallback: look in processing instruction or comment
            if 'GROBID' in tei_content:
                import re
                version_match = re.search(r'GROBID\s+(\d+\.\d+\.\d+)', tei_content)
                if version_match:
                    return version_match.group(1)

            return "unknown"

        except Exception as e:
            logger.debug(f"Could not extract GROBID version: {e}", source="GrobidService")
            return "unknown"

    def _clean_tei(self, tei_content: str) -> str:
        """
        Clean and format TEI XML content.

        Parameters
        ----------
        tei_content : str
            Raw TEI XML content.

        Returns
        -------
        str
            Cleaned TEI XML content.
        """
        try:
            # Parse and reformat XML
            root = ET.fromstring(tei_content)
            ET.indent(root, space="  ", level=0)
            cleaned_content = ET.tostring(root, encoding='unicode', xml_declaration=True)

            logger.debug("TEI XML cleaning completed", source="GrobidService")
            return cleaned_content

        except Exception as e:
            logger.warning(f"TEI cleaning failed, returning original content", source="GrobidService", error=e)
            return tei_content

    def _save_tei_locally(self, tei_content: str, filename_stem: str) -> Path:
        """
        Save TEI XML content to local file system.

        Parameters
        ----------
        tei_content : str
            TEI XML content to save.
        filename_stem : str
            Base filename without extension.

        Returns
        -------
        Path
            Path to saved TEI file.
        """
        try:
            # Ensure output directory exists
            output_dir = Path(EXTRACTED_XML_DIR)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Create output file path
            tei_filename = f"{filename_stem}.tei.xml"
            tei_path = output_dir / tei_filename

            # Write TEI content
            tei_path.write_text(tei_content, encoding='utf-8')

            logger.info(f"Saved TEI XML locally: {tei_path}", source="GrobidService")
            return tei_path

        except Exception as e:
            logger.error(f"Failed to save TEI locally", source="GrobidService", error=e)
            raise

    def _store_files_and_metadata(self, pdf_path: Path, tei_path: Path, metadata: Dict[str, Any]):
        """
        Stores processed files and metadata using BucketClient and DatabaseManager.

        Parameters
        ----------
        pdf_path : Path
            Path to processed PDF file.
        tei_path : Path
            Path to processed TEI XML file.
        metadata : Dict[str, Any]
            Document metadata to store.
        """
        logger.info("Storing files and metadata...", source="GrobidService")

        # Upload original PDF
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        pdf_upload_result = self.bucket_client.upload_file(
            file_path=get_storage_path("raw_documents", pdf_path.name),
            content=pdf_content,
            metadata={**metadata, "file_type": "pdf", "source": "grobid_processing"}
        )

        # Upload cleaned TEI XML
        with open(tei_path, 'rb') as f:
            tei_content = f.read()
        tei_upload_result = self.bucket_client.upload_file(
            file_path=get_storage_path("extracted_xml", tei_path.name),
            content=tei_content,
            metadata={**metadata, "file_type": "tei_xml", "source": "grobid_processing"}
        )

        # Update metadata with file paths
        metadata.update({
            "file_url": get_storage_path("extracted_xml", tei_path.name),  # TEI XML file path
            "pdf_url": get_storage_path("raw_documents", pdf_path.name),   # Original PDF file path
            "pdf_upload_success": pdf_upload_result.get("success", False),
            "tei_upload_success": tei_upload_result.get("success", False)
        })

        # Save metadata to database
        self.db_manager.create_record(
            "file_metadata",
            metadata
        )

        logger.info("Successfully stored files and metadata", source="GrobidService")