#!/usr/bin/env python3
import csv
import json
import logging
from pathlib import Path
from typing import List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def get_project_root() -> Path:
    """Returns the absolute path to the project root directory."""
    return Path(__file__).resolve().parent.parent.parent

def main() -> None:
    logger.info("Starting Phase 1: Data Ingestion and Enrichment")
    
    root_dir = get_project_root()
    dataset_dir = root_dir / "dataset"
    raw_csv_path = dataset_dir / "raw-dataset.csv"
    cache_dir = dataset_dir / "agents_cache"
    output_dir = dataset_dir / "enriched_agents"
    
    # Validation
    if not raw_csv_path.exists():
        raw_csv_path = dataset_dir / "raw_dataset.csv"
        if not raw_csv_path.exists():
            logger.error(f"Input CSV not found at {raw_csv_path}")
            return
            
    if not cache_dir.exists():
        logger.error(f"Cache directory not found at {cache_dir}")
        return
        
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Targeting output directory: {output_dir}")
    
    enriched_count = 0
    skipped_count = 0
    
    try:
        with open(raw_csv_path, mode='r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                owner = row.get('repository_owner', '').strip()
                repo = row.get('repository_name', '').strip()
                
                if not owner or not repo:
                    continue
                    
                repo_full_name = f"{owner}/{repo}"
                cache_filename = f"{owner}_{repo}.md"
                cache_file_path = cache_dir / cache_filename
                
                if not cache_file_path.exists():
                    logger.warning(f"File {cache_filename} not found in cache. Skipping...")
                    skipped_count += 1
                    continue
                    
                # Extract categories (columns starting with 'Label')
                categories: List[str] = []
                for key, value in row.items():
                    if key and key.startswith('Label'):
                        val = value.strip()
                        if val:
                            categories.append(val)
                            
                # Read raw markdown
                try:
                    content = cache_file_path.read_text(encoding='utf-8')
                except Exception as e:
                    logger.error(f"Failed to read {cache_file_path}: {e}")
                    skipped_count += 1
                    continue
                    
                # Build YAML frontmatter using JSON to format lists nicely
                categories_json = json.dumps(categories, ensure_ascii=False)
                
                frontmatter = (
                    "---\n"
                    f"repo: \"{repo_full_name}\"\n"
                    f"categories: {categories_json}\n"
                    "---\n"
                )
                
                new_content = frontmatter + content
                
                # Save to output
                output_file_path = output_dir / cache_filename
                try:
                    output_file_path.write_text(new_content, encoding='utf-8')
                    logger.info(f"Enriched: {repo_full_name} -> {cache_filename}")
                    enriched_count += 1
                except Exception as e:
                    logger.error(f"Failed to write enriched file {output_file_path}: {e}")
                    skipped_count += 1
                    
    except Exception as e:
        logger.error(f"An error occurred during processing: {e}")
        return
        
    logger.info("Phase 1 completed successfully.")
    logger.info(f"Summary: {enriched_count} files enriched, {skipped_count} skipped.")

if __name__ == "__main__":
    main()
