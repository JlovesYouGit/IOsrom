#!/usr/bin/env python3
"""
Celestial Router for Firmware Extraction
==========================================

Adapted from Vemex's SpatialConstructionRelay and SpectrumMaterializationEngine.

Treats firmware binary blobs as celestial fields where:
- Binary regions are "celestial bodies" (firmware components)
- Data flows between them are "light transmission paths"
- Offsets are "spatial coordinates"
- Compression types are "frequency bands"

The router finds harmonic nodes along light paths and extracts
firmware components by traversing these celestial routes.
"""

import hashlib
import math
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class CelestialNode:
    """A potential firmware component in the binary field."""
    offset: int
    size: int
    node_type: str
    confidence: float
    entropy: float
    signature: bytes
    metadata: Dict = field(default_factory=dict)


@dataclass
class LightPath:
    """A data flow path between celestial nodes."""
    source_offset: int
    target_offset: int
    path_type: str
    bandwidth: float
    harmonic_nodes: List[Dict]
    signal_preserved: bool = True


class CelestialRouter:
    """
    Routes through firmware binary data using celestial light transmission paths.
    Finds harmonic nodes (firmware components) and extracts them by traversing
    the light paths between them.
    """

    def __init__(self, base_frequency: float = 432.0):
        self.base_frequency = base_frequency
        self.routing_board: Dict[str, Any] = {}
        self.celestial_nodes: List[CelestialNode] = []
        self.light_paths: List[LightPath] = []
        self.extracted_components: List[Dict] = []
        
        # MSFB constants from Vemex
        self.msfb_M = 4e6
        self.msfb_S = 1e15
        self.msfb_F = 1e-5
        self.msfb_B = 1e10
        self.msfb_base = self.msfb_M * self.msfb_S * self.msfb_F * self.msfb_B

    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of data."""
        if not data:
            return 0.0
        from collections import Counter
        counts = Counter(data)
        total = len(data)
        return -sum((c / total) * math.log2(c / total) for c in counts.values() if c > 0)

    def _detect_compression(self, data: bytes, offset: int) -> Optional[str]:
        """Detect compression type at offset."""
        if offset + 4 > len(data):
            return None
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
        return None

    def scan_celestial_field(self, data: bytes, max_scan: int = 500 * 1024 * 1024) -> List[CelestialNode]:
        """
        Scan binary data for celestial nodes (potential firmware components).
        Focuses on finding the structure of the PFILE container.
        """
        print("☀️ SCANNING CELESTIAL FIELD FOR NODES")
        
        nodes = []
        scan_limit = min(len(data), max_scan)
        
        # Known firmware signatures
        signatures = {
            b'Img3': 'IMG3',
            b'IMG3': 'IMG3',
            b'IM4P': 'IMG4',
            b'IM4M': 'IMG4',
            b'bdav': 'Baseband',
            b'mkps': 'Keys',
            b'sepo': 'SEP',
            b'krnl': 'Kernel',
            b'iboot': 'iBoot',
            b'iBoot': 'iBoot',
            b'ILLB': 'LLB',
            b'dtre': 'DeviceTree',
            b'OS#': 'iOS',
            b'xar!': 'XAR',
            b'PK\x03\x04': 'ZIP',
            b'PK\x05\x06': 'ZIP_EOCD',
            b'PK\x01\x02': 'ZIP_CD',
        }
        
        # Scan for signatures
        for sig, sig_type in signatures.items():
            pos = 0
            while True:
                pos = data.find(sig, pos)
                if pos == -1 or pos >= scan_limit:
                    break
                context_start = max(0, pos - 16)
                context_end = min(scan_limit, pos + len(sig) + 64)
                context = data[context_start:context_end]
                entropy = self._calculate_entropy(context)
                
                nodes.append(CelestialNode(
                    offset=pos,
                    size=len(sig),
                    node_type=sig_type,
                    confidence=0.9,
                    entropy=entropy,
                    signature=sig,
                    metadata={'context_entropy': entropy}
                ))
                pos += len(sig)
        
        # Scan for compression markers (light paths)
        compression_markers = []
        compression_sigs = [
            (b'\x28\xb5\x2f\xfd', 'zstd'),
            (b'\x04\x22\x4d\x18', 'lz4'),
            (b'\x02\x21\x4c\x18', 'lz4_skippable'),
            (b'\x03\x21\x4c\x18', 'lz4_skippable'),
            (b'\x04\x21\x4c\x18', 'lz4_skippable'),
            (b'\x05\x21\x4c\x18', 'lz4_skippable'),
            (b'\x1f\x8b', 'gzip'),
        ]
        
        for sig, comp_type in compression_sigs:
            pos = 0
            while True:
                pos = data.find(sig, pos)
                if pos == -1 or pos >= scan_limit:
                    break
                compression_markers.append((pos, comp_type))
                nodes.append(CelestialNode(
                    offset=pos,
                    size=len(sig),
                    node_type=f"COMP_{comp_type}",
                    confidence=0.95,
                    entropy=self._calculate_entropy(data[pos:pos+64]),
                    signature=data[pos:pos+len(sig)],
                    metadata={'compression': comp_type}
                ))
                pos += len(sig)
        
        # Scan for entropy transitions (potential firmware boundaries)
        prev_entropy = 0.0
        boundary_candidates = []
        for i in range(0, scan_limit, 4096):
            chunk = data[i:i + 4096]
            if len(chunk) < 4096:
                break
            entropy = self._calculate_entropy(chunk)
            
            # Look for significant entropy transitions
            if abs(entropy - prev_entropy) > 1.0:
                boundary_candidates.append(i)
            prev_entropy = entropy
        
        # Add entropy boundary nodes
        for boundary in boundary_candidates[:50]:  # Limit to top 50
            nodes.append(CelestialNode(
                offset=boundary,
                size=0,
                node_type="ENTROPY_BOUNDARY",
                confidence=0.3,
                entropy=prev_entropy,
                signature=b'',
                metadata={'transition': True}
            ))
        
        # Add compression markers as light path endpoints
        for offset, comp_type in compression_markers:
            nodes.append(CelestialNode(
                offset=offset,
                size=0,
                node_type=f"LIGHT_PATH_{comp_type}",
                confidence=0.9,
                entropy=0.0,
                signature=data[offset:offset+4],
                metadata={'compression': comp_type, 'is_path': True}
            ))
        
        # Remove duplicates and sort by offset
        seen = set()
        unique_nodes = []
        for node in nodes:
            key = (node.offset, node.node_type)
            if key not in seen:
                seen.add(key)
                unique_nodes.append(node)
        
        unique_nodes.sort(key=lambda n: n.offset)
        self.celestial_nodes = unique_nodes
        
        print(f"   Found {len(unique_nodes)} celestial nodes")
        print(f"   Compression markers: {len(compression_markers)}")
        return unique_nodes

    def establish_celestial_routes(self, data: bytes, max_paths: int = 500) -> List[LightPath]:
        """
        Establish routes through celestial light transmission paths.
        Find and traverse data through light paths, treating nodes as connected.
        """
        print("🔗 ESTABLISHING CELESTIAL ROUTES")
        
        if not self.celestial_nodes:
            self.scan_celestial_field(data)
        
        paths = []
        nodes = self.celestial_nodes
        
        # Limit nodes to top 50 by confidence
        nodes = sorted(nodes, key=lambda n: n.confidence, reverse=True)[:50]
        
        # Connect nodes based on offset relationships and data flow
        for i, source in enumerate(nodes):
            for j, target in enumerate(nodes):
                if i == j:
                    continue
                
                # Calculate light path between nodes
                distance = target.offset - source.offset
                if distance <= 0 or distance > 50 * 1024 * 1024:  # Max 50MB path
                    continue
                
                # Get data between nodes (limit to 1MB for speed)
                between_start = source.offset
                between_end = min(target.offset, between_start + 1024 * 1024)
                between = data[between_start:between_end]
                
                # Calculate bandwidth based on data characteristics
                bandwidth = self._calculate_path_bandwidth(between, distance)
                
                # Find harmonic nodes along the path (limit to 4)
                harmonic_nodes = self._find_harmonic_nodes(between, distance, source.offset)[:4]
                
                paths.append(LightPath(
                    source_offset=source.offset,
                    target_offset=target.offset,
                    path_type=f"{source.node_type}_to_{target.node_type}",
                    bandwidth=bandwidth,
                    harmonic_nodes=harmonic_nodes
                ))
                
                if len(paths) >= max_paths:
                    break
            
            if len(paths) >= max_paths:
                break
        
        self.light_paths = paths
        print(f"   Established {len(paths)} light paths")
        return paths

    def _calculate_path_bandwidth(self, path_data: bytes, distance: int) -> float:
        """Calculate bandwidth of a light path based on data characteristics."""
        if not path_data:
            return 0.0
        
        entropy = self._calculate_entropy(path_data)
        
        # Higher entropy = more compressed = higher bandwidth
        if entropy > 7.5:
            return self.msfb_base * 0.8
        elif entropy > 3.0:
            return self.msfb_base * 0.5
        else:
            return self.msfb_base * 0.2

    def _find_harmonic_nodes(self, path_data: bytes, distance: int, base_offset: int) -> List[Dict]:
        """Find harmonic nodes along a light path."""
        nodes = []
        num_harmonics = min(8, max(1, distance // (1024 * 1024)))
        
        for i in range(num_harmonics):
            pos = int(distance * (i / num_harmonics))
            if pos < len(path_data):
                chunk = path_data[pos:pos + 1024]
                entropy = self._calculate_entropy(chunk)
                nodes.append({
                    'position': base_offset + pos,
                    'entropy': entropy,
                    'resonance_phase': (i / num_harmonics) * 2 * math.pi,
                    'frequency_shift': self.base_frequency * (1 + math.sin(pos * 0.001) * 0.1)
                })
        
        return nodes

    def retrace_light_routes(self, data: bytes, source_type: str = "HEADER", target_type: str = "ROOTFS") -> List[Dict]:
        """
        Retrace routes through light paths.
        Finds the optimal path from source to target through the binary.
        """
        print(f"🔄 RETRACING LIGHT ROUTES: {source_type} → {target_type}")
        
        if not self.light_paths:
            self.establish_celestial_routes(data)
        
        # Find source and target nodes
        source_nodes = [n for n in self.celestial_nodes if source_type in n.node_type.upper()]
        target_nodes = [n for n in self.celestial_nodes if target_type in n.node_type.upper()]
        
        if not source_nodes:
            source_nodes = self.celestial_nodes[:1]
        if not target_nodes:
            target_nodes = self.celestial_nodes[-1:] if self.celestial_nodes else []
        
        if not source_nodes or not target_nodes:
            print("   ⚠️ No valid source/target nodes found")
            return []
        
        routes = []
        for source in source_nodes:
            for target in target_nodes:
                path = next((p for p in self.light_paths 
                           if p.source_offset == source.offset and p.target_offset == target.offset), None)
                
                if path:
                    route = {
                        'route_id': hashlib.sha256(
                            f"{source.offset}:{target.offset}:{self.msfb_base}".encode()
                        ).hexdigest()[:16],
                        'source': source.offset,
                        'target': target.offset,
                        'distance': target.offset - source.offset,
                        'bandwidth': path.bandwidth,
                        'harmonic_count': len(path.harmonic_nodes),
                        'signal_preserved': path.signal_preserved,
                        'extraction_strategy': self._determine_extraction_strategy(path)
                    }
                    routes.append(route)
        
        print(f"   Found {len(routes)} valid routes")
        return routes

    def _determine_extraction_strategy(self, path: LightPath) -> str:
        """Determine the best extraction strategy for a light path."""
        bandwidth = path.bandwidth
        
        if bandwidth > self.msfb_base * 0.7:
            return "direct_extract"
        elif bandwidth > self.msfb_base * 0.4:
            return "decompress_then_extract"
        else:
            return "raw_copy"

    def traverse_and_extract(self, data: bytes, output_dir: Path) -> List[Dict]:
        """
        Traverse light paths and extract firmware components.
        This is the main extraction method.
        """
        print("🚀 TRAVERSING LIGHT PATHS AND EXTRACTING COMPONENTS")
        
        if not self.celestial_nodes:
            self.scan_celestial_field(data)
        if not self.light_paths:
            self.establish_celestial_routes(data)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        extracted = []
        
        # Extract each celestial node that looks like firmware
        for node in self.celestial_nodes:
            if node.node_type in ('ENTROPY_BOUNDARY', 'LIGHT_PATH_LZ4', 'LIGHT_PATH_ZSTD', 'LIGHT_PATH_GZIP'):
                continue
            
            if node.size < 1024 and node.node_type not in ('IMG3', 'IMG4', 'ZIP', 'ZIP_EOCD', 'ZIP_CD'):
                continue
            
            # Determine extraction strategy based on node type
            strategy = self._get_extraction_strategy(node)
            component_data = self._extract_node(data, node, strategy)
            
            if component_data and len(component_data) > 1024:
                # Save extracted component
                ext = self._get_extension(node.node_type)
                filename = f"component_{node.offset:010x}_{node.node_type}{ext}"
                output_path = output_dir / filename
                
                with open(output_path, 'wb') as f:
                    f.write(component_data)
                
                extracted.append({
                    'path': str(output_path),
                    'offset': node.offset,
                    'size': len(component_data),
                    'type': node.node_type,
                    'confidence': node.confidence,
                    'strategy': strategy
                })
                
                print(f"   ✅ Extracted {filename} ({len(component_data):,} bytes)")
        
        self.extracted_components = extracted
        return extracted

    def _get_extraction_strategy(self, node: CelestialNode) -> str:
        """Determine extraction strategy for a node."""
        if node.node_type in ('IMG3', 'IMG4'):
            return 'raw_copy'
        elif node.node_type in ('XAR', 'kernelcache_candidate'):
            return 'raw_copy'
        elif node.entropy > 7.5:
            return 'compressed_chunk'
        else:
            return 'raw_copy'

    def _extract_node(self, data: bytes, node: CelestialNode, strategy: str) -> Optional[bytes]:
        """Extract a celestial node from binary data."""
        try:
            if strategy == 'raw_copy':
                end = min(node.offset + node.size, len(data))
                return data[node.offset:end]
            
            elif strategy == 'compressed_chunk':
                end = min(node.offset + node.size, len(data))
                return data[node.offset:end]
            
            else:
                end = min(node.offset + node.size, len(data))
                return data[node.offset:end]
        except Exception as e:
            print(f"   ⚠️ Failed to extract node at 0x{node.offset:x}: {e}")
            return None

    def _get_extension(self, node_type: str) -> str:
        """Get file extension for a node type."""
        ext_map = {
            'IMG3': '.img3',
            'IMG4': '.img4',
            'XAR': '.xar',
            'kernelcache': '.kc',
            'ramdisk': '.dmg',
            'rootfs': '.dmg',
            'DeviceTree': '.dtre',
            'iBSS': '.iBSS',
            'iBEC': '.iBEC',
            'LLB': '.llb',
            'iBoot': '.iBoot',
            'SEP': '.sep',
            'Baseband': '.baseband',
            'ZIP': '.zip',
            'iOS': '.ipsw',
        }
        return ext_map.get(node_type, '.bin')

    def generate_extraction_report(self) -> Dict:
        """Generate a report of the celestial routing and extraction."""
        return {
            'total_nodes': len(self.celestial_nodes),
            'total_paths': len(self.light_paths),
            'total_extracted': len(self.extracted_components),
            'nodes_by_type': self._count_by_type(),
            'extracted_components': self.extracted_components,
            'routing_board': self.routing_board
        }

    def _count_by_type(self) -> Dict[str, int]:
        """Count nodes by type."""
        counts = {}
        for node in self.celestial_nodes:
            counts[node.node_type] = counts.get(node.node_type, 0) + 1
        return counts


def main():
    """Main entry point for celestial router."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Celestial Router - Firmware Extraction")
    parser.add_argument("file", type=Path, help="Firmware blob to analyze")
    parser.add_argument("--output", "-o", type=Path, help="Output directory")
    parser.add_argument("--scan-only", action="store_true", help="Only scan for nodes")
    parser.add_argument("--report", action="store_true", help="Generate extraction report")
    parser.add_argument("--max-scan", type=int, default=500, help="Max MB to scan")
    
    args = parser.parse_args()
    
    if not args.file.exists():
        print(f"[-] File not found: {args.file}")
        return 1
    
    data = args.file.read_bytes()
    print(f"[+] Loaded {len(data):,} bytes from {args.file}")
    
    router = CelestialRouter()
    
    if args.scan_only:
        nodes = router.scan_celestial_field(data, max_scan=args.max_scan * 1024 * 1024)
        print(f"\n[+] Found {len(nodes)} celestial nodes:")
        for node in nodes[:30]:
            print(f"   0x{node.offset:010x}: {node.node_type} ({node.size} bytes, entropy={node.entropy:.2f})")
        return 0
    
    # Full extraction
    output_dir = args.output or args.file.parent / f"{args.file.name}_celestial_extract"
    extracted = router.traverse_and_extract(data, output_dir)
    
    print(f"\n[+] Extracted {len(extracted)} components to {output_dir}")
    
    if args.report:
        report = router.generate_extraction_report()
        report_path = output_dir / "celestial_report.json"
        import json
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"[+] Report saved to: {report_path}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
