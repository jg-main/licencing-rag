# Project Configuration
# ---------------------
PROJECT_NAME := licencing-rag
PYTHON_VERSION := 3.13
VENV := .venv
BIN := $(VENV)/bin
PYTHON_DIRS := app api

# API Server Configuration
# ------------------------
API_HOST := 0.0.0.0
API_PORT := 8000

# Terminal Colors
# ---------------
CYAN := \033[0;36m
GREEN := \033[0;32m
RED := \033[0;31m
BLUE := \033[0;34m
YELLOW := \033[1;33m
BOLD := \033[1m
END := \033[0m

# Default target
# --------------
.DEFAULT_GOAL := help

# Utility Functions
# -----------------
define log_info
echo "$(BLUE)ℹ️  $(1)$(END)"
endef

define log_success
echo "$(GREEN)✅ $(1)$(END)"
endef

define log_warning
echo "$(YELLOW)⚠️  $(1)$(END)"
endef

define log_error
echo "$(RED)❌ $(1)$(END)"
endef


################################################################################
# HELP
################################################################################
.PHONY: help
help: ## 📚 Show this help message
	@echo "$(BOLD)$(PROJECT_NAME) Development Makefile$(END)"
	@echo ""
	@echo "$(CYAN)📋 Available Commands:$(END)"
	@echo ""
	@echo "$(BOLD)🚀 Setup & Environment:$(END)"
	@grep -E '^(check-uv|sync|upgrade|install-hooks|setup|clean|clean-all):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(END) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)🎨 Code Quality:$(END)"
	@grep -E '^(format|format-md|lint|lint-check|type-check|quality):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(END) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)🧪 Testing:$(END)"
	@grep -E '^(test[a-zA-Z_-]*|qa):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(END) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)📦 Build & Release:$(END)"
	@grep -E '^(build|release-check):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(END) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)📓 Development Tools:$(END)"
	@grep -E '^(setup-kernel|run-jupyter):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(END) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)🌐 API Server:$(END)"
	@grep -E '^(api|api-dev|api-prod):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(END) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)📈 QTrader:$(END)"
	@grep -E '^(qtrader-project):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(END) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BOLD)🔧 Utilities:$(END)"
	@grep -E '^(help):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(END) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)💡 Quick Start:$(END)"
	@echo "  $(CYAN)make setup$(END)     - Complete development environment setup"
	@echo "  $(CYAN)make qa$(END)        - Run full quality assurance (format + lint + test)"
	@echo "  $(CYAN)make test$(END)      - Run all tests with coverage"
	@echo ""


################################################################################
# PROJECT SETUP
################################################################################
.PHONY: check-uv
check-uv: ## 🔧 Verify UV package manager is available
	@echo "$(BLUE)ℹ️  Checking UV package manager...$(END)"
	@command -v uv >/dev/null 2>&1 || { \
		echo "$(RED)❌ UV is not installed$(END)"; \
		echo "$(RED)Please install UV from: https://docs.astral.sh/uv/getting-started/installation/$(END)"; \
		exit 1; \
	}
	@echo "$(GREEN)✅ UV package manager is available$(END)"

.PHONY: sync
sync: check-uv ## 📦 Sync dependencies and create virtual environment
	@echo "$(BLUE)ℹ️  Syncing dependencies with UV...$(END)"
	@uv sync --all-packages --all-groups || { \
		echo "$(RED)❌ Failed to sync packages$(END)"; \
		exit 1; \
	}
	@echo "$(GREEN)✅ Dependencies synced successfully$(END)"

.PHONY: upgrade
upgrade: check-uv ## 🔄 Upgrade all packages to latest versions
	@echo "$(BLUE)ℹ️  Upgrading all packages with UV...$(END)"
	@uv lock --upgrade || { \
		echo "$(RED)❌ Failed to upgrade packages$(END)"; \
		exit 1; \
	}
	@echo "$(BLUE)ℹ️  Syncing upgraded dependencies...$(END)"
	@uv sync --all-packages --all-groups || { \
		echo "$(RED)❌ Failed to sync upgraded packages$(END)"; \
		exit 1; \
	}
	@echo "$(GREEN)✅ All packages upgraded and synced successfully$(END)"

.PHONY: install-hooks
install-hooks: sync ## 🪝 Install pre-commit hooks
	@echo "$(BLUE)ℹ️  Installing pre-commit hooks...$(END)"
	@uv run pre-commit install || { \
		echo "$(RED)❌ Failed to install pre-commit hooks$(END)"; \
		exit 1; \
	}
	@echo "$(GREEN)✅ Pre-commit hooks installed$(END)"

.PHONY: pre-commit
pre-commit: sync ## 🔍 Run pre-commit hooks manually
	@echo "$(BLUE)ℹ️  Running pre-commit hooks...$(END)"
	@uv run pre-commit run --all-files || { \
		echo "$(RED)❌ Pre-commit hooks failed$(END)"; \
		exit 1; \
	}
	@echo "$(GREEN)✅ Pre-commit hooks passed$(END)"

.PHONY: setup
setup: sync install-hooks ## 🚀 Complete development environment setup
	@echo "$(BLUE)ℹ️  Verifying project installation...$(END)"
	@uv pip list | grep -q licencing-rag && echo "$(GREEN)✅ Project installed in editable mode$(END)" || { \
		echo "$(YELLOW)⚠️  Installing project in editable mode...$(END)"; \
		uv pip install -e .; \
	}
	@echo "$(GREEN)✅ Development environment setup complete!$(END)"
	@echo "$(BLUE)💡 Use 'uv run <command>' to run commands in the environment$(END)"
	@echo "$(BLUE)💡 Example: uv run rag query 'what is a subscriber?'$(END)"

.PHONY: clean
clean: ## 🧹 Clean workspace (remove cache, temp files)
	@echo "$(BLUE)ℹ️  Cleaning development environment...$(END)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@rm -rf build/ dist/ *.egg-info .pytest_cache/ .ruff_cache/ .mypy_cache/
	@rm -f .coverage coverage.xml
	@rm -rf .venv/
	@rm -rf htmlcov/ mypy-report/ .coverage.*
	@echo "$(GREEN)✅ Workspace cleaned$(END)"

.PHONY: clean-all
clean-all: clean ## 🧹 Full clean (workspace + indexes + extracted data)
	@echo "$(BLUE)ℹ️  Cleaning indexes and extracted data...$(END)"
	@rm -rf index/chroma/
	@rm -rf index/bm25/
	@rm -rf index/definitions/
	@rm -rf data/text/
	@rm -rf data/chunks/
	@rm -rf logs/*.jsonl
	@echo "$(GREEN)✅ Full clean complete - ready for fresh ingestion$(END)"


################################################################################
# CODE QUALITY
################################################################################

.PHONY: format
format: sync ## 🎨 Format code with ruff, isort, and markdown (matches pre-commit)
	@echo "$(BLUE)ℹ️  Formatting Python code with ruff (fix + format)...$(END)"
	@uv run ruff check --fix --target-version py313 $(PYTHON_DIRS)
	@uv run ruff format --target-version py313 $(PYTHON_DIRS)
	@echo "$(BLUE)ℹ️  Formatting imports with isort...$(END)"
	@uv run isort $(PYTHON_DIRS)
	@echo "$(BLUE)ℹ️  Formatting Markdown files...$(END)"
	@uv run mdformat . --wrap=no --end-of-line=lf || echo "$(YELLOW)⚠️  mdformat not installed, run 'uv add --dev mdformat mdformat-gfm mdformat-tables'$(END)"
	@echo "$(GREEN)✅ Code and markdown formatting completed$(END)"

.PHONY: lint
lint: sync ## 🔍 Lint code and fix auto-fixable issues (matches pre-commit)
	@echo "$(BLUE)ℹ️  Linting code...$(END)"
	@uv run ruff check --fix --target-version py313 $(PYTHON_DIRS)
	@echo "$(GREEN)✅ Code linting completed$(END)"

.PHONY: lint-check
lint-check: sync ## 📋 Check code without making changes (matches pre-commit)
	@echo "$(BLUE)ℹ️  Checking code quality...$(END)"
	@uv run ruff check --target-version py313 $(PYTHON_DIRS)
	@uv run ruff format --target-version py313 --check $(PYTHON_DIRS)
	@uv run isort --check-only $(PYTHON_DIRS)
	@echo "$(GREEN)✅ Code quality check passed$(END)"

.PHONY: format-md
format-md: sync ## 📝 Format Markdown files only
	@echo "$(BLUE)ℹ️  Formatting Markdown files...$(END)"
	@uv run mdformat . --wrap=no --end-of-line=lf || echo "$(YELLOW)⚠️  mdformat not installed, run 'uv add --dev mdformat mdformat-gfm mdformat-tables'$(END)"
	@echo "$(GREEN)✅ Markdown formatting completed$(END)"

.PHONY: type-check
type-check: sync ## 🔬 Run type checking with MyPy
	@echo "$(BLUE)ℹ️  Running type checks with MyPy...$(END)"
	@uv run mypy $(PYTHON_DIRS) || { \
		echo "$(RED)❌ Type checking failed$(END)"; \
		exit 1; \
	}
	@echo "$(GREEN)✅ Type checking completed$(END)"

.PHONY: qa
qa: format lint-check type-check ## 🏆 Run all code quality checks
	@echo "$(GREEN)✅ All code quality checks passed$(END)"


################################################################################
# API SERVER
################################################################################

.PHONY: api
api: sync ## 🌐 Run API server locally with auto-reload (development)
	@echo "$(BLUE)ℹ️  Starting API server in development mode...$(END)"
	@echo "$(CYAN)📡 Server: http://$(API_HOST):$(API_PORT)$(END)"
	@echo "$(CYAN)📚 Docs:   http://localhost:$(API_PORT)/docs$(END)"
	@echo "$(CYAN)📖 ReDoc:  http://localhost:$(API_PORT)/redoc$(END)"
	@uv run uvicorn api.main:app --host $(API_HOST) --port $(API_PORT) --reload

.PHONY: api-dev
api-dev: sync ## 🌐 Run API server with debug logging and reload
	@echo "$(BLUE)ℹ️  Starting API server in debug mode...$(END)"
	@echo "$(CYAN)📡 Server: http://$(API_HOST):$(API_PORT)$(END)"
	@echo "$(CYAN)📚 Docs:   http://localhost:$(API_PORT)/docs$(END)"
	@RAG_LOG_LEVEL=DEBUG uv run uvicorn api.main:app --host $(API_HOST) --port $(API_PORT) --reload --log-level debug

.PHONY: api-prod
api-prod: sync ## 🌐 Run API server in production mode (no reload, multiple workers)
	@echo "$(BLUE)ℹ️  Starting API server in production mode...$(END)"
	@echo "$(CYAN)📡 Server: http://$(API_HOST):$(API_PORT)$(END)"
	@uv run uvicorn api.main:app --host $(API_HOST) --port $(API_PORT) --workers 4
