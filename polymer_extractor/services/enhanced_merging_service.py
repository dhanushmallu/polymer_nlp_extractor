"""
Strict Sentence-by-Sentence Processing Service for Polymer NLP Extractor.

This service implements a precise sentence-based processing pipeline:
1. Extract sentences from TEI with exact character positions
2. Process entities sentence-by-sentence in order
3. Filter entities that don't belong to current sentence
4. Merge adjacent entities (within 2 character spans)
5. Align entities to form complete words/phrases from TEI source
6. Replace partial matches with complete TEI text
7. Remove all contributing entities to prevent duplicates
8. Generate single clean JSON output with sentence-level text (not paragraphs)
"""

import json
import re
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import defaultdict, Counter
from dataclasses import asdict
from difflib import SequenceMatcher
from lxml import etree

from polymer_extractor.utils.logging import Logger
from polymer_extractor.utils.paths import WORKSPACE_DIR
from polymer_extractor.model_config import ENTITY_SEMANTIC_GROUPS, POST_PROCESSING_CONFIG

# Initialize logger
logger = Logger()


class StrictSentenceProcessor:
    """
    Strict sentence-by-sentence entity processing with exact TEI alignment.
    
    Implements the exact flow requested:
    - Take sentence from TEI file
    - Order entities by char_start
    - Filter entities that don't belong to sentence
    - Merge adjacent entities (2 character span tolerance)
    - Align to complete words/phrases from TEI
    - Replace partial entities with complete TEI text
    - Remove all contributing entities
    - Generate clean single JSON output
    """
    
    def __init__(self):
        self.semantic_groups = ENTITY_SEMANTIC_GROUPS
        self.adjacency_tolerance = 2  # Character span tolerance for merging
        self.confidence_thresholds = POST_PROCESSING_CONFIG.get("CONFIDENCE_THRESHOLDS", {})
        
        logger.info("Strict Sentence Processor initialized", 
                   source="StrictSentenceProcessor.__init__",
                   context={"confidence_thresholds": self.confidence_thresholds})
    
    def process_ensemble_results(self, results: Dict[str, List[Dict[str, Any]]], 
                               tei_path: str, base_name: str) -> Dict[str, Any]:
        """
        Main processing pipeline - sentence by sentence processing.
        
        Args:
            results: Raw ensemble results with potential duplicates/fragments
            tei_path: Path to .tei_cleaned.tei.xml source file
            base_name: Base filename for output
            
        Returns:
            Single cleaned results dictionary
        """
        logger.info(f"Starting strict sentence processing for {base_name}",
                   source="StrictSentenceProcessor.process_ensemble_results",
                   context={"total_entities": sum(len(entities) for entities in results.values())})
        
        # Extract sentences from TEI with precise positions
        tei_sentences = self._extract_tei_sentences_with_positions(tei_path)
        logger.info(f"Extracted {len(tei_sentences)} sentences from TEI source",
                   source="StrictSentenceProcessor.process_ensemble_results")
        
        if not tei_sentences:
            logger.error("No sentences extracted from TEI file", 
                        source="StrictSentenceProcessor.process_ensemble_results")
            return {"entities": [], "sentence_count": 0, "processing_errors": ["No TEI sentences"]}
        
        # Flatten all entities for processing
        all_entities = []
        for entity_type, entities in results.items():
            for entity in entities:
                if isinstance(entity, dict) and 'text' in entity:
                    entity['entity_type'] = entity_type
                    all_entities.append(entity)
        
        logger.info(f"Flattened {len(all_entities)} entities for processing",
                   source="StrictSentenceProcessor.process_ensemble_results")
        
        # Process sentence by sentence
        final_entities = []
        used_entity_indices = set()
        processing_stats = {
            "sentences_processed": 0,
            "entities_merged": 0,
            "entities_replaced": 0,
            "entities_discarded": 0,
            "duplicates_consolidated": 0
        }
        
        # Sort entities by char_start for efficient processing
        all_entities.sort(key=lambda e: e.get('char_start', 0))
        
        # Process each sentence in order
        for sentence_idx, sentence_info in enumerate(tei_sentences):
            sentence_entities = self._process_single_sentence(
                sentence_info, all_entities, used_entity_indices, processing_stats
            )
            final_entities.extend(sentence_entities)
            processing_stats["sentences_processed"] += 1
            
            if sentence_idx % 10 == 0:
                logger.debug(f"Processed {sentence_idx + 1}/{len(tei_sentences)} sentences",
                           source="StrictSentenceProcessor.process_ensemble_results")
        
        # Organize final results
        entity_breakdown = defaultdict(int)
        for entity in final_entities:
            entity_breakdown[entity.get('entity_type', 'UNKNOWN')] += 1
        
        result = {
            "entities": final_entities,
            "sentence_count": len(tei_sentences),
            "entity_count": len(final_entities),
            "entity_breakdown": dict(entity_breakdown),
            "processing_stats": processing_stats,
            "tei_source": tei_path
        }
        
        logger.info(f"Strict processing completed: {len(final_entities)} final entities",
                   source="StrictSentenceProcessor.process_ensemble_results",
                   context=processing_stats)
        
        return result
    
    def _extract_tei_sentences_with_positions(self, tei_path: str) -> List[Dict[str, Any]]:
        """
        Extract sentences from TEI with precise character positions.
        """
        try:
            tree = etree.parse(tei_path)
            
            # Get full text content preserving structure
            full_text = ""
            text_elements = tree.xpath("//text()")
            full_text = " ".join(text_elements)
            full_text = re.sub(r'\s+', ' ', full_text).strip()
            
            # Split into sentences using scientific-aware patterns
            sentences = self._split_into_sentences(full_text)
            
            # Create sentence objects with positions
            tei_sentences = []
            current_pos = 0
            
            for sentence_id, sentence_text in enumerate(sentences):
                if len(sentence_text.strip()) < 10:  # Skip very short sentences
                    continue
                    
                # Find exact position in full text
                start_pos = full_text.find(sentence_text.strip(), current_pos)
                if start_pos == -1:
                    # Try fuzzy matching
                    start_pos = self._fuzzy_find_position(sentence_text.strip(), full_text, current_pos)
                
                if start_pos != -1:
                    end_pos = start_pos + len(sentence_text.strip())
                    
                    tei_sentences.append({
                        "sentence_id": sentence_id,
                        "text": sentence_text.strip(),
                        "char_start": start_pos,
                        "char_end": end_pos
                    })
                    
                    current_pos = end_pos
                else:
                    logger.warning(f"Could not find position for sentence: {sentence_text[:50]}...",
                                 source="StrictSentenceProcessor._extract_tei_sentences_with_positions")
            
            return tei_sentences
            
        except Exception as e:
            logger.error(f"Failed to extract TEI sentences: {e}",
                        source="StrictSentenceProcessor._extract_tei_sentences_with_positions",
                        error=e)
            return []
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences preserving scientific notation."""
        
        # Protect scientific patterns
        protected_patterns = [
            r'\b(?:Fig|Table|Eq|Ref|vs|etc|i\.e|e\.g|cf|et al)\.',
            r'\b[A-Z][a-z]*\.',  # Proper nouns
            r'\d+\.\d+',  # Decimal numbers
            r'\b[A-Z]{2,}\.',  # Acronyms
        ]
        
        # Replace protected patterns temporarily
        protected_text = text
        replacements = {}
        counter = 0
        
        for pattern in protected_patterns:
            matches = list(re.finditer(pattern, protected_text))
            for match in reversed(matches):  # Reverse to maintain positions
                placeholder = f"__PROTECT_{counter}__"
                replacements[placeholder] = match.group()
                protected_text = protected_text[:match.start()] + placeholder + protected_text[match.end():]
                counter += 1
        
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', protected_text)
        
        # Restore protected patterns
        restored_sentences = []
        for sentence in sentences:
            restored = sentence
            for placeholder, original in replacements.items():
                restored = restored.replace(placeholder, original)
            if restored.strip() and len(restored.strip()) > 5:
                restored_sentences.append(restored.strip())
        
        return restored_sentences
        
        # Replace protected patterns temporarily
        protected_text = text
        replacements = {}
        counter = 0
        
        for pattern in protected_patterns:
            matches = list(re.finditer(pattern, protected_text))
            for match in reversed(matches):  # Reverse to maintain positions
                placeholder = f"__PROTECT_{counter}__"
                replacements[placeholder] = match.group()
                protected_text = protected_text[:match.start()] + placeholder + protected_text[match.end():]
                counter += 1
        
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', protected_text)
        
        # Restore protected patterns
        restored_sentences = []
        for sentence in sentences:
            restored = sentence
            for placeholder, original in replacements.items():
                restored = restored.replace(placeholder, original)
            if restored.strip() and len(restored.strip()) > 5:
                restored_sentences.append(restored.strip())
        
        return restored_sentences
    
    def _fuzzy_find_position(self, sentence: str, full_text: str, start_pos: int) -> int:
        """Find sentence position using fuzzy matching."""
        search_window = full_text[start_pos:start_pos + len(sentence) * 2]
        
        # Try first 50 characters
        sentence_start = sentence[:50] if len(sentence) > 50 else sentence
        pos = search_window.find(sentence_start)
        
        if pos != -1:
            return start_pos + pos
        
        return -1
    
    def _process_single_sentence(self, sentence_info: Dict[str, Any], 
                               all_entities: List[Dict[str, Any]], 
                               used_entity_indices: Set[int],
                               processing_stats: Dict[str, int]) -> List[Dict[str, Any]]:
        """
        Process entities for a single sentence following the strict flow.
        """
        sentence_start = sentence_info['char_start']
        sentence_end = sentence_info['char_end']
        sentence_text = sentence_info['text']
        
        # Step 1: Find entities that belong to this sentence and meet confidence requirements
        sentence_entities = []
        for idx, entity in enumerate(all_entities):
            if idx in used_entity_indices:
                continue
                
            entity_start = entity.get('char_start', 0)
            entity_end = entity.get('char_end', 0)
            entity_type = entity.get('entity_type', 'UNKNOWN')
            confidence = entity.get('confidence', 0.0)
            
            # Apply strict confidence filtering
            min_confidence = self.confidence_thresholds.get(entity_type, self.confidence_thresholds.get('GLOBAL', 0.82))
            if confidence < min_confidence:
                processing_stats["entities_discarded"] += 1
                continue
            
            # Check if entity overlaps with sentence boundaries
            if self._entity_belongs_to_sentence(entity_start, entity_end, sentence_start, sentence_end):
                sentence_entities.append((idx, entity))
        
        if not sentence_entities:
            return []
        
        # Order entities by char_start
        sentence_entities.sort(key=lambda x: x[1].get('char_start', 0))
        
        logger.debug(f"Processing sentence {sentence_info['sentence_id']}: {len(sentence_entities)} entities",
                   source="StrictSentenceProcessor._process_single_sentence")
        
        # Step 2: Find adjacent entities (within 2 character spans)
        entity_groups = self._group_adjacent_entities(sentence_entities)
        
        # Step 3: Process each group and consolidate duplicates
        final_sentence_entities = []
        for group in entity_groups:
            processed_entity = self._process_entity_group(group, sentence_info, processing_stats)
            if processed_entity:
                final_sentence_entities.append(processed_entity)
                
                # Mark all entities in group as used
                for idx, _ in group:
                    used_entity_indices.add(idx)
        
        # Step 4: Consolidate duplicate entities within the sentence
        # This handles cases like "six epo, six pox, 13 oxy" → "epoxy"
        consolidated_entities = self._consolidate_duplicate_entities(
            final_sentence_entities, sentence_info, processing_stats
        )
        
        return consolidated_entities
    
    def _entity_belongs_to_sentence(self, entity_start: int, entity_end: int, 
                                  sentence_start: int, sentence_end: int) -> bool:
        """Check if entity belongs to sentence with exact boundaries."""
        # Entity must be completely within sentence boundaries
        return sentence_start <= entity_start and entity_end <= sentence_end
    
    def _group_adjacent_entities(self, sentence_entities: List[Tuple[int, Dict[str, Any]]]) -> List[List[Tuple[int, Dict[str, Any]]]]:
        """Group entities that are adjacent (within 2 character spans)."""
        if not sentence_entities:
            return []
        
        groups = []
        current_group = [sentence_entities[0]]
        
        for i in range(1, len(sentence_entities)):
            prev_entity = current_group[-1][1]
            curr_entity = sentence_entities[i][1]
            
            prev_end = prev_entity.get('char_end', 0)
            curr_start = curr_entity.get('char_start', 0)
            
            # Check if entities are adjacent (within tolerance)
            if curr_start - prev_end <= self.adjacency_tolerance:
                current_group.append(sentence_entities[i])
            else:
                groups.append(current_group)
                current_group = [sentence_entities[i]]
        
        groups.append(current_group)
        return groups
    
    def _process_entity_group(self, group: List[Tuple[int, Dict[str, Any]]], 
                            sentence_info: Dict[str, Any],
                            processing_stats: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """
        Process a group of adjacent entities - implement complete word/phrase alignment.
        """
        if not group:
            return None
        
        # If single entity, process individually
        if len(group) == 1:
            return self._process_single_entity(group[0][1], sentence_info, processing_stats)
        
        # Multiple entities - merge them and align to complete words/phrases
        processing_stats["entities_merged"] += len(group) - 1
        
        # Get span of entire group
        entities = [entity for _, entity in group]
        group_start = min(e.get('char_start', 0) for e in entities)
        group_end = max(e.get('char_end', 0) for e in entities)
        
        # Extract text from TEI sentence and align to complete words
        sentence_start = sentence_info['char_start']
        relative_start = group_start - sentence_start
        relative_end = group_end - sentence_start
        
        sentence_text = sentence_info['text']
        if relative_start < 0 or relative_end > len(sentence_text):
            logger.warning(f"Entity group spans outside sentence boundaries",
                         source="StrictSentenceProcessor._process_entity_group")
            return None
        
        # Get the complete phrase from TEI and expand to word boundaries
        complete_text = self._extract_and_align_complete_phrase(
            sentence_text, relative_start, relative_end
        )
        
        # Check if this is a valid entity after alignment
        if not complete_text or len(complete_text.strip()) < 2:
            processing_stats["entities_discarded"] += len(group)
            return None
        
        # Check for ridiculous fragments (like "pox", "able", "oil")
        if self._is_fragment_or_nonsense(complete_text, sentence_text):
            processing_stats["entities_discarded"] += len(group)
            return None
        
        # Select best entity type and confidence from group
        best_entity = max(entities, key=lambda e: e.get('confidence', 0))
        
        # Create merged entity
        merged_entity = {
            'text': complete_text,
            'char_start': group_start,
            'char_end': group_start + len(complete_text),
            'entity_type': best_entity.get('entity_type'),
            'confidence': best_entity.get('confidence', 0),
            'sentence_id': sentence_info['sentence_id'],
            'sentence_text': sentence_info['text'],  # Actual sentence, not paragraph
            'model': best_entity.get('model', 'ensemble'),
            'merged_from': len(entities),
            'consolidation_reason': f"merged_{len(entities)}_adjacent_entities"
        }
        
        return merged_entity
    
    def _process_single_entity(self, entity: Dict[str, Any], 
                             sentence_info: Dict[str, Any],
                             processing_stats: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """
        Process a single entity with TEI alignment and complete word extraction.
        """
        entity_start = entity.get('char_start', 0)
        entity_end = entity.get('char_end', 0)
        entity_text = entity.get('text', '').strip()
        
        # Get position relative to sentence
        sentence_start = sentence_info['char_start']
        relative_start = entity_start - sentence_start
        relative_end = entity_end - sentence_start
        
        sentence_text = sentence_info['text']
        if relative_start < 0 or relative_end > len(sentence_text):
            logger.warning(f"Entity spans outside sentence: {entity_text}",
                         source="StrictSentenceProcessor._process_single_entity")
            return None
        
        # Extract and align to complete words/phrases from TEI
        complete_text = self._extract_and_align_complete_phrase(
            sentence_text, relative_start, relative_end
        )
        
        # Validate the extracted text
        if not complete_text or len(complete_text.strip()) < 2:
            processing_stats["entities_discarded"] += 1
            return None
        
        # Check for fragments or nonsense
        if self._is_fragment_or_nonsense(complete_text, sentence_text):
            processing_stats["entities_discarded"] += 1
            return None
        
        # Replace entity text with complete TEI text if different
        if complete_text != entity_text:
            processing_stats["entities_replaced"] += 1
        
        # Create final entity
        final_entity = {
            'text': complete_text,
            'char_start': entity_start,
            'char_end': entity_start + len(complete_text),
            'entity_type': entity.get('entity_type'),
            'confidence': entity.get('confidence', 0),
            'sentence_id': sentence_info['sentence_id'],
            'sentence_text': sentence_info['text'],  # Actual sentence, not paragraph
            'model': entity.get('model', 'unknown'),
            'consolidation_reason': "single_entity_aligned"
        }
        
        return final_entity
    
    def _extract_and_align_complete_phrase(self, sentence: str, start: int, end: int) -> str:
        """
        Extract text and align to complete words/phrases from TEI sentence.
        This is the core logic for replacing partial entities with complete TEI text.
        """
        if not sentence or start < 0 or end > len(sentence):
            return ""
        
        # Get initial text
        initial_text = sentence[start:end].strip()
        
        # Expand to word boundaries
        expanded_start = start
        expanded_end = end
        
        # Expand backward to word boundary
        while expanded_start > 0 and sentence[expanded_start - 1].isalnum():
            expanded_start -= 1
        
        # Expand forward to word boundary  
        while expanded_end < len(sentence) and sentence[expanded_end].isalnum():
            expanded_end += 1
        
        # Handle special cases like parentheses, hyphens
        if expanded_start > 0 and sentence[expanded_start - 1] in '([{':
            # Find matching closing bracket
            bracket_map = {'(': ')', '[': ']', '{': '}'}
            open_bracket = sentence[expanded_start - 1]
            if open_bracket in bracket_map:
                close_bracket = bracket_map[open_bracket]
                bracket_end = sentence.find(close_bracket, expanded_end)
                if bracket_end != -1:
                    expanded_start -= 1
                    expanded_end = bracket_end + 1
        
        # Handle hyphenated compounds
        if expanded_start > 0 and sentence[expanded_start - 1] == '-':
            # Check if this is part of a compound word
            hyphen_start = expanded_start - 1
            while hyphen_start > 0 and (sentence[hyphen_start - 1].isalnum() or sentence[hyphen_start - 1] == '-'):
                hyphen_start -= 1
            expanded_start = hyphen_start
        
        if expanded_end < len(sentence) and sentence[expanded_end] == '-':
            # Extend to include rest of compound
            while expanded_end < len(sentence) and (sentence[expanded_end].isalnum() or sentence[expanded_end] == '-'):
                expanded_end += 1
        
        # Get the complete text
        complete_text = sentence[expanded_start:expanded_end].strip()
        
        # Don't expand too much (prevent capturing entire sentence)
        if len(complete_text) > len(initial_text) * 4:
            return initial_text
        
        return complete_text if complete_text else initial_text
    
    def _is_fragment_or_nonsense(self, text: str, sentence_context: str) -> bool:
        """
        Check if extracted text is a meaningless fragment that should be discarded.
        This prevents ridiculous outputs like "pox", "able", "oil".
        """
        if not text or len(text) < 2:
            return True
        
        text_lower = text.lower().strip()
        
        # Common meaningless fragments to discard
        nonsense_fragments = {
            'pox', 'poxidized', 'able', 'oil', 'oxy', 'epo', 'mer', 'pol', 
            'ing', 'tion', 'ed', 'er', 'ly', 'al', 'ic', 'ous', 'ive',
            'the', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'by'
        }
        
        if text_lower in nonsense_fragments:
            return True
        
        # Check if it's just a suffix or prefix
        if len(text) <= 3 and not text.isupper():  # Allow symbols like "DSC", "TGA"
            return True
        
        # Check for excessive punctuation
        punct_count = sum(1 for c in text if not c.isalnum() and c not in ' ()-[]{}.,;:')
        if len(text) > 0 and punct_count / len(text) > 0.4:
            return True
        
        # Check if it's a fragment of a larger word in the sentence
        words_in_sentence = sentence_context.lower().split()
        for word in words_in_sentence:
            if len(word) > len(text) * 2 and text_lower in word and text_lower != word:
                # This is likely a fragment of a larger word
                return True
        
        return False
    
    def _group_adjacent_entities(self, sentence_entities: List[Tuple[int, Dict[str, Any]]]) -> List[List[Tuple[int, Dict[str, Any]]]]:
        """Group entities that are adjacent (within 2 character spans)."""
        if not sentence_entities:
            return []
        
        groups = []
        current_group = [sentence_entities[0]]
        
        for i in range(1, len(sentence_entities)):
            prev_entity = current_group[-1][1]
            curr_entity = sentence_entities[i][1]
            
            prev_end = prev_entity.get('char_end', 0)
            curr_start = curr_entity.get('char_start', 0)
            
            # Check if entities are adjacent (within tolerance)
            if curr_start - prev_end <= self.adjacency_tolerance:
                current_group.append(sentence_entities[i])
            else:
                groups.append(current_group)
                current_group = [sentence_entities[i]]
        
        groups.append(current_group)
        return groups
    
    def _process_entity_group(self, group: List[Tuple[int, Dict[str, Any]]], 
                            sentence_info: Dict[str, Any],
                            processing_stats: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """
        Process a group of adjacent entities.
        """
        if not group:
            return None
        
        # If single entity, process individually
        if len(group) == 1:
            return self._process_single_entity(group[0][1], sentence_info, processing_stats)
        
        # Multiple entities - merge them
        processing_stats["entities_merged"] += len(group) - 1
        
        # Get span of entire group
        entities = [entity for _, entity in group]
        group_start = min(e.get('char_start', 0) for e in entities)
        group_end = max(e.get('char_end', 0) for e in entities)
        
        # Extract text from TEI sentence
        sentence_start = sentence_info['char_start']
        relative_start = group_start - sentence_start
        relative_end = group_end - sentence_start
        
        sentence_text = sentence_info['text']
        if relative_start < 0 or relative_end > len(sentence_text):
            logger.warning(f"Entity group spans outside sentence boundaries",
                         source="StrictSentenceProcessor._process_entity_group")
            return None
        
        # Get the complete phrase from TEI
        tei_text = sentence_text[relative_start:relative_end].strip()
        
        # Expand to complete words if needed
        complete_text = self._expand_to_complete_words(tei_text, sentence_text, relative_start, relative_end)
        
        # Check if we need replacement
        if complete_text != tei_text:
            processing_stats["entities_replaced"] += 1
        
        # Select best entity type and confidence from group
        best_entity = max(entities, key=lambda e: e.get('confidence', 0))
        
        # Create merged entity
        merged_entity = {
            'text': complete_text,
            'char_start': group_start,
            'char_end': group_start + len(complete_text),
            'entity_type': best_entity.get('entity_type'),
            'confidence': best_entity.get('confidence', 0),
            'sentence_id': sentence_info['sentence_id'],
            'sentence_text': sentence_info['text'],  # Actual sentence, not paragraph
            'model': best_entity.get('model', 'ensemble'),
            'merged_from': len(entities),
            'consolidation_reason': f"merged_{len(entities)}_adjacent_entities"
        }
        
        return merged_entity
    
    def _process_single_entity(self, entity: Dict[str, Any], 
                             sentence_info: Dict[str, Any],
                             processing_stats: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """
        Process a single entity with TEI alignment.
        """
        entity_start = entity.get('char_start', 0)
        entity_end = entity.get('char_end', 0)
        entity_text = entity.get('text', '').strip()
        
        # Get position relative to sentence
        sentence_start = sentence_info['char_start']
        relative_start = entity_start - sentence_start
        relative_end = entity_end - sentence_start
        
        sentence_text = sentence_info['text']
        if relative_start < 0 or relative_end > len(sentence_text):
            logger.warning(f"Entity spans outside sentence: {entity_text}",
                         source="StrictSentenceProcessor._process_single_entity")
            return None
        
        # Get text from TEI
        tei_text = sentence_text[relative_start:relative_end].strip()
        
        # Expand to complete words
        complete_text = self._expand_to_complete_words(tei_text, sentence_text, relative_start, relative_end)
        
        # Check if we replaced
        if complete_text != entity_text:
            processing_stats["entities_replaced"] += 1
        
        # Create final entity
        final_entity = {
            'text': complete_text,
            'char_start': entity_start,
            'char_end': entity_start + len(complete_text),
            'entity_type': entity.get('entity_type'),
            'confidence': entity.get('confidence', 0),
            'sentence_id': sentence_info['sentence_id'],
            'sentence_text': sentence_info['text'],  # Actual sentence, not paragraph
            'model': entity.get('model', 'unknown'),
            'consolidation_reason': "single_entity"
        }
        
        return final_entity
    
    def _expand_to_complete_words(self, text: str, sentence: str, start: int, end: int) -> str:
        """
        Expand text to complete words using sentence boundaries.
        """
        if not text or not sentence:
            return text
        
        expanded_start = start
        expanded_end = end
        
        # Expand backward to word boundary
        while expanded_start > 0 and sentence[expanded_start - 1].isalnum():
            expanded_start -= 1
        
        # Expand forward to word boundary
        while expanded_end < len(sentence) and sentence[expanded_end].isalnum():
            expanded_end += 1
        
        # Get expanded text
        expanded_text = sentence[expanded_start:expanded_end].strip()
        
        # Don't expand too much (more than 3x original length)
        if len(expanded_text) > len(text) * 3:
            return text
        
        return expanded_text if expanded_text else text
    
    def _consolidate_duplicate_entities(self, entities: List[Dict[str, Any]], 
                                      sentence_info: Dict[str, Any],
                                      processing_stats: Dict[str, int]) -> List[Dict[str, Any]]:
        """
        Consolidate duplicate/similar entities within a sentence.
        Handles cases like multiple fragments of the same word: "epo", "pox", "oxy" → "epoxy"
        """
        if not entities:
            return []
        
        # Group entities by similarity and position
        consolidated = []
        used_indices = set()
        
        for i, entity in enumerate(entities):
            if i in used_indices:
                continue
            
            entity_text = entity.get('text', '').lower().strip()
            entity_pos = entity.get('char_start', 0)
            entity_type = entity.get('entity_type', '')
            
            # Find all similar entities
            similar_entities = [entity]
            similar_indices = [i]
            
            for j, other_entity in enumerate(entities[i+1:], i+1):
                if j in used_indices:
                    continue
                
                other_text = other_entity.get('text', '').lower().strip()
                other_pos = other_entity.get('char_start', 0)
                other_type = other_entity.get('entity_type', '')
                
                # Check if entities are similar and should be consolidated
                if (entity_type == other_type and 
                    self._should_consolidate_entities(entity_text, other_text, entity_pos, other_pos, sentence_info['text'])):
                    similar_entities.append(other_entity)
                    similar_indices.append(j)
            
            # If we found multiple similar entities, consolidate them
            if len(similar_entities) > 1:
                consolidated_entity = self._create_consolidated_entity(
                    similar_entities, sentence_info, processing_stats
                )
                if consolidated_entity:
                    consolidated.append(consolidated_entity)
                    processing_stats["duplicates_consolidated"] += len(similar_entities) - 1
            else:
                # Single entity, keep as is
                consolidated.append(entity)
            
            # Mark indices as used
            for idx in similar_indices:
                used_indices.add(idx)
        
        return consolidated
    
    def _should_consolidate_entities(self, text1: str, text2: str, pos1: int, pos2: int, sentence: str) -> bool:
        """
        Determine if two entities should be consolidated.
        """
        # Don't consolidate if texts are too different
        if not text1 or not text2:
            return False
        
        # Check if they're fragments of the same word
        longer_text = text1 if len(text1) > len(text2) else text2
        shorter_text = text2 if len(text1) > len(text2) else text1
        
        # If one is contained in the other
        if shorter_text in longer_text:
            return True
        
        # Check if they're close in position (within 50 characters)
        if abs(pos1 - pos2) > 50:
            return False
        
        # Check for common scientific terms that might be fragmented
        combined = text1 + text2
        scientific_terms = [
            'epoxy', 'polymer', 'temperature', 'property', 'density',
            'modulus', 'strength', 'crystalline', 'amorphous', 'thermoplastic'
        ]
        
        for term in scientific_terms:
            if all(frag in term for frag in [text1, text2]):
                return True
        
        return False
    
    def _create_consolidated_entity(self, entities: List[Dict[str, Any]], 
                                  sentence_info: Dict[str, Any],
                                  processing_stats: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """
        Create a single consolidated entity from multiple similar entities.
        """
        if not entities:
            return None
        
        # Find the span that covers all entities
        min_start = min(e.get('char_start', 0) for e in entities)
        max_end = max(e.get('char_end', 0) for e in entities)
        
        # Extract the complete text from the sentence
        sentence_start = sentence_info['char_start']
        relative_start = min_start - sentence_start
        relative_end = max_end - sentence_start
        
        sentence_text = sentence_info['text']
        if relative_start < 0 or relative_end > len(sentence_text):
            return None
        
        # Get complete phrase and expand to word boundaries
        complete_text = self._extract_and_align_complete_phrase(
            sentence_text, relative_start, relative_end
        )
        
        # Validate the consolidated text
        if not complete_text or len(complete_text.strip()) < 2:
            return None
        
        if self._is_fragment_or_nonsense(complete_text, sentence_text):
            return None
        
        # Use the entity with highest confidence
        best_entity = max(entities, key=lambda e: e.get('confidence', 0))
        
        # Create consolidated entity
        consolidated = {
            'text': complete_text,
            'char_start': min_start,
            'char_end': min_start + len(complete_text),
            'entity_type': best_entity.get('entity_type'),
            'confidence': best_entity.get('confidence', 0),
            'sentence_id': sentence_info['sentence_id'],
            'sentence_text': sentence_info['text'],
            'model': 'consolidated',
            'consolidated_from': len(entities),
            'consolidation_reason': f"consolidated_{len(entities)}_duplicate_fragments"
        }
        
        return consolidated


# Legacy class name for compatibility
class EnhancedMergingService(StrictSentenceProcessor):
    """Legacy wrapper for the strict sentence processor."""
    pass
    
    def _extract_tei_sentences_with_positions(self, tei_path: str) -> List[Dict[str, Any]]:
        """
        Extract sentences from TEI with precise character positions.
        
        Returns list of sentences with:
        - sentence_id: Sequential ID
        - text: Full sentence text
        - char_start: Character start position in full document
        - char_end: Character end position in full document
        - paragraph_id: Source paragraph ID
        """
        try:
            tree = etree.parse(tei_path)
            
            # Extract paragraphs preserving structure
            paragraphs = []
            for p_elem in tree.xpath("//ns0:p", namespaces={"ns0": "http://www.tei-c.org/ns/1.0"}):
                p_text = " ".join(p_elem.xpath(".//text()")).strip()
                if p_text and len(p_text) > 10:
                    paragraphs.append(p_text)
            
            # Fallback to all text if no paragraphs found
            if not paragraphs:
                all_text = " ".join(tree.xpath("//text()"))
                all_text = re.sub(r'\s+', ' ', all_text).strip()
                paragraphs = [all_text]
            
            # Create full document text
            full_text = " ".join(paragraphs)
            full_text = re.sub(r'\s+', ' ', full_text).strip()
            
            # Split into sentences with enhanced patterns
            sentences = self._split_into_sentences(full_text)
            
            # Compute character positions
            tei_sentences = []
            current_pos = 0
            
            for sentence_id, sentence_text in enumerate(sentences):
                # Find sentence in full text starting from current position
                start_pos = full_text.find(sentence_text, current_pos)
                if start_pos == -1:
                    # Try fuzzy matching for slight variations
                    start_pos = self._fuzzy_find_sentence_position(sentence_text, full_text, current_pos)
                
                if start_pos != -1:
                    end_pos = start_pos + len(sentence_text)
                    
                    # Find which paragraph this sentence belongs to
                    paragraph_id = self._find_paragraph_id(start_pos, paragraphs, full_text)
                    
                    tei_sentences.append({
                        "sentence_id": sentence_id,
                        "text": sentence_text.strip(),
                        "char_start": start_pos,
                        "char_end": end_pos,
                        "paragraph_id": paragraph_id
                    })
                    
                    current_pos = end_pos
                else:
                    logger.warning(f"Could not find position for sentence: {sentence_text[:50]}...",
                                 source="EnhancedMergingService._extract_tei_sentences_with_positions")
            
            return tei_sentences
            
        except Exception as e:
            logger.error(f"Failed to extract TEI sentences: {e}",
                        source="EnhancedMergingService._extract_tei_sentences_with_positions",
                        error=e)
            return []
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Enhanced sentence splitting preserving scientific notation and abbreviations."""
        
        # Protect scientific abbreviations and notations
        protected_patterns = [
            r'\b(?:Fig|Table|Eq|Ref|vs|etc|i\.e|e\.g|cf|et al)\.',
            r'\b[A-Z][a-z]*\.',  # Proper nouns with periods
            r'\d+\.\d+',  # Decimal numbers
            r'\b[A-Z]{2,}\.',  # Acronyms
        ]
        
        # Temporarily replace protected patterns
        protected_text = text
        placeholders = {}
        placeholder_counter = 0
        
        for pattern in protected_patterns:
            matches = re.finditer(pattern, protected_text)
            for match in matches:
                placeholder = f"__PROTECTED_{placeholder_counter}__"
                placeholders[placeholder] = match.group()
                protected_text = protected_text.replace(match.group(), placeholder, 1)
                placeholder_counter += 1
        
        # Split on sentence boundaries
        sentence_patterns = [
            r'\.(?=\s+[A-Z])',  # Period followed by space and capital
            r'\.(?=\s+\d)',     # Period followed by space and digit
            r'\!(?=\s+[A-Z])',  # Exclamation
            r'\?(?=\s+[A-Z])',  # Question mark
        ]
        
        sentences = [protected_text]
        for pattern in sentence_patterns:
            new_sentences = []
            for sentence in sentences:
                parts = re.split(f'({pattern})', sentence)
                current = ""
                for i, part in enumerate(parts):
                    if re.match(pattern, part):
                        current += part
                        new_sentences.append(current.strip())
                        current = ""
                    else:
                        current += part
                if current.strip():
                    new_sentences.append(current.strip())
            sentences = [s for s in new_sentences if s.strip()]
        
        # Restore protected patterns
        restored_sentences = []
        for sentence in sentences:
            restored = sentence
            for placeholder, original in placeholders.items():
                restored = restored.replace(placeholder, original)
            if restored.strip() and len(restored.strip()) > 5:
                restored_sentences.append(restored.strip())
        
        return restored_sentences
    
    def _fuzzy_find_sentence_position(self, sentence: str, full_text: str, start_pos: int) -> int:
        """Find sentence position using fuzzy matching for slight variations."""
        
        # Try progressively more flexible matching
        search_window = full_text[start_pos:start_pos + len(sentence) * 3]
        
        # Direct search with normalized whitespace
        normalized_sentence = re.sub(r'\s+', ' ', sentence).strip()
        normalized_search = re.sub(r'\s+', ' ', search_window).strip()
        
        pos = normalized_search.find(normalized_sentence)
        if pos != -1:
            return start_pos + pos
        
        # Try with first 20 words
        sentence_words = normalized_sentence.split()[:20]
        if len(sentence_words) >= 5:
            partial_sentence = ' '.join(sentence_words)
            pos = normalized_search.find(partial_sentence)
            if pos != -1:
                return start_pos + pos
        
        return -1
    
    def _find_paragraph_id(self, char_pos: int, paragraphs: List[str], full_text: str) -> int:
        """Find which paragraph contains the given character position."""
        
        current_pos = 0
        for para_id, paragraph in enumerate(paragraphs):
            paragraph_end = current_pos + len(paragraph)
            if current_pos <= char_pos <= paragraph_end:
                return para_id
            current_pos = paragraph_end + 1  # Account for space between paragraphs
        
        return 0  # Default to first paragraph
    
    def _remove_duplicate_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove obvious duplicate entities based on text and position."""
        
        seen_entities = set()
        unique_entities = []
        
        for entity in entities:
            # Create signature based on text, entity_type, and approximate position
            text = entity.get('text', '').strip().lower()
            entity_type = entity.get('entity_type', '')
            char_start = entity.get('char_start', 0)
            
            # Round position to nearest 10 to catch near-duplicates
            position_group = (char_start // 10) * 10
            
            signature = (text, entity_type, position_group)
            
            if signature not in seen_entities:
                seen_entities.add(signature)
                unique_entities.append(entity)
            else:
                logger.debug(f"Removed duplicate: {text[:30]}... at position {char_start}",
                           source="EnhancedMergingService._remove_duplicate_entities")
        
        return unique_entities
    
    def _enhanced_merging_pipeline(self, entities: List[Dict[str, Any]], 
                                 tei_sentences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute the enhanced merging pipeline sentence by sentence.
        
        Pipeline steps:
        a. Traverse sentence by sentence linearly
        b. Break down words in each sentence
        c. Merge results relevant to that sentence via char_start/char_end
        d. Merge entities that need merging
        e. Remove entities used for merging
        f. Average meta information
        g. Fill sentence_text with correct TEI sentence
        """
        
        processed_entities = []
        used_entity_indices = set()
        
        logger.info(f"Starting pipeline for {len(tei_sentences)} sentences",
                   source="EnhancedMergingService._enhanced_merging_pipeline")
        
        # Process each sentence linearly
        for sentence_info in tei_sentences:
            sentence_id = sentence_info['sentence_id']
            sentence_text = sentence_info['text']
            sentence_start = sentence_info['char_start']
            sentence_end = sentence_info['char_end']
            
            # Find all entities relevant to this sentence
            sentence_entities = []
            for idx, entity in enumerate(entities):
                if idx in used_entity_indices:
                    continue
                
                entity_start = entity.get('char_start', 0)
                entity_end = entity.get('char_end', 0)
                
                # Check if entity overlaps with sentence boundaries
                if self._entities_overlap(entity_start, entity_end, sentence_start, sentence_end):
                    sentence_entities.append((idx, entity))
            
            if not sentence_entities:
                continue
            
            logger.debug(f"Processing sentence {sentence_id}: {len(sentence_entities)} entities",
                        source="EnhancedMergingService._enhanced_merging_pipeline")
            
            # Break down sentence into words for analysis
            sentence_words = self._break_down_sentence(sentence_text)
            
            # Process entities for this sentence
            merged_entities = self._process_sentence_entities(
                sentence_entities, sentence_info, sentence_words
            )
            
            # Mark entities as used
            for idx, _ in sentence_entities:
                used_entity_indices.add(idx)
            
            # Add merged entities to results
            processed_entities.extend(merged_entities)
        
        logger.info(f"Pipeline completed: {len(processed_entities)} final entities",
                   source="EnhancedMergingService._enhanced_merging_pipeline")
        
        return processed_entities
    
    def _entities_overlap(self, entity_start: int, entity_end: int, 
                         sentence_start: int, sentence_end: int) -> bool:
        """Check if entity and sentence character ranges overlap."""
        
        # Allow some tolerance for boundary issues
        tolerance = 5
        
        # Entity completely within sentence
        if sentence_start <= entity_start <= sentence_end and sentence_start <= entity_end <= sentence_end:
            return True
        
        # Entity starts before sentence but ends within
        if entity_start < sentence_start and sentence_start <= entity_end <= sentence_end + tolerance:
            return True
        
        # Entity starts within sentence but ends after
        if sentence_start - tolerance <= entity_start <= sentence_end and entity_end > sentence_end:
            return True
        
        # Entity completely encompasses sentence
        if entity_start <= sentence_start and entity_end >= sentence_end:
            return True
        
        return False
    
    def _break_down_sentence(self, sentence_text: str) -> List[Dict[str, Any]]:
        """Break sentence into words with positions, respecting punctuation rules."""
        
        words = []
        current_pos = 0
        
        # Split by whitespace but preserve positions
        parts = re.split(r'(\s+)', sentence_text)
        
        for part in parts:
            if part.strip():  # Non-whitespace part
                # Further split by punctuation (except brackets)
                subparts = self._split_respecting_brackets(part)
                
                for subpart in subparts:
                    if subpart.strip():
                        words.append({
                            'text': subpart,
                            'start_pos': current_pos,
                            'end_pos': current_pos + len(subpart)
                        })
            
            current_pos += len(part)
        
        return words
    
    def _split_respecting_brackets(self, text: str) -> List[str]:
        """Split text by punctuation while preserving bracket contents."""
        
        # Find bracket pairs
        bracket_ranges = []
        stack = []
        
        for i, char in enumerate(text):
            if char in '([{':
                stack.append((char, i))
            elif char in ')]}':
                if stack:
                    start_char, start_pos = stack.pop()
                    # Check if brackets match
                    pairs = {'(': ')', '[': ']', '{': '}'}
                    if pairs.get(start_char) == char:
                        bracket_ranges.append((start_pos, i + 1))
        
        # Split by punctuation, avoiding bracket interiors
        parts = []
        current_part = ""
        
        for i, char in enumerate(text):
            # Check if we're inside brackets
            inside_brackets = any(start <= i < end for start, end in bracket_ranges)
            
            if not inside_brackets and char in self.sentence_breakers:
                if current_part.strip():
                    parts.append(current_part.strip())
                    current_part = ""
                if char not in ' \t\n':  # Keep punctuation as separate token
                    parts.append(char)
            else:
                current_part += char
        
        if current_part.strip():
            parts.append(current_part.strip())
        
        return [p for p in parts if p.strip()]
    
    def _process_sentence_entities(self, sentence_entities: List[Tuple[int, Dict[str, Any]]], 
                                 sentence_info: Dict[str, Any], 
                                 sentence_words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process entities for a single sentence:
        1. Restore complete words/phrases
        2. Merge overlapping entities
        3. Average metadata
        4. Set correct sentence_text
        """
        
        entities_list = [entity for _, entity in sentence_entities]
        
        # Step 1: Restore complete words/phrases
        restored_entities = self._restore_complete_entities(entities_list, sentence_info, sentence_words)
        
        # Step 2: Merge overlapping/adjacent entities
        merged_entities = self._merge_overlapping_entities(restored_entities)
        
        # Step 3: Average metadata and clean up
        final_entities = []
        for entity_group in merged_entities:
            if isinstance(entity_group, list):
                # Multiple entities merged
                merged_entity = self._average_entity_metadata(entity_group, sentence_info)
            else:
                # Single entity
                merged_entity = self._finalize_single_entity(entity_group, sentence_info)
            
            final_entities.append(merged_entity)
        
        return final_entities
    
    def _restore_complete_entities(self, entities: List[Dict[str, Any]], 
                                 sentence_info: Dict[str, Any], 
                                 sentence_words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Restore truncated or incomplete entity text using TEI sentence."""
        
        sentence_text = sentence_info['text']
        sentence_start = sentence_info['char_start']
        
        restored_entities = []
        
        for entity in entities:
            entity_text = entity.get('text', '').strip()
            entity_start = entity.get('char_start', 0)
            entity_end = entity.get('char_end', 0)
            
            # Skip obviously corrupted entities (too short or garbled)
            if len(entity_text) <= 2 or self._is_text_corrupted(entity_text):
                logger.debug(f"Skipping corrupted entity: '{entity_text}'",
                           source="EnhancedMergingService._restore_complete_entities")
                continue
            
            # Calculate relative position in sentence
            relative_start = max(0, entity_start - sentence_start)
            relative_end = min(len(sentence_text), entity_end - sentence_start)
            
            # Validate positions are reasonable
            if relative_end <= relative_start or relative_start >= len(sentence_text):
                logger.debug(f"Invalid positions for entity: '{entity_text}' at {relative_start}:{relative_end}",
                           source="EnhancedMergingService._restore_complete_entities")
                continue
            
            # Extract text from TEI sentence at the exact position
            tei_extracted = sentence_text[relative_start:relative_end].strip()
            
            # Use TEI text if it's clean and makes sense
            if tei_extracted and len(tei_extracted) >= len(entity_text) and not self._is_text_corrupted(tei_extracted):
                # Check if TEI text is better than entity text
                if self._is_better_text(tei_extracted, entity_text):
                    logger.debug(f"Using TEI text: '{entity_text}' -> '{tei_extracted}'",
                               source="EnhancedMergingService._restore_complete_entities")
                    
                    restored_entity = entity.copy()
                    restored_entity['text'] = tei_extracted
                    restored_entity['restoration_applied'] = True
                    restored_entity['original_text'] = entity_text
                    restored_entities.append(restored_entity)
                else:
                    restored_entities.append(entity)
            else:
                # Keep original if TEI extraction doesn't help
                restored_entities.append(entity)
        
        return restored_entities
    
    def _is_entity_incomplete(self, entity_text: str, tei_text: str) -> bool:
        """Check if entity text appears to be incomplete compared to TEI text."""
        
        # Check for obvious truncation signs
        if entity_text.endswith('...') or len(entity_text) < 3:
            return True
        
        # Check if entity starts/ends with partial words
        if entity_text and not entity_text[0].isalpha() and entity_text[0] not in '([{':
            return True
        
        if entity_text and not entity_text[-1].isalnum() and entity_text[-1] not in ')]}':
            return True
        
        # Check significant length difference
        if tei_text and len(entity_text) < len(tei_text) * 0.7:
            return True
        
        return False
    
    def _restore_complete_word(self, entity_text: str, sentence_text: str, 
                             start_pos: int, end_pos: int) -> str:
        """Restore complete word/phrase from sentence context."""
        
        # Expand to word boundaries
        expanded_start = start_pos
        expanded_end = end_pos
        
        # Expand backwards to word start
        while expanded_start > 0 and sentence_text[expanded_start - 1].isalnum():
            expanded_start -= 1
        
        # Expand forwards to word end
        while expanded_end < len(sentence_text) and sentence_text[expanded_end].isalnum():
            expanded_end += 1
        
        # Handle bracket completion
        if start_pos > 0 and sentence_text[start_pos - 1] in '([{':
            # Find matching closing bracket
            bracket_map = {'(': ')', '[': ']', '{': '}'}
            open_bracket = sentence_text[start_pos - 1]
            close_bracket = bracket_map[open_bracket]
            
            bracket_end = sentence_text.find(close_bracket, end_pos)
            if bracket_end != -1:
                expanded_start = start_pos - 1
                expanded_end = bracket_end + 1
        
        restored_text = sentence_text[expanded_start:expanded_end].strip()
        
        # Validate restoration makes sense
        if len(restored_text) > len(entity_text) * 3:
            # Too much expansion, keep original
            return entity_text
        
        return restored_text if restored_text else entity_text
    
    def _merge_overlapping_entities(self, entities: List[Dict[str, Any]]) -> List[Any]:
        """Merge entities that overlap or should be combined (e.g., 'glass transition' + 'temperature')."""
        
        if len(entities) <= 1:
            return entities
        
        # Sort by character position
        sorted_entities = sorted(entities, key=lambda e: e.get('char_start', 0))
        
        merged_groups = []
        current_group = [sorted_entities[0]]
        
        for entity in sorted_entities[1:]:
            if self._should_merge_entities(current_group[-1], entity):
                current_group.append(entity)
                logger.debug(f"Merging entities: '{current_group[-2].get('text', '')}' + '{entity.get('text', '')}'",
                           source="EnhancedMergingService._merge_overlapping_entities")
            else:
                # Finalize current group
                if len(current_group) == 1:
                    merged_groups.append(current_group[0])
                else:
                    merged_groups.append(current_group)
                
                # Start new group
                current_group = [entity]
        
        # Add final group
        if len(current_group) == 1:
            merged_groups.append(current_group[0])
        else:
            merged_groups.append(current_group)
        
        return merged_groups
    
    def _should_merge_entities(self, entity1: Dict[str, Any], entity2: Dict[str, Any]) -> bool:
        """Determine if two entities should be merged - more conservative approach."""
        
        start1, end1 = entity1.get('char_start', 0), entity1.get('char_end', 0)
        start2, end2 = entity2.get('char_start', 0), entity2.get('char_end', 0)
        text1, text2 = entity1.get('text', ''), entity2.get('text', '')
        type1, type2 = entity1.get('entity_type', ''), entity2.get('entity_type', '')
        
        # Only merge if there's significant overlap (not just proximity)
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        overlap_length = max(0, overlap_end - overlap_start)
        
        # Require at least 50% overlap to merge
        min_length = min(end1 - start1, end2 - start2)
        if overlap_length < min_length * 0.5:
            return False
        
        # Don't merge if entities are different types unless they're closely related types
        if type1 != type2:
            # Only allow merging for very specific semantic relationships
            # REMOVED ('POLYMER', 'MATERIAL') to keep these as separate entity types
            related_type_pairs = [('PROPERTY', 'VALUE'), ('VALUE', 'UNIT')]
            type_pair = (type1, type2) if type1 < type2 else (type2, type1)
            if type_pair not in related_type_pairs:
                return False
        
        # Don't merge if text is completely different (avoid corruption)
        similarity = self._text_similarity(text1, text2)
        if similarity < 0.3:
            return False
        
        return True
    
    def _are_semantically_related(self, text1: str, text2: str, type1: str, type2: str) -> bool:
        """Check if two entities are semantically related and should be merged."""
        
        # Common multi-word scientific terms
        related_pairs = [
            ('glass', 'transition'),
            ('glass transition', 'temperature'),
            ('melting', 'point'),
            ('boiling', 'point'),
            ('molecular', 'weight'),
            ('glass', 'temperature'),
            ('storage', 'modulus'),
            ('loss', 'modulus'),
            ('young', 'modulus'),
            ('tensile', 'strength'),
            ('yield', 'strength'),
            ('elastic', 'modulus'),
        ]
        
        text1_lower = text1.lower().strip()
        text2_lower = text2.lower().strip()
        
        # Check both directions
        for term1, term2 in related_pairs:
            if (term1 in text1_lower and term2 in text2_lower) or \
               (term1 in text2_lower and term2 in text1_lower):
                return True
        
        # Check for unit-value relationships
        if type1 == 'VALUE' and type2 == 'UNIT':
            return True
        if type1 == 'UNIT' and type2 == 'VALUE':
            return True
        
        # Check for property-value relationships
        if type1 == 'PROPERTY' and type2 == 'VALUE':
            return True
        if type1 == 'VALUE' and type2 == 'PROPERTY':
            return True
        
        return False
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity between two strings."""
        if not text1 or not text2:
            return 0.0
        
        # Use SequenceMatcher for similarity
        matcher = SequenceMatcher(None, text1.lower(), text2.lower())
        return matcher.ratio()
    
    def _average_entity_metadata(self, entity_group: List[Dict[str, Any]], 
                               sentence_info: Dict[str, Any]) -> Dict[str, Any]:
        """Average metadata from multiple entities that were merged."""
        
        if not entity_group:
            return {}
        
        if len(entity_group) == 1:
            return self._finalize_single_entity(entity_group[0], sentence_info)
        
        # Determine merged text and span
        merged_text = self._create_merged_text(entity_group)
        min_start = min(e.get('char_start', 0) for e in entity_group)
        max_end = max(e.get('char_end', 0) for e in entity_group)
        
        # Choose primary entity type (most common or highest confidence)
        entity_types = [e.get('entity_type', '') for e in entity_group]
        primary_type = Counter(entity_types).most_common(1)[0][0]
        
        # Average numerical metadata
        confidences = [e.get('confidence', 0) for e in entity_group if e.get('confidence')]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Collect models that voted
        all_models = []
        for entity in entity_group:
            if 'model' in entity:
                all_models.append(entity['model'])
            if 'models_voted' in entity:
                all_models.extend(entity['models_voted'])
        
        unique_models = list(set(all_models))
        
        # Create merged entity
        merged_entity = {
            'text': merged_text,
            'char_start': min_start,
            'char_end': max_end,
            'confidence': avg_confidence,
            'entity_type': primary_type,
            'sentence_id': sentence_info['sentence_id'],
            'sentence_text': sentence_info['text'],  # TEI sentence, not token window
            'paragraph_id': sentence_info['paragraph_id'],
            'models_voted': unique_models,
            'cluster_size': len(entity_group),
            'consolidation_reason': f"Merged {len(entity_group)} overlapping entities",
            'source_document_length': entity_group[0].get('source_document_length', 0),
            'merged_from': len(entity_group),
            'context_snippet': self._extract_context_snippet(
                sentence_info['text'], merged_text, min_start - sentence_info['char_start']
            )
        }
        
        # Average other numerical fields
        numerical_fields = ['calibrated_confidence', 'token_position']
        for field in numerical_fields:
            values = [e.get(field) for e in entity_group if e.get(field) is not None]
            if values:
                merged_entity[field] = sum(values) / len(values)
        
        # Combine list fields
        list_fields = ['validation_flags', 'postprocessing_applied', 'validation_boosts_applied']
        for field in list_fields:
            all_values = []
            for entity in entity_group:
                if field in entity and isinstance(entity[field], list):
                    all_values.extend(entity[field])
            if all_values:
                merged_entity[field] = list(set(all_values))  # Remove duplicates
        
        return merged_entity
    
    def _create_merged_text(self, entity_group: List[Dict[str, Any]]) -> str:
        """Create merged text from multiple entities, handling overlaps intelligently."""
        
        if len(entity_group) == 1:
            return entity_group[0].get('text', '')
        
        # Sort by position
        sorted_entities = sorted(entity_group, key=lambda e: e.get('char_start', 0))
        
        # Check if entities are adjacent/overlapping vs separated
        texts = []
        positions = []
        
        for entity in sorted_entities:
            text = entity.get('text', '').strip()
            start = entity.get('char_start', 0)
            end = entity.get('char_end', 0)
            
            if text:
                texts.append(text)
                positions.append((start, end))
        
        if not texts:
            return ""
        
        # If only one text after filtering, return it
        if len(texts) == 1:
            return texts[0]
        
        # Check gaps between entities
        gaps = []
        for i in range(len(positions) - 1):
            gap = positions[i + 1][0] - positions[i][1]
            gaps.append(gap)
        
        # If small gaps (<=3 characters), join with single space
        # If larger gaps, there might be intervening words to preserve
        if all(gap <= 3 for gap in gaps):
            return ' '.join(texts)
        else:
            # More complex merging - try to preserve intervening content
            # For now, just join with space but log the complex case
            logger.debug(f"Complex merge case: {texts} with gaps {gaps}",
                       source="EnhancedMergingService._create_merged_text")
            return ' '.join(texts)
    
    def _finalize_single_entity(self, entity: Dict[str, Any], 
                              sentence_info: Dict[str, Any]) -> Dict[str, Any]:
        """Finalize a single entity with correct sentence_text from TEI."""
        
        finalized = entity.copy()
        
        # Set correct sentence information from TEI (not token window)
        finalized['sentence_id'] = sentence_info['sentence_id']
        finalized['sentence_text'] = sentence_info['text']
        finalized['paragraph_id'] = sentence_info['paragraph_id']
        
        # Ensure required fields exist
        if 'models_voted' not in finalized and 'model' in finalized:
            finalized['models_voted'] = [finalized['model']]
        
        if 'cluster_size' not in finalized:
            finalized['cluster_size'] = 1
        
        if 'consolidation_reason' not in finalized:
            finalized['consolidation_reason'] = "single_prediction"
        
        # Update context snippet if needed
        if 'context_snippet' not in finalized or not finalized['context_snippet']:
            entity_text = finalized.get('text', '')
            sentence_text = sentence_info['text']
            relative_pos = finalized.get('char_start', 0) - sentence_info['char_start']
            
            finalized['context_snippet'] = self._extract_context_snippet(
                sentence_text, entity_text, relative_pos
            )
        
        return finalized
    
    def _extract_context_snippet(self, sentence_text: str, entity_text: str, 
                                entity_pos: int, context_size: int = 50) -> str:
        """Extract context snippet around entity in sentence."""
        
        if not sentence_text or not entity_text:
            return ""
        
        # Find entity in sentence
        entity_start = max(0, entity_pos)
        entity_end = entity_start + len(entity_text)
        
        # Extract context
        context_start = max(0, entity_start - context_size)
        context_end = min(len(sentence_text), entity_end + context_size)
        
        context = sentence_text[context_start:context_end]
        
        # Add brackets around entity if it's visible in context
        if entity_start >= context_start and entity_end <= context_end:
            relative_start = entity_start - context_start
            relative_end = entity_end - context_start
            
            context = (context[:relative_start] + 
                      '[' + context[relative_start:relative_end] + ']' + 
                      context[relative_end:])
        
        return context.strip()
    
    def _is_text_corrupted(self, text: str) -> bool:
        """Check if text appears to be corrupted or garbled."""
        if not text or len(text) <= 2:
            return True
        
        # Check for repetitive patterns (sign of corruption)
        if len(text) > 10:
            # Look for repeated short sequences
            for i in range(len(text) - 3):
                pattern = text[i:i+2]
                if text.count(pattern) > 3:  # Too many repetitions
                    return True
        
        # Check for excessive punctuation or special characters
        special_count = sum(1 for c in text if not c.isalnum() and c not in ' ()-[]{}.,;:')
        if len(text) > 0 and special_count / len(text) > 0.3:
            return True
        
        # Check for gibberish (too many consonants or vowels in a row)
        vowels = 'aeiouAEIOU'
        consonant_run = 0
        vowel_run = 0
        
        for char in text:
            if char.isalpha():
                if char in vowels:
                    vowel_run += 1
                    consonant_run = 0
                    if vowel_run > 4:  # Too many consecutive vowels
                        return True
                else:
                    consonant_run += 1
                    vowel_run = 0
                    if consonant_run > 5:  # Too many consecutive consonants
                        return True
            else:
                consonant_run = 0
                vowel_run = 0
        
        return False
    
    def _is_better_text(self, tei_text: str, entity_text: str) -> bool:
        """Determine if TEI text is better than entity text."""
        if not tei_text or not entity_text:
            return bool(tei_text and not entity_text)
        
        # TEI text is better if:
        # 1. Entity text is corrupted but TEI text is not
        if self._is_text_corrupted(entity_text) and not self._is_text_corrupted(tei_text):
            return True
        
        # 2. TEI text is longer and contains the entity text
        if len(tei_text) > len(entity_text) and entity_text.lower() in tei_text.lower():
            return True
        
        # 3. Entity text is a fragment but TEI text is complete
        if len(entity_text) <= 3 and len(tei_text) > 3 and not self._is_text_corrupted(tei_text):
            return True
        
        return False
