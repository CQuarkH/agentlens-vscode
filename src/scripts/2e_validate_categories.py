#!/usr/bin/env python3
import json
import argparse
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent

def extract_frontmatter_categories(md_path: Path):
    """Parses precisely the array of categories injected during Phase 1 Enrichment."""
    text = md_path.read_text(encoding='utf-8')
    lines = text.splitlines()
    categories = []
    
    if len(lines) > 0 and lines[0] == '---':
        try:
            end_index = lines.index('---', 1)
            frontmatter_lines = lines[1:end_index]
            for line in frontmatter_lines:
                if line.startswith('categories:'):
                    cat_str = line.replace('categories:', '').strip()
                    if cat_str.startswith('[') and cat_str.endswith(']'):
                        try:
                            categories = json.loads(cat_str)
                        except:
                            pass
            return categories
        except ValueError:
            pass
    return categories

def main():
    parser = argparse.ArgumentParser(description="Validate generated JSON AST Categories against Ground-Truth in Markdown.")
    args = parser.parse_args()

    root_dir = get_project_root()
    trees_dir = root_dir / "dataset" / "json_trees"
    enriched_dir = root_dir / "dataset" / "enriched_agents"
    
    if not trees_dir.exists() or not enriched_dir.exists():
        logger.error(f"Error: Dataset directories missing.")
        return

    variants = ['llm', 'parser', 'llm_api', 'llm_forced_output']
    overall_stats = {}
    
    print("=" * 80)
    print(" 🧠 SEMANTIC CATEGORY HALLUCINATION & COMPLIANCE REPORT ")
    print("=" * 80)

    for variant in variants:
        variant_dir = trees_dir / variant
        if not variant_dir.exists():
            continue
            
        json_files = list(variant_dir.glob("*.json"))
        total_files = len(json_files)
        
        if total_files == 0:
            continue
            
        print(f"\nEvaluating Variant: [{variant.upper()}] ({total_files} files found)")
        print("-" * 80)
        
        total_hallucinations = 0
        total_missing_but_expected = 0
        total_ast_categories = 0
        files_with_hallucinations = 0
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                md_source = data.get("projectInfo", {}).get("agentsMdSource")
                if not md_source:
                    print(f"  [X] Skipping {json_file.name}: Missing agentsMdSource pointer.")
                    continue
                    
                md_path = enriched_dir / md_source
                if not md_path.exists():
                    print(f"  [X] Skipping {json_file.name}: Original markdown file missing.")
                    continue
                    
                # The "Golden Ground Truth" initialized in Phase 1
                expected_categories = set(extract_frontmatter_categories(md_path))
                
                # The nodes extracted/invented by the AI in Phase 2
                ast_categories = set()
                for cat_node in data.get("rootNode", {}).get("children", []):
                    label = cat_node.get("label")
                    if label:
                        ast_categories.add(label)
                    
                hallucinated = ast_categories - expected_categories
                missing = expected_categories - ast_categories  # Not necessarily bad (could be 0 rules for it)
                
                total_ast_categories += len(ast_categories)
                total_hallucinations += len(hallucinated)
                total_missing_but_expected += len(missing)
                
                if hallucinated:
                    files_with_hallucinations += 1
                    print(f"  [WARNING] {json_file.name}")
                    print(f"      Ground Truth: {list(expected_categories)}")
                    print(f"      Invented by Agent: {list(hallucinated)}")
                
            except Exception as e:
                logger.error(f"Error processing {json_file.name}: {e}")
                
        # Calculate stats
        hallucination_rate = (total_hallucinations / total_ast_categories * 100) if total_ast_categories > 0 else 0
        
        print(f"Summary for {variant.upper()}:")
        print(f"  - Files affected by hallucinations: {files_with_hallucinations}/{total_files}")
        print(f"  - Total categories generated in ASTs: {total_ast_categories}")
        print(f"  - Total hallucinated categories injected: {total_hallucinations}")
        print(f"  - Global Hallucination Rate: {hallucination_rate:.1f}%")
        
        overall_stats[variant] = {
            'total_files': total_files,
            'files_hallucinated': files_with_hallucinations,
            'hallucination_rate': hallucination_rate
        }

    print("\n" + "=" * 80)
    print(" FINAL HALLUCINATION METRICS ")
    print("=" * 80)
    for v, stats in overall_stats.items():
        print(f"{v.ljust(10).upper()} | Affected Files: {str(stats['files_hallucinated']).rjust(2)}/{str(stats['total_files']).ljust(2)} | Hallucinated Cat Rate: {stats['hallucination_rate']:.1f}%")

if __name__ == "__main__":
    main()
