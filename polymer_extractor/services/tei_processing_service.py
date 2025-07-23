# polymer_extractor/services/tei_processing_service.py

"""
TEIProcessingService for Polymer NLP Extractor

Cleans and prepares GROBID TEI XML files for downstream NLP tasks.

Key Responsibilities:
  - Parses and cleans TEI XML
  - Preserves abstract content
  - Relabels structural tags (figures, tables, formulas)
  - Uploads cleaned TEI with `_cleaned` suffix to Appwrite
  - Updates existing metadata documents (only missing fields)
  - Returns API-ready response without triggering tokenization or windowing
"""

import os
from datetime import datetime
from pathlib import Path

from lxml import etree

from polymer_extractor.storage.bucket_manager import BucketManager
from polymer_extractor.storage.database_manager import DatabaseManager
from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils.paths import PROCESSED_XML_DIR

TEI_NS = "http://www.tei-c.org/ns/1.0"
NSMAP = {"tei": TEI_NS}

logger = Logger()


class TEIProcessingService:
    """Service for cleaning and preparing TEI XML content."""

    ALLOWED_METADATA_KEYS = {
        "file_name", "doi", "title", "authors", "journal",
        "published_on", "grobid_version", "processed_on",
        "file_url", "pdf_url"
    }

    def __init__(self):
        self.bucket = BucketManager()
        self.db = DatabaseManager()

    def process(self, input_tei_path: str, existing_metadata: dict = None) -> dict:
        """
        Main entrypoint for TEI file processing.

        Parameters
        ----------
        input_tei_path : str
            Path to the TEI XML file.
        existing_metadata : dict, optional
            Previously stored Appwrite metadata, used to avoid duplicate writes.

        Returns
        -------
        dict
            Rich response containing file path, metadata, and status flags.
        """
        if not os.path.exists(input_tei_path):
            return self._error_response(f"File not found: {input_tei_path}", "tei_file_not_found")

        try:
            tree, root = self._parse_tei(input_tei_path)

            # Extract metadata and merge with existing
            extracted_meta = self._extract_metadata(tree)
            cleaned_file_name = Path(input_tei_path).stem + "_cleaned.tei.xml"
            extracted_meta.update({
                "file_name": cleaned_file_name,
                "grobid_version": "0.8.3-SNAPSHOT",
                "processed_on": datetime.now().isoformat() + "Z"
            })

            # Clean and relabel XML
            self._remove_non_content(root)
            self._relabel_figures_tables(root)

            # Write cleaned file
            cleaned_path = self._write_cleaned_tei(tree, cleaned_file_name)

            # Upload cleaned file
            storage_success, upload_resp, storage_errors = self._upload_cleaned_tei(cleaned_path)
            if storage_success:
                extracted_meta["file_url"] = self.bucket.get_file_url("processed_xml_bucket", cleaned_file_name)

            # Update metadata
            record = existing_metadata or {}
            for key in self.ALLOWED_METADATA_KEYS:
                if not record.get(key) and extracted_meta.get(key):
                    record[key] = extracted_meta[key]

            self._update_metadata(record)

            logger.info(f"[TEIProcessing] Complete: {cleaned_file_name}",
                        source="TEIProcessingService.process", category="tei", event_type="tei_complete")

            return {
                "success": True,
                "message": f"Successfully processed TEI: {cleaned_file_name}",
                "cleaned_tei_path": cleaned_path,
                "metadata": record,
                "storage_success": storage_success,
                "storage_errors": storage_errors,
                "next_stage_payload": {
                    "file_name": cleaned_file_name,
                    "metadata": record,
                    "cleaned_tei_path": cleaned_path
                }
            }

        except Exception as e:
            return self._error_response(f"Processing failed: {e}", "tei_processing_error", exc=e)

    def _parse_tei(self, file_path: str):
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(file_path, parser)
        root = tree.getroot()
        return tree, root

    def _extract_metadata(self, tree: etree._ElementTree) -> dict:
        meta = {
            "doi": self._text_or_none(tree.find(".//tei:idno[@type='DOI']", NSMAP)),
            "title": self._text_or_none(tree.find(".//tei:titleStmt//tei:title", NSMAP)),
            "journal": self._text_or_none(tree.find(".//tei:monogr//tei:title", NSMAP)),
            "published_on": tree.find(".//tei:publicationStmt//tei:date[@type='published']", NSMAP).attrib.get("when", None)
                              if tree.find(".//tei:publicationStmt//tei:date[@type='published']", NSMAP) else None,
            "authors": ", ".join(
                filter(None, [
                    " ".join(filter(None, [
                        pers.findtext("tei:forename[@type='first']", namespaces=NSMAP),
                        pers.findtext("tei:surname", namespaces=NSMAP)
                    ]))
                    for pers in tree.findall(".//tei:sourceDesc//tei:author//tei:persName", NSMAP)
                ])
            )
        }
        return meta

    def _remove_non_content(self, root: etree._Element) -> None:
        abstract = root.find(".//tei:teiHeader//tei:profileDesc//tei:abstract", NSMAP)
        if abstract is not None:
            text_el = root.find(".//tei:text", NSMAP)
            if text_el is not None:
                text_el.insert(0, abstract)

        for tag in root.findall(".//tei:teiHeader", NSMAP):
            tag.getparent().remove(tag)

        for tag in ("ref", "note"):
            for node in root.findall(f".//tei:{tag}", NSMAP):
                node.getparent().remove(node)

        for div_type in ("acknowledgement", "annex", "references"):
            for div in root.findall(f".//tei:back//tei:div[@type='{div_type}']", NSMAP):
                div.getparent().remove(div)

    def _relabel_figures_tables(self, root: etree._Element) -> None:
        for fig in root.findall(".//tei:figure", NSMAP):
            fig.tag = f"{{{TEI_NS}}}table" if fig.get("type") == "table" else f"{{{TEI_NS}}}figure"
        for formula in root.findall(".//tei:formula", NSMAP):
            formula.tag = f"{{{TEI_NS}}}formula"

    def _write_cleaned_tei(self, tree: etree._ElementTree, file_name: str) -> str:
        output_path = Path(PROCESSED_XML_DIR) / file_name
        os.makedirs(output_path.parent, exist_ok=True)
        tree.write(str(output_path), encoding="UTF-8", xml_declaration=True, pretty_print=True)
        return str(output_path)

    def _upload_cleaned_tei(self, cleaned_path: str):
        try:
            upload_resp = self.bucket.upload_file("processed_xml_bucket", cleaned_path)
            return True, upload_resp, []
        except Exception as e:
            return False, None, [str(e)]

    def _update_metadata(self, metadata: dict):
        try:
            file_name = metadata.get("file_name")
            candidates = self.db.list_documents("file_metadata")
            match = next((doc for doc in candidates if doc.get("file_name") == file_name), None)
            if match:
                self.db.update_document("file_metadata", document_id=match["$id"], data=metadata)
            else:
                self.db.create_document("file_metadata", data=metadata)
        except Exception as e:
            logger.error(f"Failed to update metadata for {metadata.get('file_name')}",
                         source="TEIProcessingService._update_metadata", error=e)

    def _error_response(self, message: str, error_type: str, exc: Exception = None) -> dict:
        logger.error(message, source="TEIProcessingService", error=exc, event_type=error_type)
        return {
            "success": False,
            "message": message,
            "metadata": {},
            "cleaned_tei_path": None,
            "storage_success": False,
            "storage_errors": [str(exc)] if exc else [],
            "next_stage_payload": None
        }

    @staticmethod
    def _text_or_none(element: etree.Element) -> str:
        return element.text.strip() if element is not None and element.text else None
