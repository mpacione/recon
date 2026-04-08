#!/usr/bin/env python3
"""
P4 Pipeline - Step 0: Discover Emergent Themes

This script clusters all competitor chunks to surface themes you might not
have anticipated. Run this BEFORE guided retrieval to discover patterns.

Usage:
    cd CompetitiveLandscape-2025
    python _Prompts/p4_pipeline/00_discover.py
    python _Prompts/p4_pipeline/00_discover.py --clusters 10  # More granular
    python _Prompts/p4_pipeline/00_discover.py --label        # Use Claude to label clusters

Output:
    - Prints cluster summaries with representative chunks
    - Optionally saves to .discovered/clusters.json
    - Can generate suggested theme definitions for config.yaml

Requires: Run 01_index.py first to build the vector database.
"""

import argparse
import json
import yaml
import os
from pathlib import Path
from collections import defaultdict, Counter

import numpy as np
import chromadb
from chromadb.config import Settings
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE
from sentence_transformers import SentenceTransformer

# Optional: Claude for auto-labeling
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

# Load config
SCRIPT_DIR = Path(__file__).parent.resolve()
BASE_DIR = SCRIPT_DIR.parent.parent  # CompetitiveLandscape-2025

with open(SCRIPT_DIR / "config.yaml") as f:
    CONFIG = yaml.safe_load(f)

# Paths - relative to script location
CHROMA_DIR = BASE_DIR / CONFIG["paths"]["chroma_db"]
OUTPUT_DIR = BASE_DIR / "_Prompts/p4_pipeline/.discovered"


def get_all_embeddings():
    """Extract all embeddings and metadata from ChromaDB."""
    if not CHROMA_DIR.exists():
        print(f"Error: ChromaDB not found at {CHROMA_DIR}")
        print("Run 01_index.py first")
        exit(1)

    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False)
    )

    try:
        collection = client.get_collection("competitors")
    except:
        print("Error: 'competitors' collection not found")
        print("Run 01_index.py first")
        exit(1)

    # Get all data
    results = collection.get(
        include=["embeddings", "documents", "metadatas"]
    )

    print(f"Loaded {len(results['ids'])} chunks from ChromaDB")

    return {
        "ids": results["ids"],
        "embeddings": np.array(results["embeddings"]),
        "documents": results["documents"],
        "metadatas": results["metadatas"]
    }


def cluster_embeddings(embeddings: np.ndarray, n_clusters: int = 8) -> np.ndarray:
    """Cluster embeddings using K-means."""
    print(f"\nClustering into {n_clusters} clusters...")

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)

    # Count per cluster
    counts = Counter(labels)
    print(f"Cluster sizes: {dict(sorted(counts.items()))}")

    return labels, kmeans


def analyze_clusters(data: dict, labels: np.ndarray, kmeans) -> list[dict]:
    """Analyze each cluster to understand its theme."""
    clusters = []

    for cluster_id in range(kmeans.n_clusters):
        # Get indices for this cluster
        indices = np.where(labels == cluster_id)[0]

        # Get documents and metadata for this cluster
        cluster_docs = [data["documents"][i] for i in indices]
        cluster_meta = [data["metadatas"][i] for i in indices]

        # Find chunks closest to cluster center (most representative)
        cluster_embeddings = data["embeddings"][indices]
        center = kmeans.cluster_centers_[cluster_id]
        distances = np.linalg.norm(cluster_embeddings - center, axis=1)
        closest_indices = np.argsort(distances)[:5]  # Top 5 closest to center

        representative_chunks = [cluster_docs[i] for i in closest_indices]

        # Aggregate metadata
        competitors = Counter([m["competitor_name"] for m in cluster_meta])
        sections = Counter([m["section"] for m in cluster_meta])
        threat_levels = Counter([m["threat_level"] for m in cluster_meta])
        autonomy_levels = Counter([m["autonomy_level"] for m in cluster_meta])

        clusters.append({
            "cluster_id": cluster_id,
            "size": len(indices),
            "top_competitors": competitors.most_common(10),
            "top_sections": sections.most_common(5),
            "threat_distribution": dict(threat_levels),
            "autonomy_distribution": dict(autonomy_levels),
            "representative_chunks": representative_chunks,
            "label": None  # Will be filled by auto-labeling
        })

    return clusters


