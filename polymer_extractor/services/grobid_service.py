# polymer_extractor/services/grobid_service.py

"""
GROBID Service for Polymer NLP Extractor.

Provides comprehensive document processing capabilities using GROBID server:
- Server lifecycle management (start/stop/status)
- Document format validation and conversion
- TEI XML extraction and cleaning
- Metadata extraction and storage
- Integration with Appwrite for persistent storage

Key Features:
- Supports PDF, XML, and HTML input formats
- Automatic document conversion to PDF
- GROBID TEI XML extraction
- Metadata extraction from scientific papers
- Local file storage with optional cloud backup
- Non-blocking storage operations
- Comprehensive error handling and logging

Dependencies:
- GROBID server installation
- WeasyPrint (for HTML to PDF conversion)
- ReportLab (for XML to PDF conversion)
- Appwrite Python SDK
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
from polymer_extractor.storage.bucket_manager import BucketManager
from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils.paths import WORKSPACE_DIR, EXTRACTED_XML_DIR

logger = Logger()


class GrobidService:
    """
    High-level service for GROBID document processing operations.

    Manages the complete workflow from document ingestion to metadata storage,
    with built-in resilience and non-blocking storage operations.
    """

    def __init__(self, server_url: str = "http://localhost:8070"):
        """
        Initialize GROBID service with optional custom server URL.

        Parameters
        ----------
        server_url : str, optional
            GROBID server URL. Defaults to "http://localhost:8070".
        """
        self.grobid_server_url = server_url
        self.grobid_process = None
        self.supported_formats = {'.pdf', '.xml', '.html', '.htm'}

        # Initialize storage services
        self.db_manager = DatabaseManager()
        self.bucket_manager = BucketManager()

        logger.info(f"GROBID Service initialized with server: {server_url}", source="GrobidService")

    # === SERVER MANAGEMENT ===

    def start_server(self, grobid_home: str = None, port: int = 8070) -> None:
        """
        Start GROBID server in background process.

        Parameters
        ----------
        grobid_home : str, optional
            Path to GROBID installation directory.
        port : int, optional
            Server port. Defaults to 8070.

        Raises
        ------
        RuntimeError
            If server fails to start or GROBID installation not found.
        """
        if grobid_home is None:
            grobid_home = os.path.join(WORKSPACE_DIR, "grobid-0.8.2")

        grobid_path = Path(grobid_home)

        if not grobid_path.exists():
            raise RuntimeError(f"GROBID installation not found at: {grobid_home}")

        gradle_wrapper = grobid_path / "gradlew"
        if not gradle_wrapper.exists():
            raise RuntimeError(f"Gradle wrapper not found at: {gradle_wrapper}")

        try:
            # Check if already running
            try:
                self.check_server_status()
                logger.info("GROBID server already running", source="GrobidService")
                return
            except:
                pass

            logger.info(f"Starting GROBID server from: {grobid_home}", source="GrobidService")

            # Start GROBID server
            self.grobid_process = subprocess.Popen(
                [str(gradle_wrapper), "run"],
                cwd=str(grobid_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False
            )

            # Wait for server to be ready
            max_attempts = 30
            for attempt in range(max_attempts):
                try:
                    time.sleep(2)
                    self.check_server_status()
                    logger.info(f"GROBID server started successfully (attempt {attempt + 1})", source="GrobidService")
                    return
                except:
                    if attempt == max_attempts - 1:
                        raise RuntimeError("GROBID server failed to start within timeout period")
                    continue

        except Exception as e:
            logger.error("Failed to start GROBID server", source="GrobidService", error=e)
            raise

    def stop_server(self) -> None:
        """
        Stop the GROBID server process.
        """
        try:
            if self.grobid_process:
                self.grobid_process.terminate()
                self.grobid_process.wait()
                self.grobid_process = None
                logger.info("GROBID server stopped", source="GrobidService")
            else:
                logger.warning("No GROBID process to stop", source="GrobidService")
        except Exception as e:
            logger.error("Failed to stop GROBID server", source="GrobidService", error=e)
            raise

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
        original_filename = original_filename or file_path.name
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
            pdf_path = self._validate_and_convert_document(file_path, output_stem)
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

            logger.info(f"Core processing completed for: {original_filename}", source="GrobidService")

            # Step 6: Attempt storage (non-blocking)
            try:
                self._store_to_appwrite(pdf_path, local_tei_path, metadata)
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

    def _store_to_appwrite(self, pdf_path: Path, tei_path: Path, metadata: Dict[str, Any]):
        """
        Stores processed files and metadata to Appwrite using proper URL retrieval.

        Parameters
        ----------
        pdf_path : Path
            Path to processed PDF file.
        tei_path : Path
            Path to processed TEI XML file.
        metadata : Dict[str, Any]
            Document metadata to store.
        """
        logger.info("Storing files and metadata to Appwrite...", source="GrobidService")

        # Upload original PDF
        pdf_upload = self.bucket_manager.upload_file(
            bucket_id="raw_documents_bucket",
            file_path=str(pdf_path)
        )

        # Get PDF file URL using the get_file_url method
        pdf_url = self.bucket_manager.get_file_url(
            bucket_id="raw_documents_bucket",
            file_name=pdf_path.name
        )

        # Upload cleaned TEI XML
        tei_upload = self.bucket_manager.upload_file(
            bucket_id="processed_xml_bucket",
            file_path=str(tei_path)
        )

        # Get TEI file URL using the get_file_url method
        tei_url = self.bucket_manager.get_file_url(
            bucket_id="processed_xml_bucket",
            file_name=tei_path.name
        )

        # Update metadata with the proper file URLs
        metadata.update({
            "file_url": tei_url,  # TEI XML file URL
            "pdf_url": pdf_url   # Original PDF file URL
        })

        # Save metadata to database
        self.db_manager.create_document(
            collection_id="file_metadata",
            data=metadata
        )

        logger.info("Successfully stored files and metadata to Appwrite", source="GrobidService")