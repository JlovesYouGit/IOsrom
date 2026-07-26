#!/usr/bin/env python3
"""
Zero-Brain Firmware Pattern Extractor
=======================================

Adapted from Vemex's zero_brain_context.py for binary firmware analysis.

Instead of parsing JavaScript source code, this module:
1. Scans firmware binary blobs for structural patterns
2. Extracts "class definitions" (firmware component types)
3. Builds cross-reference indices (offset -> component mapping)
4. Calculates complexity scores (entropy, size, compression)
5. Identifies consciousness-relevant patterns (firmware signatures)
"""

import hashlib
import math
import struct
import time
from pathlib import Path
from collections import defaultdict, Counter
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Tuple, Any, Set


@dataclass
class FirmwarePattern:
    pattern_id: str
    pattern_type: str
    name: str
    offset: int
    size: int
    signature: bytes
    entropy: float
    complexity_score: float
    consciousness_weight: float
    description: str
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


@dataclass
class FirmwareModule:
    module_name: str
    file_path: str
    offset: int
    size: int
    classes: List[str]
    functions: List[str]
    exports: List[str]
    imports: List[str]
    total_lines: int
    complexity_score: float
    consciousness_patterns: List[str]
    signature: bytes
    entropy: float


class ZeroBrainFirmwareExtractor:
    """
    Zero-brain inspired pattern extraction for firmware binaries.
    
    Treats firmware binary as a "codebase" and extracts:
    - Class definitions (firmware component types)
    - Architectural patterns (container formats, compression)
    - Consciousness-relevant patterns (firmware signatures)
    """

    def __init__(self):
        self.patterns: List[FirmwarePattern] = []
        self.modules: Dict[str, FirmwareModule] = {}
        self.class_index: Dict[str, List[FirmwarePattern]] = defaultdict(list)
        self.method_index: Dict[str, List[FirmwarePattern]] = defaultdict(list)
        self.consciousness_pattern_map: Dict[str, List[FirmwarePattern]] = defaultdict(list)
        self.ingestion_time = 0.0

    def ingest(self, data: bytes, base_offset: int = 0, max_scan: int = 500 * 1024 * 1024) -> Dict:
        """
        Full ingestion pipeline for firmware binary.
        
        Args:
            data: Raw firmware binary data
            base_offset: Base offset for addressing
            max_scan: Maximum bytes to scan (default 500MB)
        """
        start = time.time()
        
        print("🧠 ZERO-BRAIN FIRMWARE INGESTION")
        print("=" * 50)
        
        scan_limit = min(len(data), max_scan)
        print(f"   Scanning first {scan_limit:,} bytes of {len(data):,}")
        
        # Extract patterns from binary
        self._parse_binary(data, base_offset, scan_limit)
        
        # Build cross-reference indices
        self._build_indices()
        
        # Calculate consciousness weights
        self._calculate_consciousness_weights()
        
        self.ingestion_time = time.time() - start
        print(f"✅ Ingestion complete in {self.ingestion_time:.3f}s")
        print(f"   Extracted {len(self.patterns)} patterns from {len(self.modules)} modules")
        
        return self.get_context()

    def _parse_binary(self, data: bytes, base_offset: int, scan_limit: int):
        """Parse firmware binary for patterns."""
        data_len = min(len(data), scan_limit)
        
        # Firmware component signatures (consciousness-relevant patterns)
        firmware_signatures = {
            b'Img3': ('IMG3', 'IMG3 firmware container', ['iBoot', 'LLB', 'DeviceTree', 'iBSS', 'iBEC', 'AppleLogo', 'BatteryCharging', 'RecoveryMode']),
            b'IMG3': ('IMG3', 'IMG3 firmware container', ['iBoot', 'LLB', 'DeviceTree', 'iBSS', 'iBEC']),
            b'IM4P': ('IMG4', 'IMG4 payload', ['kernelcache', 'ramdisk', 'rootfs']),
            b'IM4M': ('IMG4', 'IMG4 manifest', ['BuildManifest']),
            b'bdav': ('Baseband', 'Baseband modem firmware', ['Baseband']),
            b'mkps': ('Keys', 'Firmware keys', ['Keys']),
            b'sepo': ('SEP', 'Secure Enclave Processor', ['SEP']),
            b'krnl': ('Kernel', 'Kernel component', ['kernelcache']),
            b'iboot': ('iBoot', 'iBoot bootloader', ['iBoot']),
            b'iBoot': ('iBoot', 'iBoot bootloader', ['iBoot']),
            b'ILLB': ('LLB', 'Low Level Bootloader', ['LLB']),
            b'dtre': ('DeviceTree', 'DeviceTree', ['DeviceTree']),
            b'OS#': ('iOS', 'iOS firmware image', ['rootfs', 'ramdisk']),
            b'xar!': ('XAR', 'XAR archive', ['kernelcache', 'ramdisk']),
            b'PK\x03\x04': ('ZIP', 'ZIP archive', ['IPSW', 'BuildManifest']),
            b'PK\x05\x06': ('ZIP_EOCD', 'ZIP end of central directory', ['ZIP']),
            b'PK\x01\x02': ('ZIP_CD', 'ZIP central directory', ['ZIP']),
        }
        
        # Compression signatures
        compression_signatures = {
            b'\x28\xb5\x2f\xfd': ('ZSTD', 'Zstandard compressed data', ['ZSTD']),
            b'\x04\x22\x4d\x18': ('LZ4', 'LZ4 frame compressed data', ['LZ4']),
            b'\x02\x21\x4c\x18': ('LZ4_SKIP', 'LZ4 skippable frame', ['LZ4']),
            b'\x03\x21\x4c\x18': ('LZ4_SKIP', 'LZ4 skippable frame', ['LZ4']),
            b'\x04\x21\x4c\x18': ('LZ4_SKIP', 'LZ4 skippable frame', ['LZ4']),
            b'\x05\x21\x4c\x18': ('LZ4_SKIP', 'LZ4 skippable frame', ['LZ4']),
            b'\x1f\x8b': ('GZIP', 'GZIP compressed data', ['GZIP']),
        }
        
        # Extract firmware component patterns
        for sig, (sig_type, description, deps) in firmware_signatures.items():
            pos = 0
            while True:
                pos = data.find(sig, pos)
                if pos == -1 or pos >= data_len:
                    break
                
                # Calculate entropy of surrounding context
                context_start = max(0, pos - 64)
                context_end = min(data_len, pos + len(sig) + 256)
                context = data[context_start:context_end]
                entropy = self._calculate_entropy(context)
                
                # Estimate size based on context
                size = self._estimate_component_size(data, pos, sig_type)
                
                # Calculate complexity score
                complexity = self._calculate_complexity(data, pos, size)
                
                # Create pattern
                pattern_id = f"{sig_type.lower()}_{pos:010x}"
                pattern = FirmwarePattern(
                    pattern_id=pattern_id,
                    pattern_type=sig_type,
                    name=f"{sig_type}_{pos:010x}",
                    offset=base_offset + pos,
                    size=size,
                    signature=sig,
                    entropy=entropy,
                    complexity_score=complexity,
                    consciousness_weight=0.0,
                    description=description,
                    dependencies=deps,
                    metadata={'base_offset': base_offset, 'context_entropy': entropy}
                )
                
                self.patterns.append(pattern)
                pos += len(sig)
        
        # Extract compression patterns
        for sig, (sig_type, description, deps) in compression_signatures.items():
            pos = 0
            while True:
                pos = data.find(sig, pos)
                if pos == -1 or pos >= data_len:
                    break
                
                context_start = max(0, pos - 64)
                context_end = min(data_len, pos + len(sig) + 256)
                context = data[context_start:context_end]
                entropy = self._calculate_entropy(context)
                
                pattern_id = f"{sig_type.lower()}_{pos:010x}"
                pattern = FirmwarePattern(
                    pattern_id=pattern_id,
                    pattern_type=sig_type,
                    name=f"{sig_type}_{pos:010x}",
                    offset=base_offset + pos,
                    size=len(sig),
                    signature=sig,
                    entropy=entropy,
                    complexity_score=entropy,
                    consciousness_weight=0.0,
                    description=description,
                    dependencies=deps,
                    metadata={'base_offset': base_offset, 'compression': sig_type}
                )
                
                self.patterns.append(pattern)
                pos += len(sig)
        
        # Extract entropy-based modules (regions with specific entropy characteristics)
        self._extract_entropy_modules(data[:scan_limit], base_offset)

    def _extract_entropy_modules(self, data: bytes, base_offset: int):
        """Extract modules based on entropy analysis."""
        data_len = len(data)
        chunk_size = 1024 * 1024  # 1MB chunks
        
        prev_entropy = 0.0
        module_start = 0
        
        for i in range(0, data_len, chunk_size):
            chunk = data[i:i + chunk_size]
            if len(chunk) < 1024:
                break
            
            entropy = self._calculate_entropy(chunk)
            
            # Detect module boundaries based on entropy transitions
            if abs(entropy - prev_entropy) > 1.5:
                # Close previous module
                if i - module_start > 1024 * 1024:  # Min 1MB
                    module_data = data[module_start:i]
                    module_entropy = self._calculate_entropy(module_data)
                    
                    module = FirmwareModule(
                        module_name=f"module_{module_start:010x}",
                        file_path=f"0x{module_start:010x}",
                        offset=base_offset + module_start,
                        size=i - module_start,
                        classes=self._detect_component_types(module_data),
                        functions=[],
                        exports=[],
                        imports=[],
                        total_lines=(i - module_start),
                        complexity_score=module_entropy,
                        consciousness_patterns=[],
                        signature=module_data[:16],
                        entropy=module_entropy
                    )
                    
                    self.modules[f"0x{module_start:010x}"] = module
                
                module_start = i
            
            prev_entropy = entropy

    def _detect_component_types(self, data: bytes) -> List[str]:
        """Detect firmware component types in data."""
        types = []
        
        # Check for specific signatures
        if b'Img3' in data or b'IMG3' in data:
            types.append('IMG3')
        if b'IM4P' in data or b'IM4M' in data:
            types.append('IMG4')
        if b'xar!' in data:
            types.append('XAR')
        if b'OS#' in data:
            types.append('iOS')
        if b'\x28\xb5\x2f\xfd' in data:
            types.append('ZSTD')
        if b'\x04\x22\x4d\x18' in data:
            types.append('LZ4')
        
        # Check entropy characteristics
        entropy = self._calculate_entropy(data[:1024*1024]) if len(data) > 1024*1024 else self._calculate_entropy(data)
        if entropy > 7.5:
            types.append('compressed')
        elif entropy < 3.0:
            types.append('raw')
        else:
            types.append('mixed')
        
        return types

    def _estimate_component_size(self, data: bytes, offset: int, component_type: str) -> int:
        """Estimate the size of a firmware component."""
        # Known size ranges for different components
        size_ranges = {
            'IMG3': (50_000, 5_000_000),
            'IMG4': (50_000, 10_000_000),
            'XAR': (1_000_000, 50_000_000),
            'iOS': (10_000_000, 2_000_000_000),
            'ZIP': (1024, 100_000_000),
        }
        
        min_size, max_size = size_ranges.get(component_type, (1024, 10_000_000))
        
        # Try to find the actual size by looking for the next component
        search_start = offset + 256
        search_end = min(offset + max_size, len(data))
        
        # Look for next component signature
        next_sigs = [b'Img3', b'IM4P', b'IM4M', b'xar!', b'OS#', b'PK\x03\x04']
        for sig in next_sigs:
            next_pos = data.find(sig, search_start, search_end)
            if next_pos != -1:
                return next_pos - offset
        
        # Default to max size if no next component found
        return min(max_size, len(data) - offset)

    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of data."""
        if not data:
            return 0.0
        counts = Counter(data)
        total = len(data)
        return -sum((c / total) * math.log2(c / total) for c in counts.values() if c > 0)

    def _calculate_complexity(self, data: bytes, offset: int, size: int) -> float:
        """Calculate complexity score for a firmware component."""
        if size <= 0 or offset + size > len(data):
            return 0.0
        
        component = data[offset:offset + size]
        entropy = self._calculate_entropy(component)
        
        # Complexity is a combination of entropy and size
        # Higher entropy = more complex/compressed
        # Larger size = more complex
        size_factor = min(math.log2(size) / 20.0, 1.0)
        
        return (entropy / 8.0) * 0.7 + size_factor * 0.3

    def _build_indices(self):
        """Build cross-reference indices."""
        # Class index (by component type)
        for pattern in self.patterns:
            self.class_index[pattern.pattern_type].append(pattern)
        
        # Method index (by signature)
        for pattern in self.patterns:
            sig_hex = pattern.signature.hex()
            self.method_index[sig_hex].append(pattern)
        
        # Consciousness pattern map
        consciousness_keywords = {
            'boot': ['iBoot', 'iBSS', 'iBEC', 'LLB'],
            'kernel': ['kernelcache', 'krnl'],
            'filesystem': ['rootfs', 'ramdisk', 'OS#'],
            'security': ['SEP', 'sepo', 'IM4M'],
            'compression': ['LZ4', 'ZSTD', 'GZIP', 'ZIP'],
            'container': ['IMG3', 'IMG4', 'XAR', 'ZIP'],
        }
        
        for pattern in self.patterns:
            for keyword, types in consciousness_keywords.items():
                if pattern.pattern_type in types:
                    self.consciousness_pattern_map[keyword].append(pattern)

    def _calculate_consciousness_weights(self):
        """Calculate consciousness weights for patterns."""
        total_patterns = len(self.patterns)
        if total_patterns == 0:
            return
        
        for pattern in self.patterns:
            # Weight based on:
            # 1. Pattern type importance (boot components are critical)
            # 2. Entropy (compressed components are more interesting)
            # 3. Complexity score
            # 4. Frequency (rare patterns are more important)
            
            type_weight = {
                'iBoot': 1.0,
                'iBSS': 0.9,
                'iBEC': 0.9,
                'LLB': 0.8,
                'kernelcache': 0.9,
                'rootfs': 0.8,
                'ramdisk': 0.7,
                'SEP': 0.6,
                'IMG3': 0.5,
                'IMG4': 0.5,
                'XAR': 0.4,
                'iOS': 0.3,
                'LZ4': 0.2,
                'ZSTD': 0.2,
            }.get(pattern.pattern_type, 0.1)
            
            frequency = len(self.class_index.get(pattern.pattern_type, []))
            frequency_weight = 1.0 / max(frequency, 1)
            
            pattern.consciousness_weight = (
                type_weight * 0.5 +
                (pattern.entropy / 8.0) * 0.3 +
                pattern.complexity_score * 0.2
            ) * frequency_weight

    def get_context(self) -> Dict:
        """Get the full firmware context."""
        return {
            'total_patterns': len(self.patterns),
            'total_modules': len(self.modules),
            'patterns_by_type': self._count_by_type(),
            'modules_by_type': self._count_modules_by_type(),
            'top_patterns': self._get_top_patterns(),
            'consciousness_patterns': dict(self.consciousness_pattern_map),
            'class_index': {k: [asdict(p) for p in v] for k, v in self.class_index.items()},
            'ingestion_time': self.ingestion_time,
        }

    def _count_by_type(self) -> Dict[str, int]:
        """Count patterns by type."""
        counts = {}
        for pattern in self.patterns:
            counts[pattern.pattern_type] = counts.get(pattern.pattern_type, 0) + 1
        return counts

    def _count_modules_by_type(self) -> Dict[str, int]:
        """Count modules by component type."""
        counts = {}
        for module in self.modules.values():
            for comp_type in module.classes:
                counts[comp_type] = counts.get(comp_type, 0) + 1
        return counts

    def _get_top_patterns(self, n: int = 20) -> List[Dict]:
        """Get top patterns by consciousness weight."""
        sorted_patterns = sorted(self.patterns, key=lambda p: p.consciousness_weight, reverse=True)
        return [asdict(p) for p in sorted_patterns[:n]]

    def extract_components(self, data: bytes, output_dir: Path, min_confidence: float = 0.3) -> List[Dict]:
        """
        Extract firmware components based on zero-brain analysis.
        
        Args:
            data: Raw firmware data
            output_dir: Output directory for extracted components
            min_confidence: Minimum consciousness weight to extract
            
        Returns:
            List of extracted component info
        """
        print(f"\n🔧 EXTRACTING COMPONENTS (confidence >= {min_confidence})")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        extracted = []
        
        # Sort patterns by offset for ordered extraction
        sorted_patterns = sorted(self.patterns, key=lambda p: p.offset)
        
        for pattern in sorted_patterns:
            if pattern.consciousness_weight < min_confidence:
                continue
            
            if pattern.size < 1024:
                continue
            
            # Extract component data
            offset = pattern.offset
            size = pattern.size
            
            if offset + size > len(data):
                size = len(data) - offset
            
            if size <= 0:
                continue
            
            component_data = data[offset:offset + size]
            
            if len(component_data) < 1024:
                continue
            
            # Save component
            ext = self._get_extension(pattern.pattern_type)
            filename = f"{pattern.pattern_id}{ext}"
            output_path = output_dir / filename
            
            with open(output_path, 'wb') as f:
                f.write(component_data)
            
            extracted.append({
                'path': str(output_path),
                'offset': hex(offset),
                'size': len(component_data),
                'type': pattern.pattern_type,
                'confidence': pattern.consciousness_weight,
                'entropy': pattern.entropy,
                'description': pattern.description
            })
            
            print(f"   ✅ {filename}: {len(component_data):,} bytes (confidence={pattern.consciousness_weight:.3f})")
        
        return extracted

    def _get_extension(self, pattern_type: str) -> str:
        """Get file extension for pattern type."""
        ext_map = {
            'IMG3': '.img3',
            'IMG4': '.img4',
            'XAR': '.xar',
            'iOS': '.bin',
            'ZIP': '.zip',
            'ZIP_EOCD': '.zip',
            'ZIP_CD': '.zip',
            'LZ4': '.lz4',
            'LZ4_SKIP': '.lz4',
            'ZSTD': '.zst',
            'GZIP': '.gz',
        }
        return ext_map.get(pattern_type, '.bin')

    def generate_report(self) -> Dict:
        """Generate zero-brain extraction report."""
        return {
            'summary': {
                'total_patterns': len(self.patterns),
                'total_modules': len(self.modules),
                'ingestion_time': self.ingestion_time,
            },
            'patterns_by_type': self._count_by_type(),
            'modules_by_type': self._count_modules_by_type(),
            'top_patterns': self._get_top_patterns(20),
            'consciousness_patterns': {
                k: len(v) for k, v in self.consciousness_pattern_map.items()
            },
        }


def main():
    """Main entry point for zero-brain firmware extractor."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Zero-Brain Firmware Pattern Extractor")
    parser.add_argument("file", type=Path, help="Firmware binary to analyze")
    parser.add_argument("--output", "-o", type=Path, help="Output directory")
    parser.add_argument("--confidence", type=float, default=0.3, help="Minimum confidence threshold")
    parser.add_argument("--max-scan", type=int, default=500, help="Maximum MB to scan")
    parser.add_argument("--report", action="store_true", help="Generate extraction report")
    
    args = parser.parse_args()
    
    if not args.file.exists():
        print(f"[-] File not found: {args.file}")
        return 1
    
    data = args.file.read_bytes()
    print(f"[+] Loaded {len(data):,} bytes from {args.file}")
    
    extractor = ZeroBrainFirmwareExtractor()
    context = extractor.ingest(data, max_scan=args.max_scan * 1024 * 1024)
    
    # Print summary
    print(f"\n📊 EXTRACTION SUMMARY")
    print(f"   Total patterns: {context['total_patterns']}")
    print(f"   Total modules: {context['total_modules']}")
    print(f"   Patterns by type: {context['patterns_by_type']}")
    
    # Extract components
    output_dir = args.output or args.file.parent / f"{args.file.name}_zero_brain"
    extracted = extractor.extract_components(data, output_dir, args.confidence)
    
    print(f"\n✅ Extracted {len(extracted)} components to {output_dir}")
    
    # Generate report
    if args.report:
        report = extractor.generate_report()
        report_path = output_dir / "zero_brain_report.json"
        import json
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"📄 Report saved to: {report_path}")
    
    return 0


if __name__ == "__main__":
    import sys
    import time
    sys.exit(main())
