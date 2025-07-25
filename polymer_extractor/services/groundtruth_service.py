# polymer_extractor/services/groundtruth_service.py

"""
Ground Truth Service for Polymer NLP Extractor.

Provides comprehensive ground truth data processing capabilities:
- Upload and validation of CSV/JSON ground truth files
- Intelligent column alignment and cleaning for CSV files
- DataFrame standardization and storage
- Integration with Appwrite for persistent storage
- Model evaluation metrics tracking

Key Features:
- Supports both CSV and JSON input formats
- Automatic column name cleaning and standardization
- Intelligent misalignment detection and correction for CSV
- Flexible column slot handling (e.g., polymer_1, polymer_2, etc.)
- Local and cloud storage with metadata tracking
- Comprehensive error handling and logging

Dependencies:
- pandas (for DataFrame operations)
- numpy (for numerical operations)
- Appwrite Python SDK
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Union, Dict, Any, List

import pandas as pd

from polymer_extractor.storage.bucket_manager import BucketManager
from polymer_extractor.storage.database_manager import DatabaseManager
from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils.paths import TESTING_DATA_DIR
logger = Logger()


class GroundTruthService:
    """
    High-level service for ground truth data processing and management.

    Handles the complete workflow from data ingestion to standardized storage,
    with built-in intelligence for misalignment correction and data validation.
    """

    # Required minimum columns for ground truth data
    REQUIRED_COLUMNS = {
        'filename', 'heading', 'polymer', 'material',
        'property', 'symbol', 'unit', 'value', 'sentence'
    }

    # Expandable columns that can have slots (e.g., polymer_1, polymer_2)
    EXPANDABLE_COLUMNS = {
        'polymer', 'material', 'property', 'symbol', 'unit', 'value'
    }

    # Non-expandable columns
    FIXED_COLUMNS = {'filename', 'heading', 'sentence'}

    def __init__(self):
        """
        Initialize Ground Truth service.
        """
        self.db_manager = DatabaseManager()
        self.bucket_manager = BucketManager()

        # Ensure ground truth directory exists
        self.ground_truth_dir = Path(TESTING_DATA_DIR)
        self.ground_truth_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Ground Truth Service initialized", source="GroundTruthService")

    # === DATA PROCESSING WORKFLOW ===

    def process_ground_truth_file(self, file_path: Union[str, Path],
                                  filename_stem: str = None,
                                  original_filename: str = None,
                                  target_input: str = None) -> Dict[str, Any]:
        """
        Execute the complete ground truth processing workflow.

        Workflow:
        1. Validate file format and content
        2. Load and parse data (CSV/JSON)
        3. Clean and standardize column names
        4. Perform intelligent alignment correction (CSV only)
        5. Convert to standardized DataFrame
        6. Save locally and to cloud storage
        7. Store metadata

        Parameters
        ----------
        file_path : str or Path
            Path to the ground truth file.
        filename_stem : str, optional
            Custom filename stem for output files.
        original_filename : str, optional
            Original filename for metadata tracking.
        target_input : str, optional
            Target input filename that this ground truth is associated with.
            This allows you to specify which input file this ground truth data
            is designed to test against (e.g., "057.pdf", "research_paper.xml").

        Returns
        -------
        Dict[str, Any]
            Processing results including paths, metadata, and storage status.
        """
        file_path = Path(file_path)
        original_filename = original_filename or file_path.name
        output_stem = filename_stem or Path(original_filename).stem

        logger.info(f"Starting ground truth processing for: {original_filename}",
                    source="GroundTruthService")

        result = {
            'original_file': original_filename,
            'file_type': None,
            'raw_data': None,
            'cleaned_data': None,
            'standardized_dataframe': None,
            'metadata': {},
            'dataset_name': None,  # Will be set later
            'local_path': None,
            'storage_success': False,
            'storage_errors': []
        }

        try:
            # Step 1: Validate file format
            file_type = self._validate_file_format(file_path)
            result['file_type'] = file_type

            # Step 2: Load and parse data
            raw_data = self._load_data(file_path, file_type)
            result['raw_data'] = len(raw_data) if isinstance(raw_data, (list, pd.DataFrame)) else None

            # Step 3: Process based on file type
            if file_type == 'json':
                cleaned_data = self._process_json_data(raw_data)
            else:  # csv
                cleaned_data = self._process_csv_data(raw_data)

            result['cleaned_data'] = len(cleaned_data)

            # Step 4: Convert to standardized DataFrame
            standardized_df = self._create_standardized_dataframe(cleaned_data)
            result['standardized_dataframe'] = len(standardized_df)

            # Step 5: Generate metadata with target_input
            metadata = self._generate_metadata(standardized_df, original_filename, file_type, target_input)
            result['metadata'] = metadata
            # Add dataset name to metadata
            dataset_name = filename_stem or Path(original_filename).stem
            metadata["dataset_name"] = dataset_name
            result["dataset_name"] = dataset_name

            # Step 6: Save locally
            local_path = self._save_locally(standardized_df, output_stem)
            result['local_path'] = str(local_path)

            logger.info(f"Core processing completed for: {original_filename}",
                        source="GroundTruthService")

            # Step 7: Attempt cloud storage (non-blocking)
            try:
                self._store_to_appwrite(local_path, standardized_df, metadata, dataset_name)
                result['storage_success'] = True
                logger.info(f"Storage completed for: {original_filename}",
                            source="GroundTruthService")
            except Exception as storage_error:
                result['storage_errors'].append(str(storage_error))
                logger.warning(f"Storage failed but processing succeeded for: {original_filename}",
                               source="GroundTruthService", error=storage_error)

            return result

        except Exception as e:
            logger.error(f"Ground truth processing failed for: {original_filename}",
                         source="GroundTruthService", error=e)
            raise

    # === FILE VALIDATION AND LOADING ===

    def _validate_file_format(self, file_path: Path) -> str:
        """
        Validate file format and determine processing type.

        Parameters
        ----------
        file_path : Path
            Path to the file.

        Returns
        -------
        str
            File type ('csv' or 'json').

        Raises
        ------
        ValueError
            If file format is not supported.
        """
        file_ext = file_path.suffix.lower()

        if file_ext not in ['.csv', '.json']:
            raise ValueError(f"Unsupported file format: {file_ext}. "
                             f"Supported formats: .csv, .json")

        if not file_path.exists():
            raise FileNotFoundError(f"Ground truth file not found: {file_path}")

        file_type = 'json' if file_ext == '.json' else 'csv'
        logger.info(f"Validated {file_type.upper()} ground truth file: {file_path.name}",
                    source="GroundTruthService")

        return file_type

    def _load_data(self, file_path: Path, file_type: str) -> Union[pd.DataFrame, List[Dict]]:
        """
        Load data from file based on type with robust CSV parsing.

        Parameters
        ----------
        file_path : Path
            Path to the file.
        file_type : str
            Type of file ('csv' or 'json').

        Returns
        -------
        Union[pd.DataFrame, List[Dict]]
            Loaded data.
        """
        try:
            if file_type == 'json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if not isinstance(data, list):
                    raise ValueError("JSON data must be a list of objects")

                logger.info(f"Loaded {len(data)} records from JSON file",
                            source="GroundTruthService")
                return data

            else:  # csv
                # Enhanced CSV loading with error handling
                try:
                    # First attempt: standard loading
                    df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
                except pd.errors.ParserError as e:
                    logger.warning(f"Standard CSV parsing failed: {e}. Attempting robust parsing.",
                                   source="GroundTruthService")

                    # Second attempt: handle inconsistent field counts
                    df = pd.read_csv(
                        file_path,
                        dtype=str,
                        keep_default_na=False,
                        on_bad_lines='skip',  # Skip problematic lines
                        engine='python',  # Use Python parser for better error handling
                        quoting=1,  # QUOTE_ALL
                        skipinitialspace=True
                    )
                    logger.info(f"Used robust CSV parsing, some lines may have been skipped",
                                source="GroundTruthService")

                logger.info(f"Loaded CSV with {len(df)} rows and {len(df.columns)} columns",
                            source="GroundTruthService")
                return df

        except Exception as e:
            logger.error(f"Failed to load {file_type} data from: {file_path}",
                         source="GroundTruthService", error=e)
            raise

    def _load_csv_with_fallback(self, file_path: Path) -> pd.DataFrame:
        """
        Load CSV with multiple fallback strategies for problematic files.

        Parameters
        ----------
        file_path : Path
            Path to the CSV file.

        Returns
        -------
        pd.DataFrame
            Loaded DataFrame.
        """
        strategies = [
            # Strategy 1: Standard pandas
            {
                'method': 'standard',
                'kwargs': {'dtype': str, 'keep_default_na': False}
            },
            # Strategy 2: Skip bad lines
            {
                'method': 'skip_bad_lines',
                'kwargs': {
                    'dtype': str,
                    'keep_default_na': False,
                    'on_bad_lines': 'skip',
                    'engine': 'python'
                }
            },
            # Strategy 3: Use different separator detection
            {
                'method': 'auto_sep',
                'kwargs': {
                    'dtype': str,
                    'keep_default_na': False,
                    'sep': None,  # Auto-detect separator
                    'engine': 'python'
                }
            },
            # Strategy 4: Manual line-by-line parsing
            {
                'method': 'manual',
                'kwargs': {}
            }
        ]

        for strategy in strategies:
            try:
                logger.info(f"Trying CSV loading strategy: {strategy['method']}",
                            source="GroundTruthService")

                if strategy['method'] == 'manual':
                    return self._manual_csv_parse(file_path)
                else:
                    df = pd.read_csv(file_path, **strategy['kwargs'])
                    logger.info(f"Successfully loaded CSV using {strategy['method']} strategy",
                                source="GroundTruthService")
                    return df

            except Exception as e:
                logger.debug(f"Strategy {strategy['method']} failed: {e}",
                             source="GroundTruthService")
                continue

        raise ValueError("All CSV loading strategies failed")

    def _manual_csv_parse(self, file_path: Path) -> pd.DataFrame:
        """
        Manually parse CSV line by line to handle severely malformed files.

        Parameters
        ----------
        file_path : Path
            Path to the CSV file.

        Returns
        -------
        pd.DataFrame
            Manually parsed DataFrame.
        """
        import csv

        rows = []
        headers = None
        max_cols = 0

        with open(file_path, 'r', encoding='utf-8') as f:
            # Read all lines to determine maximum column count
            lines = f.readlines()

            for i, line in enumerate(lines):
                try:
                    # Try to parse with csv module
                    row = list(csv.reader([line.strip()]))[0]
                    if i == 0:
                        headers = row
                        max_cols = len(row)
                    else:
                        max_cols = max(max_cols, len(row))
                        rows.append(row)
                except Exception:
                    logger.warning(f"Skipping malformed line {i + 1}",
                                   source="GroundTruthService")
                    continue

        # Pad rows to have consistent column count
        padded_rows = []
        for row in rows:
            padded_row = row + [''] * (max_cols - len(row))
            padded_rows.append(padded_row[:max_cols])  # Trim if too long

        # Pad headers if necessary
        if headers and len(headers) < max_cols:
            headers.extend([f'col_{i}' for i in range(len(headers), max_cols)])

        df = pd.DataFrame(padded_rows, columns=headers)
        logger.info(f"Manual parsing created DataFrame with {len(df)} rows and {len(df.columns)} columns",
                    source="GroundTruthService")

        return df

    # === JSON DATA PROCESSING ===

    def _process_json_data(self, json_data: List[Dict]) -> pd.DataFrame:
        """
        Process JSON data into standardized format.

        Parameters
        ----------
        json_data : List[Dict]
            List of JSON objects.

        Returns
        -------
        pd.DataFrame
            Cleaned and standardized DataFrame.
        """
        logger.info("Processing JSON ground truth data", source="GroundTruthService")

        # Convert to DataFrame
        df = pd.DataFrame(json_data)

        # Clean column names
        df = self._clean_column_names(df)

        # Validate required columns
        self._validate_required_columns(df)

        # Handle missing values
        df = df.fillna('')

        logger.info(f"Processed JSON data: {len(df)} records with {len(df.columns)} columns",
                    source="GroundTruthService")

        return df

    # === CSV DATA PROCESSING ===

    def _process_csv_data(self, csv_df: pd.DataFrame) -> pd.DataFrame:
        """
        Process CSV data with intelligent alignment correction.

        Parameters
        ----------
        csv_df : pd.DataFrame
            Raw CSV DataFrame.

        Returns
        -------
        pd.DataFrame
            Cleaned and aligned DataFrame.
        """
        logger.info("Processing CSV ground truth data with alignment correction",
                    source="GroundTruthService")

        # Handle empty or malformed DataFrame
        if csv_df.empty:
            raise ValueError("CSV file contains no valid data")

        # Step 1: Clean column names
        df = self._clean_column_names(csv_df)

        # Step 2: Remove completely empty rows
        df = df.dropna(how='all').reset_index(drop=True)

        # Step 3: Detect and organize slotted columns
        column_structure = self._analyze_column_structure(df)

        # Step 4: Perform intelligent alignment
        aligned_df = self._perform_intelligent_alignment(df, column_structure)

        # Step 5: Validate and finalize
        self._validate_required_columns(aligned_df, check_base_only=True)

        logger.info(f"Processed CSV data: {len(aligned_df)} records with alignment correction",
                    source="GroundTruthService")

        return aligned_df

    def _clean_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and standardize column names.

        Parameters
        ----------
        df : pd.DataFrame
            Input DataFrame.

        Returns
        -------
        pd.DataFrame
            DataFrame with cleaned column names.
        """
        # Create a copy to avoid modifying original
        cleaned_df = df.copy()

        # Clean column names: lowercase, strip, remove prefixes/suffixes
        new_columns = []
        for col in cleaned_df.columns:
            # Convert to lowercase and strip whitespace
            clean_col = str(col).lower().strip()

            # Remove common prefixes/suffixes
            clean_col = re.sub(r'^(gt_|groundtruth_|target_|expected_)', '', clean_col)
            clean_col = re.sub(r'(_gt|_groundtruth|_target|_expected)$', '', clean_col)

            # Handle filename variations
            if clean_col in ['file', 'filename', 'file_name', 'target_input']:
                clean_col = 'filename'

            new_columns.append(clean_col)

        cleaned_df.columns = new_columns

        logger.debug(f"Cleaned {len(new_columns)} column names", source="GroundTruthService")
        return cleaned_df

    def _analyze_column_structure(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """
        Analyze column structure to identify slotted columns and their organization.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame with cleaned column names.

        Returns
        -------
        Dict[str, Dict]
            Structure analysis with slots and ordering information.
        """
        structure = {}

        for base_col in self.EXPANDABLE_COLUMNS:
            slots = {}

            # Find all columns that belong to this base column
            for col in df.columns:
                if col == base_col:
                    slots[0] = col  # Base column without number
                elif col.startswith(f"{base_col}_"):
                    # Extract slot number
                    try:
                        slot_num = int(col.split('_')[-1])
                        slots[slot_num] = col
                    except ValueError:
                        continue

            if slots:
                structure[base_col] = {
                    'slots': slots,
                    'max_slot': max(slots.keys()),
                    'slot_count': len(slots),
                    'ordered_columns': [slots[i] for i in sorted(slots.keys())]
                }

        logger.debug(f"Analyzed column structure: {len(structure)} expandable column groups",
                     source="GroundTruthService")

        return structure

    def _perform_intelligent_alignment(self, df: pd.DataFrame,
                                       column_structure: Dict[str, Dict]) -> pd.DataFrame:
        """
        Perform intelligent alignment correction for misaligned CSV data.

        Parameters
        ----------
        df : pd.DataFrame
            Input DataFrame.
        column_structure : Dict[str, Dict]
            Column structure analysis.

        Returns
        -------
        pd.DataFrame
            Aligned DataFrame.
        """
        logger.info("Performing intelligent alignment correction", source="GroundTruthService")

        aligned_df = df.copy()
        alignment_corrections = 0

        # Process each row individually
        for idx in range(len(aligned_df)):
            row_corrections = self._align_row(aligned_df, idx, column_structure)
            alignment_corrections += row_corrections

        logger.info(f"Applied {alignment_corrections} alignment corrections",
                    source="GroundTruthService")

        return aligned_df

    def _align_row(self, df: pd.DataFrame, row_idx: int,
                   column_structure: Dict[str, Dict]) -> int:
        """
        Align a single row's data within its column slots.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame being processed.
        row_idx : int
            Index of the row to align.
        column_structure : Dict[str, Dict]
            Column structure information.

        Returns
        -------
        int
            Number of corrections applied to this row.
        """
        corrections = 0

        for base_col, info in column_structure.items():
            if info['slot_count'] <= 1:
                continue  # No alignment needed for single slots

            # Get values for this column group in this row
            slot_values = []
            slot_columns = info['ordered_columns']

            for col in slot_columns:
                value = df.at[row_idx, col]
                slot_values.append((col, value if pd.notna(value) and value != '' else None))

            # Find non-empty values and their current positions
            non_empty_values = [(col, val) for col, val in slot_values if val is not None]

            if not non_empty_values:
                continue  # No values to align

            # Check if values are already properly aligned (starting from first slot)
            properly_aligned = True
            for i, (col, val) in enumerate(non_empty_values):
                expected_col = slot_columns[i]
                if col != expected_col:
                    properly_aligned = False
                    break

            if not properly_aligned:
                # Clear all slots first
                for col in slot_columns:
                    df.at[row_idx, col] = ''

                # Realign values to start from first slot
                for i, (_, val) in enumerate(non_empty_values[:len(slot_columns)]):
                    target_col = slot_columns[i]
                    df.at[row_idx, target_col] = val
                    corrections += 1

        return corrections

    # === DATAFRAME STANDARDIZATION ===

    def _create_standardized_dataframe(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create a standardized DataFrame with all required columns.

        Parameters
        ----------
        data : pd.DataFrame
            Processed data.

        Returns
        -------
        pd.DataFrame
            Standardized DataFrame.
        """
        logger.info("Creating standardized DataFrame", source="GroundTruthService")

        # Ensure all required base columns exist
        standardized_df = data.copy()

        for req_col in self.REQUIRED_COLUMNS:
            if req_col not in standardized_df.columns:
                standardized_df[req_col] = ''

        # Clean and validate data types
        standardized_df = self._clean_data_types(standardized_df)

        # Add processing metadata columns
        standardized_df['processed_at'] = datetime.now().isoformat() + "Z"
        standardized_df['record_id'] = range(1, len(standardized_df) + 1)

        logger.info(f"Created standardized DataFrame: {len(standardized_df)} records",
                    source="GroundTruthService")

        return standardized_df

    def _clean_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and standardize data types in the DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            Input DataFrame.

        Returns
        -------
        pd.DataFrame
            DataFrame with cleaned data types.
        """
        cleaned_df = df.copy()

        # Fill NaN values with empty strings for text columns
        text_columns = ['filename', 'heading', 'polymer', 'material', 'property',
                        'symbol', 'unit', 'sentence']

        for col in text_columns:
            if col in cleaned_df.columns:
                cleaned_df[col] = cleaned_df[col].fillna('').astype(str)

        # Clean numeric value column
        if 'value' in cleaned_df.columns:
            cleaned_df['value'] = cleaned_df['value'].fillna('')
            # Try to convert to numeric where possible, but keep as string for flexibility
            cleaned_df['value'] = cleaned_df['value'].astype(str)

        return cleaned_df

    # === VALIDATION ===

    def _validate_required_columns(self, df: pd.DataFrame, check_base_only: bool = False):
        """
        Validate that required columns exist in the DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame to validate.
        check_base_only : bool, optional
            If True, only check for base column names (e.g., 'polymer' instead of 'polymer_1').

        Raises
        ------
        ValueError
            If required columns are missing.
        """
        existing_columns = set(df.columns)

        if check_base_only:
            # For CSV with slots, check if base columns exist in any form
            missing_columns = []
            for req_col in self.REQUIRED_COLUMNS:
                if req_col in existing_columns:
                    continue

                # Check if any slotted version exists
                has_slotted = any(col.startswith(f"{req_col}_") for col in existing_columns)
                if not has_slotted:
                    missing_columns.append(req_col)
        else:
            # Direct column check
            missing_columns = list(self.REQUIRED_COLUMNS - existing_columns)

        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

        logger.debug("Column validation passed", source="GroundTruthService")

    # === METADATA GENERATION ===

    def _generate_metadata(self, df: pd.DataFrame, original_filename: str,
                           file_type: str, target_input: str = None) -> Dict[str, Any]:
        """
        Generate comprehensive metadata for the processed ground truth data.

        Parameters
        ----------
        df : pd.DataFrame
            Processed DataFrame.
        original_filename : str
            Original filename.
        file_type : str
            File type ('csv' or 'json').
        target_input : str, optional
            Target input filename that this ground truth is associated with.

        Returns
        -------
        Dict[str, Any]
            Metadata dictionary.
        """
        # Calculate statistics
        stats = {
            'total_records': len(df),
            'total_columns': len(df.columns),
            'non_empty_records': len(df.dropna(how='all')),
            'unique_filenames': df['filename'].nunique() if 'filename' in df.columns else 0,
            'unique_polymers': df['polymer'].nunique() if 'polymer' in df.columns else 0,
            'unique_properties': df['property'].nunique() if 'property' in df.columns else 0
        }

        data_quality = {
            'completeness_ratio': (stats['non_empty_records'] / stats['total_records']) * 100 if stats[
                                                                                                     'total_records'] > 0 else 0,
            'has_all_required_columns': all(col in df.columns for col in self.REQUIRED_COLUMNS)
        }

        metadata = {
            'original_filename': original_filename,
            'file_type': file_type,
            'processed_at': datetime.now().isoformat() + "Z",
            'statistics': json.dumps(stats),  # Convert to JSON string
            'columns': json.dumps(list(df.columns)),  # Convert to JSON string
            'data_quality': json.dumps(data_quality),  # Convert to JSON string
            # Add missing attributes for datasets_metadata collection
            'type': 'testing',  # Default, can be set dynamically if needed
            'created_on': datetime.now().isoformat() + "Z",
            'source': original_filename,
            'size': stats['total_records'],
            'notes': '',
            'target_input': target_input or ''  # Include target_input in metadata
        }

        logger.debug("Generated comprehensive metadata", source="GroundTruthService")
        return metadata

    # === STORAGE OPERATIONS ===

    def _save_locally(self, df: pd.DataFrame, filename_stem: str) -> Path:
        """
        Save DataFrame to local storage.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame to save.
        filename_stem : str
            Base filename without extension.

        Returns
        -------
        Path
            Path to saved file.
        """
        try:
            output_path = self.ground_truth_dir / f"{filename_stem}.csv"
            df.to_csv(output_path, index=False, encoding='utf-8')

            logger.info(f"Saved processed ground truth locally: {output_path}",
                        source="GroundTruthService")
            return output_path

        except Exception as e:
            logger.error("Failed to save ground truth data locally",
                         source="GroundTruthService", error=e)
            raise

    def _store_to_appwrite(self, local_path: Path, processed_df: pd.DataFrame, metadata: Dict[str, Any],
                           dataset_name: str):
        """
        Store processed ground truth data to Appwrite.

        Parameters
        ----------
        local_path : Path
            Path to the saved CSV file.
        processed_df : pd.DataFrame
            Processed ground truth DataFrame.
        metadata : Dict[str, Any]
            Metadata about the dataset.
        dataset_name : str
            Name of the dataset.
        """
        logger.info("Storing ground truth data to Appwrite...", source="GroundTruthService")

        # Upload CSV file to datasets bucket
        csv_upload = self.bucket_manager.upload_file(
            bucket_id="datasets_bucket",
            file_path=str(local_path)
        )

        # Get file URL
        file_url = self.bucket_manager.get_file_url(
            bucket_id="datasets_bucket",
            file_name=local_path.name
        )

        # Update metadata with file information
        metadata.update({
            "file_url": file_url,
            "appwrite_file_id": csv_upload['$id'],
            "local_path": str(local_path),
            "file_size": local_path.stat().st_size
        })

        # Store metadata in database
        self.db_manager.create_document(
            collection_id="datasets_metadata",
            data=metadata
        )

        logger.info("Successfully stored ground truth data to Appwrite", source="GroundTruthService")

    # === RETRIEVAL METHODS ===

    def list_ground_truth_datasets(self) -> List[Dict[str, Any]]:
        """
        List all processed ground truth datasets.

        Returns
        -------
        List[Dict[str, Any]]
            List of dataset metadata.
        """
        try:
            datasets = self.db_manager.list_documents("datasets_metadata")
            logger.info(f"Retrieved {len(datasets)} ground truth datasets",
                        source="GroundTruthService")
            return datasets
        except Exception as e:
            logger.error("Failed to list ground truth datasets",
                         source="GroundTruthService", error=e)
            raise

    def get_ground_truth_dataset(self, dataset_id: str) -> pd.DataFrame:
        """
        Retrieve a specific ground truth dataset as DataFrame.

        Parameters
        ----------
        dataset_id : str
            Dataset identifier.

        Returns
        -------
        pd.DataFrame
            Ground truth dataset.
        """
        try:
            # Get dataset metadata
            metadata = self.db_manager.get_document("datasets_metadata", dataset_id)

            # Check if local file exists
            local_path = Path(metadata['local_path'])
            if local_path.exists():
                df = pd.read_csv(local_path)
                logger.info(f"Retrieved ground truth dataset from local storage: {dataset_id}",
                            source="GroundTruthService")
                return df

            # Download from Appwrite if local file not available
            file_id = metadata['appwrite_file_id']
            temp_path = self.ground_truth_dir / f"temp_{dataset_id}.csv"

            self.bucket_manager.download_file("datasets_bucket", file_id, str(temp_path))
            df = pd.read_csv(temp_path)

            # Clean up temp file
            temp_path.unlink()

            logger.info(f"Retrieved ground truth dataset from cloud storage: {dataset_id}",
                        source="GroundTruthService")
            return df

        except Exception as e:
            logger.error(f"Failed to retrieve ground truth dataset: {dataset_id}",
                         source="GroundTruthService", error=e)
            raise