def auto_label_cluster(cluster: dict) -> str:
    """Use Claude to generate a label for a cluster."""
    if not HAS_ANTHROPIC or not os.environ.get("ANTHROPIC_API_KEY"):
        return None

    client = anthropic.Anthropic()

    chunks_text = "\n\n---\n\n".join(cluster["representative_chunks"][:3])
    competitors = ", ".join([c[0] for c in cluster["top_competitors"][:5]])

    prompt = f"""Based on these representative text chunks from a competitive analysis, suggest a short theme label (3-5 words) that captures what this cluster is about.

Competitors in this cluster: {competitors}

Representative chunks:
{chunks_text}

Respond with ONLY the theme label, nothing else. Examples of good labels:
- "Agentic Code Execution"
- "Developer Experience Focus"
- "Enterprise Security Features"
- "CI/CD Pipeline Integration"
- "AI-Assisted Code Review"
"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=50,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text.strip()


def generate_theme_config(cluster: dict) -> dict:
    """Generate a theme config entry from a cluster."""
    label = cluster["label"] or f"Cluster {cluster['cluster_id']}"
    key = label.lower().replace(" ", "_").replace("-", "_")

    # Generate queries from representative chunks (extract key phrases)
    # This is a simple heuristic - Claude labeling does better
    queries = []
    for chunk in cluster["representative_chunks"][:3]:
        # Take first sentence or first 100 chars as a query seed
        first_sentence = chunk.split(".")[0][:100]
        if len(first_sentence) > 20:
            queries.append(first_sentence)

    return {
        "key": key,
        "config": {
            "title": label,
            "output_file": f"_{key.title().replace('_', '')}.md",
            "queries": queries[:5],
            "top_competitors": [c[0] for c in cluster["top_competitors"][:5]]
        }
    }


def print_cluster_report(clusters: list[dict], auto_label: bool = False):
    """Print a human-readable cluster report."""
    print("\n" + "=" * 70)
    print("EMERGENT THEME DISCOVERY REPORT")
    print("=" * 70)

    for cluster in sorted(clusters, key=lambda x: x["size"], reverse=True):
        print(f"\n{'─' * 70}")
        label = cluster["label"] or f"Cluster {cluster['cluster_id']}"
        print(f"📁 {label}")
        print(f"   Size: {cluster['size']} chunks")
        print(f"   Top competitors: {', '.join([c[0] for c in cluster['top_competitors'][:5]])}")
        print(f"   Sections: {', '.join([s[0] for s in cluster['top_sections'][:3]])}")
        print(f"   Threat: {cluster['threat_distribution']}")
        print(f"   Autonomy: {cluster['autonomy_distribution']}")
        print(f"\n   Representative excerpt:")
        excerpt = cluster["representative_chunks"][0][:300].replace("\n", " ")
        print(f"   \"{excerpt}...\"")


def main():
    parser = argparse.ArgumentParser(description="Discover emergent themes via clustering")
    parser.add_argument("--clusters", type=int, default=8, help="Number of clusters (default: 8)")
    parser.add_argument("--label", action="store_true", help="Use Claude to auto-label clusters")
    parser.add_argument("--save", action="store_true", help="Save results to .discovered/")
    parser.add_argument("--suggest-config", action="store_true", help="Generate theme config suggestions")

    args = parser.parse_args()

    # Load data
    data = get_all_embeddings()

    # Cluster
    labels, kmeans = cluster_embeddings(data["embeddings"], args.clusters)

    # Analyze
    clusters = analyze_clusters(data, labels, kmeans)

    # Auto-label if requested
    if args.label:
        if not HAS_ANTHROPIC:
            print("Warning: anthropic package not installed, skipping auto-labeling")
        elif not os.environ.get("ANTHROPIC_API_KEY"):
            print("Warning: ANTHROPIC_API_KEY not set, skipping auto-labeling")
        else:
            print("\nAuto-labeling clusters with Claude...")
            for cluster in clusters:
                cluster["label"] = auto_label_cluster(cluster)
                print(f"  Cluster {cluster['cluster_id']}: {cluster['label']}")

    # Print report
    print_cluster_report(clusters, args.label)

    # Save results
    if args.save:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / "clusters.json"
        with open(output_path, "w") as f:
            json.dump(clusters, f, indent=2, default=str)
        print(f"\n✅ Saved cluster analysis to {output_path}")

    # Generate config suggestions
    if args.suggest_config:
        print("\n" + "=" * 70)
        print("SUGGESTED THEME CONFIG (add to config.yaml)")
        print("=" * 70)

        for cluster in clusters:
            theme = generate_theme_config(cluster)
            print(f"\n  {theme['key']}:")
            print(f"    title: \"{theme['config']['title']}\"")
            print(f"    output_file: \"{theme['config']['output_file']}\"")
            print(f"    queries:")
            for q in theme['config']['queries']:
                print(f"      - \"{q}\"")

    print("\n" + "─" * 70)
    print("Next steps:")
    print("  1. Review clusters above — do any surprise you?")
    print("  2. Add interesting emergent themes to config.yaml")
    print("  3. Run: python _Prompts/p4_pipeline/02_retrieve.py --theme <new_theme>")
    print("─" * 70)


if __name__ == "__main__":
    main()
