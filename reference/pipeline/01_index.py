#!/usr/bin/env python3
"""
P4 Pipeline - Step 1: Index competitor files into ChromaDB

This script reads all competitor markdown files, chunks them, generates
embeddings using a local model, and stores them in ChromaDB for retrieval.

Usage:
    cd CompetitiveLandscape-2025
    python _Prompts/p4_pipeline/01_index.py

First run will download the embedding model (~90MB).
Indexing ~300 files takes 5-10 minutes on CPU.
"""

import os
import re
import yaml
import hashlib
from pathlib import Path
from datetime import datetime

import frontmatter
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# Load config
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent.parent  # CompetitiveLandscape-2025

with open(SCRIPT_DIR / "config.yaml") as f:
    CONFIG = yaml.safe_load(f)

# Paths - relative to script location
COMPETITORS_DIR = BASE_DIR / CONFIG["paths"]["competitors_dir"]
ATLASSIAN_DIR = BASE_DIR / CONFIG["paths"]["atlassian_dir"]
CHROMA_DIR = BASE_DIR / CONFIG["paths"]["chroma_db"]


def get_markdown_files():
    """Collect all markdown files to index."""
    files = []

    if COMPETITORS_DIR.exists():
        files.extend(COMPETITORS_DIR.glob("*.md"))

    if ATLASSIAN_DIR.exists():
        files.extend(ATLASSIAN_DIR.glob("*.md"))

    return sorted(files)


def parse_file(filepath: Path) -> dict | None:
    """Parse a markdown file and extract metadata + content."""
    try:
        post = frontmatter.load(filepath)
    except Exception as e:
        print(f"  Warning: Could not parse {filepath.name}: {e}")
        return None

    # Skip scaffolds and skipped files
    status = post.metadata.get("research_status", "")
    if status in ["scaffold", "skipped"]:
        return None

    # Skip files without a name
    if not post.metadata.get("name"):
        return None

    return {
        "filepath": str(filepath),
        "filename": filepath.name,
        "name": post.metadata.get("name", filepath.stem),
        "type": post.metadata.get("type", "competitor"),
        "threat_level": post.metadata.get("threat_level", "Medium"),
        "autonomy_level": post.metadata.get("autonomy_level", "L1"),
        "atlassian_overlap": post.metadata.get("atlassian_overlap", []),
        "content": post.content,
        "metadata": post.metadata
    }


def chunk_content(content: str, chunk_size: int = 500, overlap: int = 50) -> list[dict]:
    """Split content into overlapping chunks by section."""
    chunks = []

    # Split by markdown headers
    sections = re.split(r'\n(?=##? )', content)

    current_section = "Overview"
    for section in sections:
        # Extract section header if present
        header_match = re.match(r'^(##?) (.+)\n', section)
        if header_match:
            current_section = header_match.group(2).strip()

        # Split long sections into smaller chunks
        words = section.split()

        if len(words) <= chunk_size:
            if section.strip():
                chunks.append({
                    "text": section.strip(),
                    "section": current_section
                })
        else:
            # Sliding window chunking
            for i in range(0, len(words), chunk_size - overlap):
                chunk_words = words[i:i + chunk_size]
                if chunk_words:
                    chunks.append({
                        "text": " ".join(chunk_words),
                        "section": current_section
                    })

    return chunks


def generate_chunk_id(filepath: str, chunk_idx: int, text: str) -> str:
    """Generate a unique ID for a chunk."""
    content_hash = hashlib.md5(text.encode()).hexdigest()[:8]
    return f"{Path(filepath).stem}_{chunk_idx}_{content_hash}"


def main():
    print("=" * 60)
    print("P4 Pipeline - Step 1: Indexing")
    print("=" * 60)

    # Check we're in the right directory
    if not COMPETITORS_DIR.exists():
        print(f"\nError: Cannot find {COMPETITORS_DIR}")
        print("Make sure you run this from the CompetitiveLandscape-2025 directory")
        return

    # Load embedding model
    print(f"\nLoading embedding model: {CONFIG['embedding']['model']}")
    print("(First run will download the model, ~90MB)")
    model = SentenceTransformer(CONFIG["embedding"]["model"])

    # Initialize ChromaDB
    print(f"\nInitializing ChromaDB at {CHROMA_DIR}")
    CHROMA_DIR.mkdir(exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False)
    )

    # Delete existing collection if it exists (fresh index)
    try:
        client.delete_collection("competitors")
        print("Deleted existing collection")
    except:
        pass

    collection = client.create_collection(
        name="competitors",
        metadata={"description": "Competitor analysis chunks"}
    )

    # Get all files
    files = get_markdown_files()
    print(f"\nFound {len(files)} markdown files")

    # Process files
    all_chunks = []
    all_embeddings = []
    all_ids = []
    all_metadatas = []

    skipped = 0
    indexed = 0

    for filepath in tqdm(files, desc="Processing files"):
        parsed = parse_file(filepath)
        if not parsed:
            skipped += 1
            continue

        chunks = chunk_content(
            parsed["content"],
            CONFIG["chunking"]["chunk_size"],
            CONFIG["chunking"]["chunk_overlap"]
        )

        if not chunks:
            skipped += 1
            continue

        indexed += 1

        for idx, chunk in enumerate(chunks):
            chunk_id = generate_chunk_id(parsed["filepath"], idx, chunk["text"])

            all_chunks.append(chunk["text"])
            all_ids.append(chunk_id)
            all_metadatas.append({
                "competitor_name": parsed["name"],
                "filename": parsed["filename"],
                "filepath": parsed["filepath"],
                "type": parsed["type"],
                "threat_level": parsed["threat_level"],
                "autonomy_level": parsed["autonomy_level"],
                "atlassian_overlap": ",".join(parsed["atlassian_overlap"]) if parsed["atlassian_overlap"] else "",
                "section": chunk["section"],
                "chunk_index": idx
            })

    print(f"\nIndexed: {indexed} files")
    print(f"Skipped: {skipped} files (scaffolds or invalid)")
    print(f"Total chunks: {len(all_chunks)}")

    # Generate embeddings in batches
    print("\nGenerating embeddings (this may take a few minutes)...")
    batch_size = 64

    for i in tqdm(range(0, len(all_chunks), batch_size), desc="Embedding batches"):
        batch_texts = all_chunks[i:i + batch_size]
        batch_ids = all_ids[i:i + batch_size]
        batch_metadatas = all_metadatas[i:i + batch_size]

        # Generate embeddings
        embeddings = model.encode(batch_texts, show_progress_bar=False)

        # Add to collection
        collection.add(
            ids=batch_ids,
            embeddings=embeddings.tolist(),
            documents=batch_texts,
            metadatas=batch_metadatas
        )

    # Verify
    count = collection.count()
    print(f"\n✅ Indexed {count} chunks into ChromaDB")
    print(f"   Database location: {CHROMA_DIR}")

    # Save index metadata
    index_meta = {
        "indexed_at": datetime.now().isoformat(),
        "files_indexed": indexed,
        "files_skipped": skipped,
        "total_chunks": count,
        "embedding_model": CONFIG["embedding"]["model"]
    }

    with open(CHROMA_DIR / "index_meta.yaml", "w") as f:
        yaml.dump(index_meta, f)

    print(f"\nNext step: python _Prompts/p4_pipeline/02_retrieve.py --theme agentic_shift")


if __name__ == "__main__":
    main()
