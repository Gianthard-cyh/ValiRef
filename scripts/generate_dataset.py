import os
import sys
import argparse

# Add project root to sys.path to allow imports from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bench.dataset import BenchmarkDatasetFactory


def main():
    parser = argparse.ArgumentParser(description="Generate hallucinated dataset from ArXiv papers.")
    parser.add_argument("--topic", type=str, default="cs.CL", help="ArXiv topic code (e.g., cs.CL)")
    parser.add_argument("--count", type=int, default=1000, help="Number of papers to crawl")
    parser.add_argument("--output", type=str, default="data/dataset.csv", help="Output CSV file path")
    
    args = parser.parse_args()

    print(f"Initializing dataset factory...")
    try:
        factory = BenchmarkDatasetFactory()
    except ValueError as e:
        print(f"Error: {e}")
        print("Please set the DEEPSEEK_API_KEY environment variable or in a .env file.")
        return

    print(f"Crawling {args.count} papers for topic {args.topic}...")
    try:
        dataset = factory.crawl(topic=args.topic, count=args.count)
        print(f"Crawled {len(dataset)} papers.")
    except Exception as e:
        print(f"Error crawling papers: {e}")
        return

    print("Injecting hallucinations...")
    try:
        hallucinated_dataset = factory.hallucinate(dataset)
        print(f"Hallucination injection complete. Total papers: {len(hallucinated_dataset)}")
    except Exception as e:
        print(f"Error injecting hallucinations: {e}")
        return

    print(f"Saving dataset to {args.output}...")
    try:
        hallucinated_dataset.to_csv(args.output)
        print(f"Successfully saved dataset to {args.output}")
    except Exception as e:
        print(f"Error saving dataset: {e}")

if __name__ == "__main__":
    main()
