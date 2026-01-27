"""CLI entrypoint for the License Intelligence System.

This module provides the main() function that serves as the entry point
for the 'rag' command when installed via pip install -e .
"""

import argparse
import sys

from app.config import PROVIDERS
from app.logging import configure_logging


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
    from app.output import OutputFormat
    from app.output import print_result
    from app.query import query

    providers = args.provider if args.provider else None
    search_mode = getattr(args, "search_mode", "hybrid")

    try:
        result = query(
            args.question,
            providers=providers,
            top_k=args.top_k,
            search_mode=search_mode,
        )

        # Select output format
        output_format = (
            OutputFormat.JSON if args.format == "json" else OutputFormat.CONSOLE
        )

        print_result(result, output_format)
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
    """Main CLI entrypoint for the 'rag' command.

    Returns:
        Exit code.
    """
    parser = argparse.ArgumentParser(
        prog="rag",
        description="License Intelligence System - Local RAG for license agreements",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  rag ingest --provider cme
  rag query "What are the redistribution requirements?"
  rag query --provider cme "What fees apply to derived data?"
  rag query --search-mode keyword "subscriber definition"
  rag query --search-mode vector "What are the licensing terms?"
  rag query --format json "What are the fees?" > result.json
  rag list --provider cme
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
    query_parser.add_argument(
        "--search-mode",
        type=str,
        choices=["vector", "keyword", "hybrid"],
        default="hybrid",
        help="Search mode: vector (semantic), keyword (BM25), or hybrid (default)",
    )
    query_parser.add_argument(
        "--format",
        type=str,
        choices=["console", "json"],
        default="console",
        help="Output format: console (Rich styled, default) or json (structured)",
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

    # Global options
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Initialize logging
    configure_logging(debug=args.debug)

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


def cli_main() -> None:
    """Entry point wrapper that calls sys.exit().

    This is the function referenced in pyproject.toml [project.scripts].
    """
    sys.exit(main())
