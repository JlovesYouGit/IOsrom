#!/usr/bin/env python3
"""
Binary Token Attention Graph for Firmware Pattern Matching
Adapted from Vemex's TokenAttentionGraph for binary data.

Instead of text tokens, this works with:
- Byte signatures (magic bytes)
- Structural patterns (headers, offsets, sizes)
- Entropy clusters (compressed vs uncompressed regions)
"""

import json
import math
import struct
from pathlib import Path
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Set


FORMULA_TABLE_PATH = Path(__file__).parent / "firmware_formula_table.json"


@dataclass
class ByteToken:
    token_id: str
    token_type: str
    pattern: bytes
    weight: float = 1.0
    entropy: float = 0.0
    confidence: float = 0.0
    metadata: Dict = field(default_factory=dict)


@dataclass
class PatternMatch:
    token_id: str
    offset: int
    length: int
    confidence: float
    context: Dict = field(default_factory=dict)


class BinaryTokenAttentionGraph:
    """Builds an attention graph over binary patterns in firmware data."""

    def __init__(self, formula_table: list):
        self.table = {e["id"]: e for e in formula_table}
        self.tokens: Dict[str, ByteToken] = {}
        self.cooccurrence = defaultdict(lambda: defaultdict(int))
        self.token_positions: Dict[str, List[int]] = defaultdict(list)
        self._build()

    def _tokenize_signature(self, magic_hex: str) -> List[str]:
        """Convert hex magic bytes into token sequence."""
        if not magic_hex:
            return []
        tokens = []
        # Split into 2-byte chunks for pattern matching
        for i in range(0, len(magic_hex) - 1, 2):
            chunk = magic_hex[i:i+2]
            tokens.append(f"0x{chunk}")
        # Also add full signature
        if len(magic_hex) >= 4:
            tokens.append(f"sig_{magic_hex[:8]}")
        return tokens

    def _calculate_entropy(self, data: bytes, offset: int, length: int = 256) -> float:
        """Calculate Shannon entropy of a data region."""
        if len(data) < offset + length:
            length = len(data) - offset
        if length <= 0:
            return 0.0
        region = data[offset:offset + length]
        counts = Counter(region)
        total = len(region)
        return -sum((c / total) * math.log2(c / total) for c in counts.values() if c > 0)

    def _build(self):
        """Build token graph from firmware formula table."""
        for fid, entry in self.table.items():
            magic_hex = entry.get("magic_bytes", "")
            tokens = self._tokenize_signature(magic_hex)
            category = entry.get("category", "unknown")
            
            token_id = f"formula_{fid}"
            self.tokens[token_id] = ByteToken(
                token_id=token_id,
                token_type=category,
                pattern=bytes.fromhex(magic_hex) if magic_hex else b"",
                weight=entry.get("confidence", 1.0),
                confidence=entry.get("confidence", 1.0),
                metadata={
                    "formula_id": fid,
                    "description": entry.get("description", ""),
                    "min_size": entry.get("min_size", 0),
                }
            )

            # Co-occurrence based on shared category keywords
            for other_fid, other_entry in self.table.items():
                if other_fid == fid:
                    continue
                other_cat = other_entry.get("category", "")
                if category == other_cat:
                    self.cooccurrence[token_id][f"formula_{other_fid}"] += 1

        # Normalize weights
        for token_id, token in self.tokens.items():
            total_co = sum(self.cooccurrence[token_id].values())
            token.entropy = total_co / max(len(self.table), 1)

    def scan_data(self, data: bytes, min_confidence: float = 0.5) -> List[PatternMatch]:
        """Scan binary data for known firmware patterns."""
        matches = []
        data_len = len(data)
        
        for token_id, token in self.tokens.items():
            pattern = token.pattern
            if not pattern:
                continue
            
            confidence = token.confidence
            if confidence < min_confidence:
                continue
            
            # Search for pattern in data
            pos = 0
            while True:
                pos = data.find(pattern, pos)
                if pos == -1:
                    break
                
                # Calculate context entropy
                entropy = self._calculate_entropy(data, max(0, pos - 128), 256)
                
                matches.append(PatternMatch(
                    token_id=token_id,
                    offset=pos,
                    length=len(pattern),
                    confidence=confidence,
                    context={
                        "entropy": entropy,
                        "description": token.metadata.get("description", ""),
                        "category": token.token_type,
                    }
                ))
                pos += len(pattern)
        
        # Sort by offset for ordered analysis
        matches.sort(key=lambda m: m.offset)
        return matches

    def get_attention_between(self, token_a: str, token_b: str) -> float:
        """Get attention weight between two patterns."""
        return self.cooccurrence.get(token_a, {}).get(token_b, 0)

    def top_attended_patterns(self, n: int = 20) -> List[ByteToken]:
        """Return most attended (highest co-occurrence) patterns."""
        return sorted(self.tokens.values(), key=lambda t: t.entropy, reverse=True)[:n]

    def get_pattern_neighbors(self, token_id: str) -> List[Tuple[str, float]]:
        """Get neighboring patterns by attention."""
        neighbors = self.cooccurrence.get(token_id, {})
        return sorted(neighbors.items(), key=lambda x: x[1], reverse=True)


