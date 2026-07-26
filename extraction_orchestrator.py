#!/usr/bin/env python3
"""
Vemex + Blob Extractor Merged Firmware Extraction System
=========================================================

Merges Vemex's pattern learning architecture with Vector35/blob_extractor's
unblob-based extraction to identify and extract iOS firmware components from
unknown binary containers like the PFILE format.

Architecture:
  1. BlobExtractor: Uses unblob to identify and extract known formats
  2. VemexPatternMatcher: Uses Vemex-inspired token attention to find firmware patterns
  3. SpatialGraph: Maps firmware component relationships
  4. TrainingLoop: Learns from successful/failed extractions
  5. Orchestrator: Coordinates all components
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from binary_consciousness_engine import (
    BinaryTokenAttentionGraph,
    FirmwareSpatialGraph,
    HashPipeline,
    load_formula_table,
    PatternMatch,
)


class BlobExtractor:
    """Wrapper around unblob for format detection and extraction."""

    def __init__(self, unblob_path: str = "/tmp/blob_venv/bin/unblob"):
        self.unblob_path = Path(unblob_path)
        if not self.unblob_path.exists():
            raise FileNotFoundError(f"unblob not found at {unblob_path}")
        self._check_dependencies()

    def _check_dependencies(self):
        """Check unblob external dependencies."""
        result = subprocess.run(
            [str(self.unblob_path), "--show-external-dependencies"],
            capture_output=True, text=True
        )
        self.dependencies = {}
        for line in result.stdout.splitlines():
            if "✓" in line or "✗" in line:
                parts = line.strip().split()
                if len(parts) >= 2:
                    tool = parts[0]
                    status = "✓" in line
                    self.dependencies[tool] = status

    def scan_file(self, filepath: Path) -> Dict:
        """Scan a file and identify embedded formats."""
        out_dir = filepath.parent / f"{filepath.name}_unblob_scan"
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [str(self.unblob_path), "-e", str(out_dir), "-d", "3", str(filepath)],
            capture_output=True, text=True, timeout=600
        )
        
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "output_dir": str(out_dir),
            "files": self._list_extracted(out_dir),
        }

    def extract_file(self, filepath: Path, out_dir: Path) -> List[Dict]:
        """Extract all embedded files from a blob."""
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [str(self.unblob_path), "-e", str(out_dir), "-d", "3", "-f", str(filepath)],
            capture_output=True, text=True, timeout=600
        )
        
        return self._list_extracted(out_dir)

    def _list_extracted(self, out_dir: Path) -> List[Dict]:
        """List extracted files with metadata."""
        files = []
        if not out_dir.exists():
            return files
        for f in out_dir.rglob("*"):
            if f.is_file():
                files.append({
                    "path": str(f),
                    "size": f.stat().st_size,
                    "name": f.name,
                })
        return files


class VemexPatternMatcher:
    """Vemex-inspired pattern matching for firmware binary data."""

    def __init__(self, formula_table_path: Optional[Path] = None):
        if formula_table_path is None:
            formula_table_path = Path(__file__).parent / "firmware_formula_table.json"
        table = load_formula_table(formula_table_path)
        self.token_graph = BinaryTokenAttentionGraph(table)
        self.spatial_graph = FirmwareSpatialGraph(table)
        self.hash_pipeline = HashPipeline()
        self.learning_history: List[Dict] = []

    def scan_and_match(self, data: bytes, min_confidence: float = 0.5) -> List[PatternMatch]:
        """Scan binary data for firmware patterns."""
        return self.token_graph.scan_data(data, min_confidence)

    def get_pattern_chain(self, match: PatternMatch) -> List[str]:
        """Get related patterns for a matched firmware component."""
        neighbors = self.spatial_graph.find_similar(match.token_id, top_k=5)
        return [n[0] for n in neighbors]

    def record_extraction(self, pattern_id: str, success: bool, context: Dict):
        """Record extraction result for learning (Vemex reinforcement)."""
        score_delta = 0.08 if success else -0.05
        self.learning_history.append({
            "pattern_id": pattern_id,
            "success": success,
            "score_delta": score_delta,
            "context": context,
            "timestamp": time.time(),
        })

    def get_learning_stats(self) -> Dict:
        """Get learning statistics."""
        if not self.learning_history:
            return {"total": 0, "success_rate": 0.0}
        
        successes = sum(1 for h in self.learning_history if h["success"])
        return {
            "total": len(self.learning_history),
            "successes": successes,
            "failures": len(self.learning_history) - successes,
            "success_rate": successes / len(self.learning_history),
        }


class FirmwareExtractionOrchestrator:
    """Main orchestrator combining blob_extractor and Vemex pattern matching."""

    def __init__(self, formula_table_path: Optional[Path] = None):
        if formula_table_path is None:
            formula_table_path = Path(__file__).parent / "firmware_formula_table.json"
        self.blob_extractor = BlobExtractor()
        self.vemex = VemexPatternMatcher(formula_table_path)
        self.extraction_results: List[Dict] = []

    def analyze_file(self, filepath: Path, out_dir: Path) -> Dict:
        """Full analysis pipeline: unblob scan + Vemex pattern matching."""
        print(f"[+] Analyzing: {filepath.name}")
        
        # Step 1: Unblob scan
        print("[1] Running unblob scan...")
        scan_result = self.blob_extractor.scan_file(filepath)
        
        # Step 2: Load extracted data for Vemex analysis
        print("[2] Running Vemex pattern matching...")
        extracted_files = scan_result.get("files", [])
        
        # Read the original file for pattern scanning
        data = filepath.read_bytes()
        matches = self.vemex.scan_and_match(data)
        
        # Step 3: Correlate unblob results with Vemex patterns
        print("[3] Correlating extraction results...")
        correlations = self._correlate_results(scan_result, matches, data)
        
        result = {
            "file": str(filepath),
            "scan": scan_result,
            "vemex_matches": [
                {
                    "token_id": m.token_id,
                    "offset": m.offset,
                    "length": m.length,
                    "confidence": m.confidence,
                    "description": m.context.get("description", ""),
                    "category": m.context.get("category", ""),
                    "entropy": m.context.get("entropy", 0.0),
                }
                for m in matches
            ],
            "correlations": correlations,
            "learning_stats": self.vemex.get_learning_stats(),
        }
        
        self.extraction_results.append(result)
        return result

    def _correlate_results(self, scan_result: Dict, matches: List[PatternMatch], data: bytes) -> List[Dict]:
        """Correlate unblob extraction with Vemex pattern matches."""
        correlations = []
        extracted_files = scan_result.get("files", [])
        
        for match in matches:
            # Find nearby extracted files
            nearby = []
            for ef in extracted_files:
                try:
                    ef_path = Path(ef["path"])
                    # Extract offset from filename if present (e.g., "26347570-2607813176.lz4_skippable_extract")
                    parts = ef_path.name.split("-")
                    if len(parts) >= 2:
                        try:
                            start = int(parts[0])
                            nearby.append({
                                "file": ef["path"],
                                "start_offset": start,
                                "distance": abs(start - match.offset),
                            })
                        except ValueError:
                            pass
                except Exception:
                    pass
            
            nearby.sort(key=lambda x: x.get("distance", float('inf')))
            
            correlations.append({
                "pattern": match.token_id,
                "offset": match.offset,
                "description": match.context.get("description", ""),
                "nearby_extractions": nearby[:3],
                "suggested_action": self._suggest_action(match, nearby),
            })
        
        return correlations

    def _suggest_action(self, match: PatternMatch, nearby: List[Dict]) -> str:
        """Suggest extraction action based on pattern and context."""
        token_id = match.token_id
        category = match.context.get("category", "")
        entropy = match.context.get("entropy", 0.0)
        
        if "LZ4" in token_id or "lz4" in category.lower():
            return "extract_lz4_chunks"
        elif "ZIP" in token_id or "IPSW" in token_id:
            return "extract_zip_archive"
        elif "DMG" in token_id or "rootfs" in token_id.lower():
            return "extract_dmg_image"
        elif "IMG3" in token_id or "IMG4" in token_id:
            return "extract_img3_img4"
        elif "XAR" in token_id or "kernelcache" in category.lower():
            return "extract_xar_archive"
        elif entropy > 7.5:
            return "likely_compressed_or_encrypted"
        else:
            return "manual_inspection"

    def generate_extraction_plan(self, filepath: Path) -> Dict:
        """Generate a step-by-step extraction plan."""
        analysis = self.analyze_file(filepath, filepath.parent / "vemextract_plan")
        
        plan = {
            "target": str(filepath),
            "steps": [],
            "estimated_components": len(analysis["vemex_matches"]),
            "learning_stats": analysis["learning_stats"],
        }
        
        # Generate ordered extraction steps
        seen_actions = set()
        for corr in analysis["correlations"]:
            action = corr["suggested_action"]
            if action not in seen_actions:
                plan["steps"].append({
                    "action": action,
                    "offset": corr["offset"],
                    "pattern": corr["pattern"],
                    "description": corr["description"],
                    "nearby_files": [n["file"] for n in corr["nearby_extractions"]],
                })
                seen_actions.add(action)
        
        return plan

    def train_on_result(self, pattern_id: str, success: bool, context: Dict):
        """Train Vemex on extraction result."""
        self.vemex.record_extraction(pattern_id, success, context)


def main():
    """Main entry point for Vemex + Blob Extractor merged system."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Vemex + Blob Extractor - Firmware Extraction System"
    )
    parser.add_argument("file", type=Path, help="Firmware blob to analyze")
    parser.add_argument("--formula-table", type=Path, help="Path to firmware formula table")
    parser.add_argument("--out-dir", type=Path, help="Output directory")
    parser.add_argument("--plan-only", action="store_true", help="Generate extraction plan only")
    parser.add_argument("--train", action="store_true", help="Run in training mode")
    
    args = parser.parse_args()
    
    if not args.file.exists():
        print(f"[-] File not found: {args.file}")
        return 1
    
    formula_path = args.formula_table or Path(__file__).parent / "firmware_formula_table.json"
    orchestrator = FirmwareExtractionOrchestrator(formula_path)
    
    if args.plan_only:
        plan = orchestrator.generate_extraction_plan(args.file)
        print(json.dumps(plan, indent=2, default=str))
        return 0
    
    # Full analysis
    out_dir = args.out_dir or args.file.parent / f"{args.file.name}_vemextract"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    result = orchestrator.analyze_file(args.file, out_dir)
    
    # Save results
    result_path = out_dir / "vemex_analysis.json"
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"\n[+] Analysis saved to: {result_path}")
    print(f"[+] Vemex matches: {len(result['vemex_matches'])}")
    print(f"[+] Correlations: {len(result['correlations'])}")
    print(f"[+] Learning stats: {result['learning_stats']}")
    
    # Print extraction plan
    print("\n[+] Extraction Plan:")
    for i, corr in enumerate(result["correlations"][:10], 1):
        print(f"  {i}. {corr['suggested_action']} at 0x{corr['offset']:x} - {corr['description']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
