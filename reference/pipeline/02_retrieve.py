#!/usr/bin/env python3
"""
P4 Pipeline - Step 2: Retrieve relevant chunks for a theme

This script queries ChromaDB to find the most relevant competitor chunks
for a given synthesis theme, using multiple semantic queries for coverage.

Usage:
    cd CompetitiveLandscape-2025
    python _Prompts/p4_pipeline/02_retrieve.py --theme agentic_shift
    python _Prompts/p4_pipeline/02_retrieve.py --theme all  # All themes
    python _Prompts/p4_pipeline/02_retrieve.py --list       # List themes

Output:
    Creates .retrieved/{theme_name}.json with ranked chunks and metadata
"""

import argparse
import json
import yaml
from pathlib import Path
from collections import defaultdict

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
CHROMA_DIR = BASE_DIR / CONFIG["paths"]["chroma_db"]
OUTPUT_DIR = SCRIPT_DIR / ".retrieved"


def get_collection():
    """Connect to ChromaDB and get the collection."""
    if not CHROMA_DIR.exists():
        print(f"Error: ChromaDB not found at {CHROMA_DIR}")
        print("Run 01_index.py first")
        exit(1)

    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False)
    )

    try:
        return client.get_collection("competitors")
    except:
        print("Error: 'competitors' collection not found")
        print("Run 01_index.py first")
        exit(1)


def retrieve_for_theme(theme_key: str, collection, model) -> dict:
    """Retrieve relevant chunks for a theme using multiple queries."""
    theme = CONFIG["themes"][theme_key]
    queries = theme["queries"]
    top_k = CONFIG["retrieval"]["top_k"]

    print(f"\n{'=' * 60}")
    print(f"Theme: {theme['title']}")
    print(f"{'=' * 60}")
    print(f"Running {len(queries)} queries, retrieving top {top_k} per query")

    # Collect results from all queries
    all_results = defaultdict(lambda: {"score": 0, "count": 0, "chunks": []})

    for query in tqdm(queries, desc="Querying"):
        # Embed the query
        query_embedding = model.encode(query).tolist()

        # Query ChromaDB
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        # Process results
        for i, (doc, meta, dist) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        )):
            competitor = meta["competitor_name"]
            # Convert distance to similarity score (lower distance = higher similarity)
            score = 1 / (1 + dist)

            # Aggregate by competitor
            all_results[competitor]["score"] += score
            all_results[competitor]["count"] += 1
            all_results[competitor]["threat_level"] = meta["threat_level"]
            all_results[competitor]["autonomy_level"] = meta["autonomy_level"]
            all_results[competitor]["atlassian_overlap"] = meta["atlassian_overlap"]
            all_results[competitor]["filepath"] = meta["filepath"]

            # Track individual chunks (avoid duplicates)
            chunk_key = f"{meta['filename']}:{meta['section']}:{meta['chunk_index']}"
            existing_chunks = [c["key"] for c in all_results[competitor]["chunks"]]
            if chunk_key not in existing_chunks:
                all_results[competitor]["chunks"].append({
                    "key": chunk_key,
                    "section": meta["section"],
                    "text": doc,
                    "score": score,
                    "query": query
                })

    # Sort competitors by aggregate score
    ranked = sorted(
        all_results.items(),
        key=lambda x: x[1]["score"],
        reverse=True
    )

    # Build output
    output = {
        "theme": theme_key,
        "title": theme["title"],
        "queries": queries,
        "total_competitors": len(ranked),
        "competitors": []
    }

    for competitor, data in ranked:
        # Sort chunks by score within competitor
        sorted_chunks = sorted(data["chunks"], key=lambda x: x["score"], reverse=True)

        output["competitors"].append({
            "name": competitor,
            "aggregate_score": round(data["score"], 4),
            "query_hits": data["count"],
            "threat_level": data["threat_level"],
            "autonomy_level": data["autonomy_level"],
            "atlassian_overlap": data["atlassian_overlap"].split(",") if data["atlassian_overlap"] else [],
            "filepath": data["filepath"],
            "top_chunks": sorted_chunks[:5]  # Top 5 chunks per competitor
        })

    # Summary stats
    print(f"\nRetrieved {len(ranked)} competitors")
    print(f"Top 10 by relevance:")
    for i, comp in enumerate(output["competitors"][:10]):
        print(f"  {i+1}. {comp['name']} (score: {comp['aggregate_score']:.3f}, hits: {comp['query_hits']})")

    return output


def save_results(theme_key: str, results: dict):
    """Save retrieval results to JSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{theme_key}.json"

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ Saved to {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Retrieve relevant chunks for synthesis themes")
    parser.add_argument("--theme", type=str, help="Theme key (e.g., 'agentic_shift') or 'all'")
    parser.add_argument("--list", action="store_true", help="List available themes")

    args = parser.parse_args()

    # List themes
    if args.list:
        print("Available themes:")
        for key, theme in CONFIG["themes"].items():
            print(f"  {key}: {theme['title']}")
        return

    if not args.theme:
        parser.print_help()
        return

    # Load model and collection
    print(f"Loading embedding model: {CONFIG['embedding']['model']}")
    model = SentenceTransformer(CONFIG["embedding"]["model"])

    collection = get_collection()
    print(f"Connected to ChromaDB ({collection.count()} chunks indexed)")

    # Process theme(s)
    if args.theme == "all":
        themes = list(CONFIG["themes"].keys())
    else:
        if args.theme not in CONFIG["themes"]:
            print(f"Error: Unknown theme '{args.theme}'")
            print("Use --list to see available themes")
            return
        themes = [args.theme]

    for theme_key in themes:
        results = retrieve_for_theme(theme_key, collection, model)
        output_path = save_results(theme_key, results)

    print(f"\nNext step: python _Prompts/p4_pipeline/03_synthesize.py --theme {themes[0]}")


if __name__ == "__main__":
    main()
