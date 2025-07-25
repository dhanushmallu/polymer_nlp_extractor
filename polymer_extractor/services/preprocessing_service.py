# """
# Preprocessing Service for Polymer NLP Extractor.

# Handles full pipeline:
#   - GROBID TEI extraction
#   - TEI XML cleaning and metadata extraction
#   - Tokenizer audit and extension (optional step)
#   - Token packing into overlapping windows

# 
# """

# import os
# from typing import List, Dict, Any, Optional

# from polymer_extractor.services.grobid_service import GrobidService
# from polymer_extractor.services.tei_processing_service import TEIProcessingService
# # from polymer_extractor.services.tokenizer_service import TokenizerService
# from polymer_extractor.services.token_packing_service import TokenPackingService
# from polymer_extractor.utils.logging import Logger

# logger = Logger()


# class PreprocessingService:
#     """
#     Service to orchestrate the full preprocessing pipeline.
#     """

#     def __init__(self, model_names: Optional[List[str]] = None, grobid_url: str = "http://localhost:8070"):
#         """
#         Initialize PreprocessingService.

#         Parameters
#         ----------
#         model_names : list[str], optional
#             List of Hugging Face model IDs to process. Defaults to all ensemble models.
#         grobid_url : str
#             URL of running GROBID server.
#         """
#         self.model_names = model_names
#         self.grobid_service = GrobidService(server_url=grobid_url)
#         self.tokenizer_service = TokenizerService()

#     def run_full_preprocessing(self, file_path: str) -> Dict[str, Any]:
#         """
#         Run full preprocessing pipeline on a single document.

#         Workflow:
#           1. Process document with GROBID to get TEI XML
#           2. Clean TEI XML and extract metadata
#           3. Audit and extend tokenizers
#           4. Pack tokenized text into overlapping windows

#         Parameters
#         ----------
#         file_path : str
#             Path to the PDF/XML/HTML document.

#         Returns
#         -------
#         dict
#             Summary of all processing steps.
#         """
#         logger.info(
#             message=f"Starting full preprocessing pipeline for file: {file_path}",
#             source="PreprocessingService.run_full_preprocessing",
#             category="pipeline",
#             event_type="pipeline_start"
#         )

#         # Step 1️⃣: Process document with GROBID
#         try:
#             grobid_result = self.grobid_service.process_document(file_path)
#             processed_tei_path = grobid_result.get("local_tei_path")
#             logger.info(
#                 message="GROBID processing completed successfully.",
#                 source="PreprocessingService.run_full_preprocessing",
#                 category="pipeline",
#                 event_type="grobid_complete"
#             )
#         except Exception as e:
#             logger.error(
#                 message=f"GROBID processing failed: {e}",
#                 source="PreprocessingService.run_full_preprocessing",
#                 error=e,
#                 category="pipeline",
#                 event_type="grobid_error"
#             )
#             raise

#         # Step 2️⃣: Clean TEI and extract metadata
#         try:
#             tei_service = TEIProcessingService()
#             tei_result = tei_service.process(processed_tei_path)
#             logger.info(
#                 message="TEI cleaning and metadata extraction completed.",
#                 source="PreprocessingService.run_full_preprocessing",
#                 category="pipeline",
#                 event_type="tei_processing_complete"
#             )
#         except Exception as e:
#             logger.error(
#                 message=f"TEI processing failed: {e}",
#                 source="PreprocessingService.run_full_preprocessing",
#                 error=e,
#                 category="pipeline",
#                 event_type="tei_processing_error"
#             )
#             raise

#         # Step 3️⃣: Audit and extend tokenizers
#         try:
#             tokenizer_results = self.tokenizer_service.audit_and_extend_all(force=False)
#             logger.info(
#                 message="Tokenizer audit and extension completed.",
#                 source="PreprocessingService.run_full_preprocessing",
#                 category="pipeline",
#                 event_type="tokenizer_complete"
#             )
#         except Exception as e:
#             logger.error(
#                 message=f"Tokenizer audit failed: {e}",
#                 source="PreprocessingService.run_full_preprocessing",
#                 error=e,
#                 category="pipeline",
#                 event_type="tokenizer_error"
#             )
#             raise

#         # Step 4️⃣: Tokenize and pack sentences for each model
#         packing_results = {}
#         try:
#             models_to_process = self.model_names or [model.model_id for model in self.tokenizer_service.models]

#             for model_name in models_to_process:
#                 logger.info(
#                     message=f"Packing tokens for model: {model_name}",
#                     source="PreprocessingService.run_full_preprocessing",
#                     category="pipeline",
#                     event_type="token_packing_start"
#                 )
#                 packing_service = TokenPackingService(model_name=model_name)
#                 packing_result = packing_service.process_tei_file(processed_tei_path)
#                 packing_results[model_name] = packing_result

#             logger.info(
#                 message="Token packing completed for all models.",
#                 source="PreprocessingService.run_full_preprocessing",
#                 category="pipeline",
#                 event_type="token_packing_complete"
#             )
#         except Exception as e:
#             logger.error(
#                 message=f"Token packing failed: {e}",
#                 source="PreprocessingService.run_full_preprocessing",
#                 error=e,
#                 category="pipeline",
#                 event_type="token_packing_error"
#             )
#             raise

#         summary = {
#             "success": True,
#             "original_file": file_path,
#             "grobid_result": grobid_result,
#             "tei_result": tei_result,
#             "tokenizer_results": tokenizer_results,
#             "packing_results": packing_results
#         }

#         logger.info(
#             message="Full preprocessing pipeline completed successfully.",
#             source="PreprocessingService.run_full_preprocessing",
#             category="pipeline",
#             event_type="pipeline_complete"
#         )
#         return summary