class FirmwareSpatialGraph:
    """64-dim spatial graph for firmware component relationships.
    Adapted from Vemex's Satoshi-NM spatial node graph.
    """

    def __init__(self, formula_table: list):
        self.nodes: Dict[str, Dict] = {}
        self.formula_table = {e["id"]: e for e in formula_table}
        self._build_graph()

    def _build_graph(self):
        """Build spatial nodes for each firmware component."""
        categories = {}
        for fid, entry in self.formula_table.items():
            cat = entry.get("category", "unknown")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(fid)

        for fid, entry in self.formula_table.items():
            # Create 64-dim vector based on category and properties
            vec = self._create_vector(entry, categories)
            self.nodes[f"formula_{fid}"] = {
                "id": f"formula_{fid}",
                "formula_id": fid,
                "vector": vec,
                "category": entry.get("category", "unknown"),
                "description": entry.get("description", ""),
                "confidence": entry.get("confidence", 1.0),
            }

    def _create_vector(self, entry: Dict, categories: Dict) -> List[float]:
        """Create 64-dim semantic vector for a firmware pattern."""
        vec = [0.0] * 64
        
        # Category encoding (first 16 dims)
        cat = entry.get("category", "unknown")
        cat_hash = hash(cat) % 16
        vec[cat_hash] = 1.0
        
        # Confidence encoding (dims 16-24)
        conf = entry.get("confidence", 1.0)
        conf_bucket = int(conf * 8)
        vec[16 + conf_bucket] = 1.0
        
        # Magic byte signature encoding (dims 24-48)
        magic = entry.get("magic_bytes", "")
        if magic:
            for i, ch in enumerate(magic[:12]):
                vec[24 + (i % 24)] += float(int(ch, 16)) / 255.0
        
        # Size encoding (dims 48-56)
        min_size = entry.get("min_size", 0)
        size_bucket = min(int(math.log2(max(min_size, 1))) % 8, 7)
        vec[48 + size_bucket] = 1.0
        
        # Hash-based noise for uniqueness (dims 56-64)
        name_hash = hash(entry.get("description", "")) & 0xFFFFFFFFFFFFFFFF
        for i in range(8):
            vec[56 + i] = ((name_hash >> (i * 4)) & 0xF) / 16.0
        
        return vec

    def find_similar(self, token_id: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Find spatially similar firmware patterns."""
        if token_id not in self.nodes:
            return []
        
        target_vec = self.nodes[token_id]["vector"]
        similarities = []
        
        for other_id, other_node in self.nodes.items():
            if other_id == token_id:
                continue
            sim = self._cosine_similarity(target_vec, other_node["vector"])
            similarities.append((other_id, sim))
        
        return sorted(similarities, key=lambda x: x[1], reverse=True)[:top_k]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    def cluster_by_category(self) -> Dict[str, List[str]]:
        """Group firmware patterns by category."""
        clusters = defaultdict(list)
        for node_id, node in self.nodes.items():
            clusters[node["category"]].append(node_id)
        return dict(clusters)


class HashPipeline:
    """Adapted from Vemex's BowOfAchilles hash pipeline for firmware data."""

    @staticmethod
    def hash_region(data: bytes, offset: int, length: int = 4096) -> str:
        """Hash a region of firmware data."""
        region = data[offset:offset + length]
        import hashlib
        return hashlib.sha3_256(region).hexdigest()[:16]

    @staticmethod
    def calculate_entropy(data: bytes, offset: int, length: int = 4096) -> float:
        """Calculate Shannon entropy of a firmware region."""
        if len(data) < offset + length:
            length = len(data) - offset
        if length <= 0:
            return 0.0
        region = data[offset:offset + length]
        counts = Counter(region)
        total = len(region)
        return -sum((c / total) * math.log2(c / total) for c in counts.values() if c > 0)

    @staticmethod
    def detect_compression_type(data: bytes, offset: int) -> str:
        """Detect compression type at offset."""
        magic = data[offset:offset + 4]
        if magic == b'\x28\xb5\x2f\xfd':
            return "zstd"
        elif magic == b'\x04\x22\x4d\x18':
            return "lz4"
        elif magic in (b'\x02\x21\x4c\x18', b'\x03\x21\x4c\x18', b'\x04\x21\x4c\x18', b'\x05\x21\x4c\x18'):
            return "lz4_skippable"
        elif magic[:2] == b'\x1f\x8b':
            return "gzip"
        elif magic[:2] == b'PK':
            return "zip"
        elif magic == b'\x50\x4b':
            return "zip"
        return "unknown"


def load_formula_table(path: Path = FORMULA_TABLE_PATH) -> list:
    """Load firmware formula table."""
    with open(path, "r") as f:
        return json.load(f)
