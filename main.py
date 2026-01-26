#!/usr/bin/env python3
# main.py
"""CLI entrypoint for the License Intelligence System."""

import argparse
import sys

from app.config import PROVIDERS


def cmd_ingest(args: argparse.Namespace) -> int:
    """Handle the ingest command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    from app.ingest import ingest_provider

    providers_to_ingest = []

    if args.all:
        providers_to_ingest = list(PROVIDERS.keys())
    elif args.provider:
        providers_to_ingest = [args.provider]
    else:
        print("Error: Specify --provider <name> or --all")
        return 1

    for provider in providers_to_ingest:
        try:
            print(f"\n{'=' * 60}")
            print(f"Ingesting provider: {provider}")
            print("=" * 60)
            stats = ingest_provider(provider, force=args.force)
            errors = stats.get("errors", [])
            if errors and isinstance(errors, list) and len(errors) > 0:
                print(f"Completed with {len(errors)} errors")
        except (ValueError, FileNotFoundError) as e:
            print(f"Error: {e}")
            return 1
        except Exception as e:
            print(f"Unexpected error during ingestion: {e}")
            return 1

    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """Handle the query command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    from app.query import print_response
    from app.query import query

    providers = args.provider if args.provider else None

    try:
        result = query(args.question, providers=providers, top_k=args.top_k)
        print_response(result)
        return 0
    except RuntimeError as e:
        print(f"Error: {e}")
        return 3
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """Handle the list command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    from app.ingest import list_indexed_documents

    providers_to_list = []

    if args.provider:
        providers_to_list = [args.provider]
    else:
        providers_to_list = list(PROVIDERS.keys())

    for provider in providers_to_list:
        print(f"\n{provider.upper()} Documents:")
        print("-" * 40)

        documents = list_indexed_documents(provider)
        if documents:
            for i, doc in enumerate(documents, 1):
                print(f"  {i:3}. {doc}")
            print(f"\nTotal: {len(documents)} documents")
        else:
            print("  No documents indexed.")

    return 0


def main() -> int:
    """Main CLI entrypoint.

    Returns:
        Exit code.
    """
    parser = argparse.ArgumentParser(
        description="License Intelligence System - Local RAG for license agreements",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py ingest --provider cme
  python main.py query "What are the redistribution requirements?"
  python main.py query --provider cme "What fees apply to derived data?"
  python main.py list --provider cme
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Ingest command
    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Ingest documents into the vector database",
    )
    ingest_parser.add_argument(
        "--provider",
        type=str,
        help="Provider to ingest (e.g., cme)",
    )
    ingest_parser.add_argument(
        "--all",
        action="store_true",
        help="Ingest all configured providers",
    )
    ingest_parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing collection before ingesting",
    )

    # Query command
    query_parser = subparsers.add_parser(
        "query",
        help="Query the knowledge base",
    )
    query_parser.add_argument(
        "question",
        type=str,
        help="Question to ask",
    )
    query_parser.add_argument(
        "--provider",
        type=str,
        action="append",
        help="Provider(s) to query (can be specified multiple times)",
    )
    query_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of chunks to retrieve (default: 5)",
    )

    # List command
    list_parser = subparsers.add_parser(
        "list",
        help="List indexed documents",
    )
    list_parser.add_argument(
        "--provider",
        type=str,
        help="Provider to list (default: all)",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "ingest":
        return cmd_ingest(args)
    elif args.command == "query":
        return cmd_query(args)
    elif args.command == "list":
        return cmd_list(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
