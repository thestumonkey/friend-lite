# ========================================
# Friend-Lite Management System
# ========================================
# Central management interface for Friend-Lite project
# Handles configuration, deployment, and maintenance tasks

# Load environment variables from .env file (if it exists)
ifneq (,$(wildcard ./.env))
    include .env
    export $(shell sed 's/=.*//' .env | grep -v '^\s*$$' | grep -v '^\s*\#')
endif

# Load configuration definitions for Kubernetes
# Use config-k8s.env for K8s deployments
ifneq (,$(wildcard ./config-k8s.env))
    include config-k8s.env
    export $(shell sed 's/=.*//' config-k8s.env | grep -v '^\s*$$' | grep -v '^\s*\#')
else
    # Fallback to config.env for backwards compatibility
    ifneq (,$(wildcard ./config.env))
        include config.env
        export $(shell sed 's/=.*//' config.env | grep -v '^\s*$$' | grep -v '^\s*\#')
    endif
endif

# Load secrets (gitignored) - required for K8s secrets generation
ifneq (,$(wildcard ./.env.secrets))
    include .env.secrets
    export $(shell sed 's/=.*//' .env.secrets | grep -v '^\s*$$' | grep -v '^\s*\#')
endif

# Load API keys (gitignored) - required for K8s secrets generation
ifneq (,$(wildcard ./.env.api-keys))
    include .env.api-keys
    export $(shell sed 's/=.*//' .env.api-keys | grep -v '^\s*$$' | grep -v '^\s*\#')
endif

# Script directories
SCRIPTS_DIR := scripts
K8S_SCRIPTS_DIR := $(SCRIPTS_DIR)/k8s

.PHONY: help menu wizard setup-secrets setup-tailscale configure-tailscale-serve setup-environment check-secrets setup-k8s setup-infrastructure setup-rbac setup-storage-pvc config config-k8s config-all clean deploy deploy-docker deploy-k8s deploy-k8s-full deploy-infrastructure deploy-apps check-infrastructure check-apps build-backend up-backend down-backend k8s-status k8s-cleanup k8s-purge audio-manage mycelia-sync-status mycelia-sync-all mycelia-sync-user mycelia-check-orphans mycelia-reassign-orphans mycelia-create-token test-robot test-robot-integration test-robot-unit test-robot-endpoints test-robot-specific test-robot-clean infra-start infra-stop infra-restart infra-logs infra-status infra-clean caddy-start caddy-stop caddy-restart caddy-logs caddy-status caddy-regenerate env-list env-start env-stop env-clean env-status

# Default target
.DEFAULT_GOAL := menu

menu: ## Show interactive menu (default)
	@echo "🎯 Chronicle Management System"
	@echo "================================"
	@echo
	@echo "🚀 Standard Docker Compose Commands:"
	@echo "  make up                     🚀 Start Chronicle (auto-starts infra if needed)"
	@echo "  make down                   🛑 Stop app only (keeps infra running)"
	@echo "  make down-all               🛑 Stop everything (infra + app)"
	@echo "  make build                  🔨 Rebuild application images"
	@echo "  make restart                🔄 Restart app only"
	@echo "  make restart-all            🔄 Restart everything"
	@echo "  make logs                   📋 View app logs"
	@echo "  make logs-all               📋 View all logs"
	@echo
	@echo "  OR use docker compose directly:"
	@echo "  docker compose -f docker-compose.infra.yml up -d     (start infra)"
	@echo "  cd backends/advanced && docker compose up -d         (start app)"
	@echo "  cd backends/advanced && docker compose down          (stop app only)"
	@echo "  docker compose -f docker-compose.infra.yml down      (stop infra)"
	@echo
	@echo "⚡ Quick Start (First Time):"
	@echo "  quick-start                 🚀 Interactive setup with zero configuration"
	@echo "  quick-start-reset           🔄 Reset and regenerate configuration"
	@echo
	@echo "🏗️  Infrastructure Control:"
	@echo "  infra-start                 🏗️  Start infrastructure only (MongoDB, Redis, Qdrant)"
	@echo "  infra-stop                  🛑 Stop infrastructure (keeps data)"
	@echo "  infra-clean                 🗑️  Stop infrastructure and remove all data"
	@echo
	@echo "🧙 Advanced Setup:"
	@echo "  installer                   🚀 Chronicle Install - Python-based installer"
	@echo "  wizard                      🧙 Interactive setup wizard (secrets + Tailscale + environment)"
	@echo "  setup-secrets               🔐 Configure API keys and passwords"
	@echo "  setup-tailscale             🌐 Configure Tailscale for distributed deployment"
	@echo "  configure-tailscale-serve   🌐 Configure Tailscale serve routes (single environment)"
	@echo "  setup-environment           📦 Create a custom environment"
	@echo
	@echo "📋 Quick Actions:"
	@echo "  setup-dev          🛠️  Setup development environment (git hooks, pre-commit)"
	@echo "  setup-k8s          🏗️  Complete Kubernetes setup (registry + infrastructure + RBAC)"
	@echo "  config             📝 Generate all configuration files"
	@echo "  deploy             🚀 Deploy using configured mode ($(DEPLOYMENT_MODE))"
	@echo "  k8s-status         📊 Check Kubernetes cluster status"
	@echo "  k8s-cleanup        🧹 Clean up Kubernetes resources"
	@echo "  audio-manage       🎵 Manage audio files"
	@echo
	@echo "🧪 Testing:"
	@echo "  test-robot         🧪 Run all Robot Framework tests"
	@echo "  test-robot-integration 🔬 Run integration tests only"
	@echo "  test-robot-endpoints 🌐 Run endpoint tests only"
	@echo
	@echo "📝 Configuration:"
	@echo "  config-k8s         ☸️  Generate Kubernetes files (Skaffold env + ConfigMap/Secret)"
	@echo
	@echo "🚀 Deployment:"
	@echo "  deploy-docker      🐳 Deploy with Docker Compose"
	@echo "  deploy-k8s         ☸️  Deploy to Kubernetes with Skaffold"
	@echo "  deploy-k8s-full    🏗️  Deploy infrastructure + applications"
	@echo
	@echo "🔧 Utilities:"
	@echo "  k8s-purge          🗑️  Purge unused images (registry + container)"
	@echo "  check-infrastructure 🔍 Check infrastructure services"
	@echo "  check-apps         🔍 Check application services"
	@echo "  clean              🧹 Clean up generated files"
	@echo
	@echo "🔄 Mycelia Sync:"
	@echo "  mycelia-create-token     🔑 Create Mycelia API token for a user"
	@echo "  mycelia-sync-status      📊 Show Mycelia OAuth sync status"
	@echo "  mycelia-sync-all         🔄 Sync all Friend-Lite users to Mycelia"
	@echo "  mycelia-sync-user        👤 Sync specific user (EMAIL=user@example.com)"
	@echo "  mycelia-check-orphans    🔍 Find orphaned Mycelia objects"
	@echo "  mycelia-reassign-orphans ♻️  Reassign orphans (EMAIL=admin@example.com)"
	@echo
	@echo "🏗️  Shared Infrastructure:"
	@echo "  infra-start              🚀 Start shared infrastructure (MongoDB, Redis, Qdrant, optional Neo4j)"
	@echo "  infra-stop               🛑 Stop infrastructure"
	@echo "  infra-restart            🔄 Restart infrastructure"
	@echo "  infra-status             📊 Check infrastructure status"
	@echo "  infra-logs               📋 View infrastructure logs"
	@echo "  infra-clean              🗑️  Clean all infrastructure data (DANGER!)"
	@echo
	@echo "🌐 Caddy Reverse Proxy (Shared Service):"
	@echo "  caddy-start              🚀 Start shared Caddy (serves all environments)"
	@echo "  caddy-stop               🛑 Stop Caddy"
	@echo "  caddy-restart            🔄 Restart Caddy"
	@echo "  caddy-status             📊 Check if Caddy is running"
	@echo "  caddy-logs               📋 View Caddy logs"
	@echo "  caddy-regenerate         🔧 Regenerate Caddyfile from environments"
	@echo
	@echo "Current configuration:"
	@echo "  DOMAIN: $(DOMAIN)"
	@echo "  DEPLOYMENT_MODE: $(DEPLOYMENT_MODE)"
	@echo "  CONTAINER_REGISTRY: $(CONTAINER_REGISTRY)"
	@echo "  SPEAKER_NODE: $(SPEAKER_NODE)"
	@echo "  INFRASTRUCTURE_NAMESPACE: $(INFRASTRUCTURE_NAMESPACE)"
	@echo "  APPLICATION_NAMESPACE: $(APPLICATION_NAMESPACE)"
	@echo
	@echo "💡 Tip: Run 'make help' for detailed help on any target"

help: ## Show detailed help for all targets
	@echo "🎯 Friend-Lite Management System - Detailed Help"
	@echo "================================================"
	@echo
	@echo "🏗️  KUBERNETES SETUP:"
	@echo "  setup-k8s          Complete initial Kubernetes setup"
	@echo "                     - Configures insecure registry access"
	@echo "                     - Sets up infrastructure services (MongoDB, Qdrant)"
	@echo "                     - Creates shared models PVC"
	@echo "                     - Sets up cross-namespace RBAC"
	@echo "                     - Generates and applies configuration"
	@echo "  setup-infrastructure Deploy infrastructure services (MongoDB, Qdrant)"
	@echo "  setup-rbac         Set up cross-namespace RBAC"
	@echo "  setup-storage-pvc  Create shared models PVC"
	@echo
	@echo "📝 CONFIGURATION:"
	@echo "  config             Generate all configuration files (K8s)"
	@echo "  config-k8s         Generate Kubernetes files (Skaffold env + ConfigMap/Secret)"
	@echo
	@echo "🚀 DEPLOYMENT:"
	@echo "  deploy             Deploy using configured deployment mode"
	@echo "  deploy-docker      Deploy with Docker Compose"
	@echo "  deploy-k8s         Deploy to Kubernetes with Skaffold"
	@echo "  deploy-k8s-full    Deploy infrastructure + applications"
	@echo
	@echo "🔧 KUBERNETES UTILITIES:"
	@echo "  k8s-status         Check Kubernetes cluster status and health"
	@echo "  k8s-cleanup        Clean up Kubernetes resources and storage"
	@echo "  k8s-purge          Purge unused images (registry + container)"
	@echo
	@echo "🎵 AUDIO MANAGEMENT:"
	@echo "  audio-manage       Interactive audio file management"
	@echo
	@echo "🔄 MYCELIA SYNC:"
	@echo "  mycelia-create-token Create Mycelia API token for a user"
	@echo "  mycelia-sync-status Show Mycelia OAuth sync status for all users"
	@echo "  mycelia-sync-all   Sync all Friend-Lite users to Mycelia OAuth"
	@echo "  mycelia-sync-user  Sync specific user (EMAIL=user@example.com)"
	@echo "  mycelia-check-orphans Find Mycelia objects without Friend-Lite owner"
	@echo "  mycelia-reassign-orphans Reassign orphaned objects (EMAIL=admin@example.com)"
	@echo
	@echo "🧪 ROBOT FRAMEWORK TESTING:"
	@echo "  test-robot         Run all Robot Framework tests"
	@echo "  test-robot-integration Run integration tests only"
	@echo "  test-robot-endpoints Run endpoint tests only"
	@echo "  test-robot-specific FILE=path Run specific test file"
	@echo "  test-robot-clean   Clean up test results"
	@echo
	@echo "🔍 MONITORING:"
	@echo "  check-infrastructure Check if infrastructure services are running"
	@echo "  check-apps         Check if application services are running"
	@echo
	@echo "🧹 CLEANUP:"
	@echo "  clean              Clean up generated configuration files"

# ========================================
# DEVELOPMENT SETUP
# ========================================

setup-dev: ## Setup development environment (git hooks, pre-commit)
	@echo "🛠️  Setting up development environment..."
	@echo ""
	@echo "📦 Installing pre-commit..."
	@pip install pre-commit 2>/dev/null || pip3 install pre-commit
	@echo ""
	@echo "🔧 Installing git hooks..."
	@pre-commit install --hook-type pre-push
	@pre-commit install --hook-type pre-commit
	@echo ""
	@echo "✅ Development environment setup complete!"
	@echo ""
	@echo "💡 Hooks installed:"
	@echo "  • Robot Framework tests run before push"
	@echo "  • Black/isort format Python code on commit"
	@echo "  • Code quality checks on commit"
	@echo ""
	@echo "⚙️  To skip hooks: git push --no-verify / git commit --no-verify"

# ========================================
# QUICK START (Zero Configuration)
# ========================================

.PHONY: up down down-all build restart restart-all logs logs-all quick-start quick-start-reset quick-start-stop quick-start-clean quick-start-logs quick-start-rebuild infra-start infra-stop infra-clean

up: ## 🚀 Start Chronicle (infrastructure + application)
	@echo "🚀 Starting Chronicle..."
	@if [ ! -f .env.default ]; then \
		echo "⚠️  Configuration not found. Running quick-start.sh..."; \
		./quick-start.sh; \
	else \
		if ! docker ps --filter "name=^mongo$$" --filter "status=running" -q | grep -q .; then \
			echo "🏗️  Infrastructure not running, starting it first..."; \
			docker compose -f docker-compose.infra.yml up -d; \
			sleep 3; \
		fi; \
		WEBUI_PORT=$$(grep '^WEBUI_PORT=' backends/advanced/.env 2>/dev/null | cut -d= -f2 || echo "3000"); \
		BACKEND_PORT=$$(grep '^BACKEND_PORT=' backends/advanced/.env 2>/dev/null | cut -d= -f2 || echo "8000"); \
		cd backends/advanced && docker compose up -d; \
		echo "✅ Chronicle started"; \
		echo ""; \
		printf "╔════════════════════════════════════════════════════╗\n"; \
		printf "║                                                    ║\n"; \
		printf "║  🚀 Chronicle Started Successfully                 ║\n"; \
		printf "║                                                    ║\n"; \
		printf "║  WebUI:    http://localhost:%-22s║\n" "$$WEBUI_PORT"; \
		printf "║  Backend:  http://localhost:%-22s║\n" "$$BACKEND_PORT"; \
		printf "║                                                    ║\n"; \
		printf "╚════════════════════════════════════════════════════╝\n"; \
		echo ""; \
	fi

down: ## 🛑 Stop Chronicle application only (keeps infrastructure running)
	@echo "🛑 Stopping Chronicle application..."
	@cd backends/advanced && docker compose down
	@echo "✅ Application stopped (infrastructure still running)"
	@echo "💡 To stop everything: make down-all"

down-all: ## 🛑 Stop everything (infrastructure + application)
	@echo "🛑 Stopping all services..."
	@cd backends/advanced && docker compose down
	@docker compose -f docker-compose.infra.yml down
	@echo "✅ All services stopped"

build: ## 🔨 Rebuild Chronicle application images
	@echo "🔨 Building Chronicle..."
	@cd backends/advanced && docker compose build

restart: ## 🔄 Restart Chronicle application only
	@echo "🔄 Restarting Chronicle application..."
	@cd backends/advanced && docker compose restart
	@echo "✅ Application restarted"

restart-all: ## 🔄 Restart everything (infrastructure + application)
	@echo "🔄 Restarting all services..."
	@cd backends/advanced && docker compose restart
	@docker compose -f docker-compose.infra.yml restart
	@echo "✅ All services restarted"

logs: ## 📋 View Chronicle application logs
	@cd backends/advanced && docker compose logs -f

logs-all: ## 📋 View all logs (infrastructure + application)
	@cd backends/advanced && docker compose logs -f &
	@docker compose -f docker-compose.infra.yml logs -f

quick-start: ## 🚀 Start Chronicle with zero configuration (interactive setup)
	@./quick-start.sh

quick-start-reset: ## 🔄 Reset and regenerate quick-start configuration
	@./quick-start.sh --reset

quick-start-stop: ## 🛑 Stop quick-start environment
	@echo "🛑 Stopping application..."
	@cd backends/advanced && docker compose down
	@echo "✅ Application stopped (data preserved)"

quick-start-clean: ## 🗑️  Stop application and remove all data volumes
	@echo "🗑️  Stopping application and removing data..."
	@cd backends/advanced && docker compose down -v
	@docker compose -f docker-compose.infra.yml down -v
	@echo "✅ Environment cleaned"

quick-start-logs: ## 📋 View quick-start logs
	@cd backends/advanced && docker compose logs -f

quick-start-rebuild: ## 🔨 Rebuild and restart application (keeps infrastructure running)
	@echo "🔨 Rebuilding application..."
	@cd backends/advanced && docker compose up -d --build
	@echo "✅ Application rebuilt and restarted"

# ========================================
# INTERACTIVE SETUP WIZARD
# ========================================

.PHONY: installer wizard setup-secrets setup-tailscale setup-environment check-secrets

installer: ## 🚀 Chronicle Install - Python-based interactive installer (recommended)
	@./chronicle-install.sh

wizard: ## 🧙 Interactive setup wizard - guides through complete Friend-Lite setup
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "🧙 Friend-Lite Setup Wizard"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "This wizard will guide you through:"
	@echo "  1. 📦 Creating your environment (name, ports, services)"
	@echo "  2. 🔐 Configuring secrets (API keys based on your services)"
	@echo "  3. 🌐 Optionally configuring Tailscale for remote access"
	@echo "  4. 🔧 Finalizing setup (certificates, final configuration)"
	@echo ""
	@read -p "Press Enter to continue or Ctrl+C to exit..."
	@echo ""
	@$(MAKE) --no-print-directory setup-environment
	@echo ""
	@$(MAKE) --no-print-directory setup-secrets
	@echo ""
	@$(MAKE) --no-print-directory setup-tailscale
	@echo ""
	@$(MAKE) --no-print-directory finalize-setup
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "✅ Setup Complete!"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "🚀 Next Steps:"
	@echo ""
	@if [ -f ".env.secrets" ] && [ -d "environments" ]; then \
		LATEST_ENV=$$(ls -t environments/*.env 2>/dev/null | head -1 | xargs basename -s .env 2>/dev/null || echo "dev"); \
		echo "  Start your environment:"; \
		echo "    ./start-env.sh $$LATEST_ENV"; \
		echo ""; \
		echo "  💡 Your configured services will start automatically!"; \
	else \
		echo "  ⚠️  Some setup steps were skipped. Run individual targets:"; \
		echo "    make setup-secrets"; \
		echo "    make setup-environment"; \
	fi
	@echo ""
	@echo "📚 Documentation:"
	@echo "  • ENVIRONMENTS.md - Environment system overview"
	@echo "  • SSL_SETUP.md - Tailscale and SSL configuration"
	@echo "  • SETUP.md - Detailed setup instructions"
	@echo ""

check-secrets: ## Check if secrets file exists and is configured
	@if [ ! -f ".env.secrets" ]; then \
		echo "❌ .env.secrets not found"; \
		exit 1; \
	fi
	@if ! grep -q "^AUTH_SECRET_KEY=" .env.secrets || grep -q "your-super-secret" .env.secrets; then \
		echo "❌ .env.secrets exists but needs configuration"; \
		exit 1; \
	fi
	@echo "✅ Secrets file configured"

setup-secrets: ## 🔐 Interactive secrets setup (API keys, passwords)
	@./scripts/setup-secrets.sh

setup-tailscale: ## 🌐 Interactive Tailscale setup for distributed deployment
	@./scripts/setup-tailscale.sh

configure-tailscale-serve: ## 🌐 Configure Tailscale serve for an environment
	@./scripts/configure-tailscale-serve.sh

setup-environment: ## 📦 Create a custom environment configuration
	@./scripts/setup-environment.sh

finalize-setup: ## 🔧 Finalize setup (generate Caddyfile, provision certificates)
	@./scripts/finalize-setup.sh

# ========================================
# KUBERNETES SETUP
# ========================================

setup-k8s: ## Initial Kubernetes setup (registry + infrastructure)
	@echo "🏗️  Starting Kubernetes initial setup..."
	@echo "This will set up the complete infrastructure for Friend-Lite"
	@echo
	@echo "📋 Setup includes:"
	@echo "  • Insecure registry configuration"
	@echo "  • Infrastructure services (MongoDB, Qdrant)"
	@echo "  • Shared models PVC for speaker recognition"
	@echo "  • Cross-namespace RBAC"
	@echo "  • Configuration generation and application"
	@echo
	@read -p "Enter your Kubernetes node IP address: " node_ip; \
	if [ -z "$$node_ip" ]; then \
		echo "❌ Node IP is required"; \
		exit 1; \
	fi; \
	echo "🔧 Step 1: Configuring insecure registry access on $$node_ip..."; \
	$(SCRIPTS_DIR)/configure-insecure-registry-remote.sh $$node_ip; \
	echo "📦 Step 2: Setting up storage for speaker recognition..."; \
	$(K8S_SCRIPTS_DIR)/setup-storage.sh; \
	echo "📝 Step 3: Generating configuration files..."; \
	$(MAKE) config-k8s; \
	echo "🏗️  Step 4: Setting up infrastructure services..."; \
	$(MAKE) setup-infrastructure; \
	echo "🔐 Step 5: Setting up cross-namespace RBAC..."; \
	$(MAKE) setup-rbac; \
	echo "💾 Step 6: Creating shared models PVC..."; \
	$(MAKE) setup-storage-pvc; \
	echo "✅ Kubernetes initial setup completed!"
	@echo
	@echo "🎯 Next steps:"
	@echo "  • Run 'make deploy' to deploy applications"
	@echo "  • Run 'make k8s-status' to check cluster status"
	@echo "  • Run 'make help' for more options"

setup-infrastructure: ## Set up infrastructure services (MongoDB, Qdrant)
	@echo "🏗️  Setting up infrastructure services..."
	@echo "Deploying MongoDB and Qdrant to $(INFRASTRUCTURE_NAMESPACE) namespace..."
	@set -a; source skaffold.env; set +a; skaffold run --profile=infrastructure --default-repo=$(CONTAINER_REGISTRY)
	@echo "⏳ Waiting for infrastructure services to be ready..."
	@kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=mongodb -n $(INFRASTRUCTURE_NAMESPACE) --timeout=300s || echo "⚠️  MongoDB not ready yet"
	@kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=qdrant -n $(INFRASTRUCTURE_NAMESPACE) --timeout=300s || echo "⚠️  Qdrant not ready yet"
	@echo "✅ Infrastructure services deployed"

setup-rbac: ## Set up cross-namespace RBAC
	@echo "🔐 Setting up cross-namespace RBAC..."
	@kubectl apply -f k8s-manifests/cross-namespace-rbac.yaml
	@echo "✅ Cross-namespace RBAC configured"

setup-storage-pvc: ## Set up shared models PVC
	@echo "💾 Setting up shared models PVC..."
	@kubectl apply -f k8s-manifests/shared-models-pvc.yaml
	@echo "⏳ Waiting for PVC to be bound..."
	@kubectl wait --for=condition=bound pvc/shared-models-cache -n speech --timeout=60s || echo "⚠️  PVC not bound yet"
	@echo "✅ Shared models PVC created"

# ========================================
# CONFIGURATION
# ========================================

config: config-all ## Generate all configuration files

config-k8s: ## Generate Kubernetes configuration files (ConfigMap/Secret only - no .env files)
	@echo "☸️  Generating Kubernetes configuration files..."
	@python3 scripts/generate-k8s-configs.py
	@echo "📦 Applying ConfigMap and Secret to Kubernetes..."
	@kubectl apply -f k8s-manifests/configmap.yaml -n $(APPLICATION_NAMESPACE) 2>/dev/null || echo "⚠️  ConfigMap not applied (cluster not available?)"
	@kubectl apply -f k8s-manifests/secrets.yaml -n $(APPLICATION_NAMESPACE) 2>/dev/null || echo "⚠️  Secret not applied (cluster not available?)"
	@echo "📦 Copying ConfigMap and Secrets to speech namespace..."
	@kubectl get configmap friend-lite-config -n $(APPLICATION_NAMESPACE) -o yaml | \
		sed -e '/namespace:/d' -e '/resourceVersion:/d' -e '/uid:/d' -e '/creationTimestamp:/d' | \
		kubectl apply -n speech -f - 2>/dev/null || echo "⚠️  ConfigMap not copied to speech namespace"
	@kubectl get secret friend-lite-secrets -n $(APPLICATION_NAMESPACE) -o yaml | \
		sed -e '/namespace:/d' -e '/resourceVersion:/d' -e '/uid:/d' -e '/creationTimestamp:/d' | \
		kubectl apply -n speech -f - 2>/dev/null || echo "⚠️  Credentials secret not copied to speech namespace"
	@kubectl get secret friend-lite-api-keys -n $(APPLICATION_NAMESPACE) -o yaml | \
		sed -e '/namespace:/d' -e '/resourceVersion:/d' -e '/uid:/d' -e '/creationTimestamp:/d' | \
		kubectl apply -n speech -f - 2>/dev/null || echo "⚠️  API keys secret not copied to speech namespace"
	@echo "✅ Kubernetes configuration files generated"

config-all: config-k8s ## Generate all configuration files
	@echo "✅ All configuration files generated"

clean: ## Clean up generated configuration files
	@echo "🧹 Cleaning up generated configuration files..."
	@rm -f backends/advanced/.env
	@rm -f extras/speaker-recognition/.env
	@rm -f extras/openmemory-mcp/.env
	@rm -f extras/asr-services/.env
	@rm -f extras/havpe-relay/.env
	@rm -f backends/simple/.env
	@rm -f backends/other-backends/omi-webhook-compatible/.env
	@rm -f skaffold.env
	@rm -f backends/charts/advanced-backend/templates/env-configmap.yaml
	@echo "✅ Generated files cleaned"

# ========================================
# DEPLOYMENT TARGETS
# ========================================

deploy: ## Deploy using configured deployment mode
	@echo "🚀 Deploying using $(DEPLOYMENT_MODE) mode..."
ifeq ($(DEPLOYMENT_MODE),docker-compose)
	@$(MAKE) deploy-docker
else ifeq ($(DEPLOYMENT_MODE),kubernetes)
	@$(MAKE) deploy-k8s
else
	@echo "❌ Unknown deployment mode: $(DEPLOYMENT_MODE)"
	@exit 1
endif

deploy-docker: ## Deploy using Docker Compose
	@echo "🐳 Deploying with Docker Compose..."
	@cd backends/advanced && docker-compose up -d
	@echo "✅ Docker Compose deployment completed"

deploy-k8s: config-k8s ## Deploy to Kubernetes using Skaffold
	@echo "☸️  Deploying to Kubernetes with Skaffold..."
	@set -a; source skaffold.env; set +a; skaffold run --profile=advanced-backend --default-repo=$(CONTAINER_REGISTRY)
	@echo "✅ Kubernetes deployment completed"

deploy-k8s-full: deploy-infrastructure deploy-apps ## Deploy infrastructure + applications to Kubernetes
	@echo "✅ Full Kubernetes deployment completed"

deploy-infrastructure: ## Deploy infrastructure services to Kubernetes
	@echo "🏗️  Deploying infrastructure services..."
	@kubectl apply -f k8s-manifests/
	@echo "✅ Infrastructure deployment completed"

deploy-apps: config-k8s ## Deploy application services to Kubernetes
	@echo "📱 Deploying application services..."
	@set -a; source skaffold.env; set +a; skaffold run --profile=advanced-backend --default-repo=$(CONTAINER_REGISTRY)
	@echo "✅ Application deployment completed"

# ========================================
# UTILITY TARGETS
# ========================================

check-infrastructure: ## Check if infrastructure services are running
	@echo "🔍 Checking infrastructure services..."
	@kubectl get pods -n $(INFRASTRUCTURE_NAMESPACE) || echo "❌ Infrastructure namespace not found"
	@kubectl get services -n $(INFRASTRUCTURE_NAMESPACE) || echo "❌ Infrastructure services not found"

check-apps: ## Check if application services are running
	@echo "🔍 Checking application services..."
	@kubectl get pods -n $(APPLICATION_NAMESPACE) || echo "❌ Application namespace not found"
	@kubectl get services -n $(APPLICATION_NAMESPACE) || echo "❌ Application services not found"

# ========================================
# DEVELOPMENT TARGETS
# ========================================

build-backend: ## Build backend Docker image
	@echo "🔨 Building backend Docker image..."
	@cd backends/advanced && docker build -t advanced-backend:latest .

up-backend: ## Start backend services
	@echo "🚀 Starting backend services..."
	@cd backends/advanced && docker-compose up -d

down-backend: ## Stop backend services
	@echo "🛑 Stopping backend services..."
	@cd backends/advanced && docker-compose down

# ========================================
# KUBERNETES UTILITIES
# ========================================

k8s-status: ## Check Kubernetes cluster status and health
	@echo "📊 Checking Kubernetes cluster status..."
	@$(K8S_SCRIPTS_DIR)/cluster-status.sh

k8s-cleanup: ## Clean up Kubernetes resources and storage
	@echo "🧹 Starting Kubernetes cleanup..."
	@echo "This will help clean up registry storage and unused resources"
	@$(K8S_SCRIPTS_DIR)/cleanup-registry-storage.sh

k8s-purge: ## Purge unused images (registry + container)
	@echo "🗑️  Purging unused images..."
	@$(K8S_SCRIPTS_DIR)/purge-images.sh

# ========================================
# AUDIO MANAGEMENT
# ========================================

audio-manage: ## Interactive audio file management
	@echo "🎵 Starting audio file management..."
	@$(SCRIPTS_DIR)/manage-audio-files.sh

# ========================================
# MYCELIA SYNC
# ========================================

mycelia-sync-status: ## Show Mycelia OAuth sync status for all users
	@echo "📊 Checking Mycelia OAuth sync status..."
	@cd backends/advanced && uv run python scripts/sync_friendlite_mycelia.py --status

mycelia-sync-all: ## Sync all Friend-Lite users to Mycelia OAuth
	@echo "🔄 Syncing all Friend-Lite users to Mycelia OAuth..."
	@echo "⚠️  This will create OAuth credentials for users without them"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@cd backends/advanced && uv run python scripts/sync_friendlite_mycelia.py --sync-all

mycelia-sync-user: ## Sync specific user to Mycelia OAuth (usage: make mycelia-sync-user EMAIL=user@example.com)
	@echo "👤 Syncing specific user to Mycelia OAuth..."
	@if [ -z "$(EMAIL)" ]; then \
		echo "❌ EMAIL parameter is required. Usage: make mycelia-sync-user EMAIL=user@example.com"; \
		exit 1; \
	fi
	@cd backends/advanced && uv run python scripts/sync_friendlite_mycelia.py --email $(EMAIL)

mycelia-check-orphans: ## Find Mycelia objects without Friend-Lite owner
	@echo "🔍 Checking for orphaned Mycelia objects..."
	@cd backends/advanced && uv run python scripts/sync_friendlite_mycelia.py --check-orphans

mycelia-reassign-orphans: ## Reassign orphaned objects to user (usage: make mycelia-reassign-orphans EMAIL=admin@example.com)
	@echo "♻️  Reassigning orphaned Mycelia objects..."
	@if [ -z "$(EMAIL)" ]; then \
		echo "❌ EMAIL parameter is required. Usage: make mycelia-reassign-orphans EMAIL=admin@example.com"; \
		exit 1; \
	fi
	@echo "⚠️  This will reassign all orphaned objects to: $(EMAIL)"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@cd backends/advanced && uv run python scripts/sync_friendlite_mycelia.py --reassign-orphans --target-email $(EMAIL)

mycelia-create-token: ## Create Mycelia API token for a user in specified environment
	@echo "🔑 Creating Mycelia API Token"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@# List available environments
	@if [ ! -d "environments" ] || [ -z "$$(ls -A environments/*.env 2>/dev/null)" ]; then \
		echo "❌ No environments found. Create one with: make wizard"; \
		exit 1; \
	fi
	@echo "📋 Available environments:"; \
	ls -1 environments/*.env 2>/dev/null | sed 's|environments/||;s|.env$$||' | sed 's/^/  - /'; \
	echo ""
	@# Ask for environment
	@read -p "Environment name: " env_name; \
	if [ ! -f "environments/$$env_name.env" ]; then \
		echo "❌ Environment '$$env_name' not found"; \
		exit 1; \
	fi; \
	echo ""; \
	echo "📦 Checking if $$env_name environment is running..."; \
	echo ""; \
	source "environments/$$env_name.env"; \
	running=$$(docker ps --filter "name=$$COMPOSE_PROJECT_NAME-friend-backend-1" --format "{{.Names}}" 2>/dev/null); \
	if [ -z "$$running" ]; then \
		echo "⚠️  Environment not running. Start it first with:"; \
		echo "   ./start-env.sh $$env_name"; \
		echo ""; \
		exit 1; \
	fi; \
	echo "✅ Environment is running ($$COMPOSE_PROJECT_NAME)"; \
	echo ""; \
	cd backends/advanced && ENV_NAME=$$env_name uv run python scripts/create_mycelia_api_key.py

# ========================================
# TESTING TARGETS
# ========================================

# Define test environment variables
TEST_ENV := BACKEND_URL=http://localhost:8001 ADMIN_EMAIL=test-admin@example.com ADMIN_PASSWORD=test-admin-password-123

test-robot: ## Run all Robot Framework tests
	@echo "🧪 Running all Robot Framework tests..."
	@cd tests && $(TEST_ENV) robot --outputdir ../results .
	@echo "✅ All Robot Framework tests completed"
	@echo "📊 Results available in: results/"

test-robot-integration: ## Run integration tests only
	@echo "🧪 Running Robot Framework integration tests..."
	@cd tests && $(TEST_ENV) robot --outputdir ../results integration/
	@echo "✅ Robot Framework integration tests completed"
	@echo "📊 Results available in: results/"

test-robot-unit: ## Run unit tests only
	@echo "🧪 Running Robot Framework unit tests..."
	@cd tests && $(TEST_ENV) robot --outputdir ../results unit/ || echo "⚠️  No unit tests directory found"
	@echo "✅ Robot Framework unit tests completed"
	@echo "📊 Results available in: results/"

test-robot-endpoints: ## Run endpoint tests only
	@echo "🧪 Running Robot Framework endpoint tests..."
	@cd tests && $(TEST_ENV) robot --outputdir ../results endpoints/
	@echo "✅ Robot Framework endpoint tests completed"
	@echo "📊 Results available in: results/"

test-robot-specific: ## Run specific Robot Framework test file (usage: make test-robot-specific FILE=path/to/test.robot)
	@echo "🧪 Running specific Robot Framework test: $(FILE)"
	@if [ -z "$(FILE)" ]; then \
		echo "❌ FILE parameter is required. Usage: make test-robot-specific FILE=path/to/test.robot"; \
		exit 1; \
	fi
	@cd tests && $(TEST_ENV) robot --outputdir ../results $(FILE)
	@echo "✅ Robot Framework test completed: $(FILE)"
	@echo "📊 Results available in: results/"

test-robot-clean: ## Clean up Robot Framework test results
	@echo "🧹 Cleaning up Robot Framework test results..."
	@rm -rf results/
	@echo "✅ Test results cleaned"

# ========================================
# MULTI-ENVIRONMENT SUPPORT
# ========================================

env-list: ## List available environments
	@echo "📋 Available Environments:"
	@echo ""
	@ls -1 environments/*.env 2>/dev/null | sed 's|environments/||;s|.env$$||' | while read env; do \
		echo "  • $$env"; \
		if [ -f "environments/$$env.env" ]; then \
			grep '^# ' environments/$$env.env | head -1 | sed 's/^# /    /'; \
		fi; \
	done
	@echo ""
	@echo "Usage: make env-start ENV=<name>"
	@echo "   or: ./start-env.sh <name> [options]"

env-start: ## Start specific environment (usage: make env-start ENV=dev)
	@if [ -z "$(ENV)" ]; then \
		echo "❌ ENV parameter required"; \
		echo "Usage: make env-start ENV=dev"; \
		echo ""; \
		$(MAKE) env-list; \
		exit 1; \
	fi
	@./start-env.sh $(ENV) $(OPTS)

env-stop: ## Stop specific environment (usage: make env-stop ENV=dev)
	@if [ -z "$(ENV)" ]; then \
		echo "❌ ENV parameter required"; \
		echo "Usage: make env-stop ENV=dev"; \
		exit 1; \
	fi
	@echo "🛑 Stopping environment: $(ENV)"
	@COMPOSE_PROJECT_NAME=friend-lite-$(ENV) docker compose down

env-clean: ## Clean specific environment data (usage: make env-clean ENV=dev)
	@if [ -z "$(ENV)" ]; then \
		echo "❌ ENV parameter required"; \
		echo "Usage: make env-clean ENV=dev"; \
		exit 1; \
	fi
	@echo "⚠️  This will delete all data for environment: $(ENV)"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@source environments/$(ENV).env && rm -rf $$DATA_DIR
	@COMPOSE_PROJECT_NAME=friend-lite-$(ENV) docker compose down -v
	@echo "✅ Environment $(ENV) cleaned"

env-status: ## Show status of all environments
	@echo "📊 Environment Status:"
	@echo ""
	@for env in $$(ls -1 environments/*.env 2>/dev/null | sed 's|environments/||;s|.env$$||'); do \
		echo "Environment: $$env"; \
		COMPOSE_PROJECT_NAME=friend-lite-$$env docker compose ps 2>/dev/null | grep -v "NAME" || echo "  Not running"; \
		echo ""; \
	done

# ========================================
# SHARED INFRASTRUCTURE (MongoDB, Redis, Qdrant)
# ========================================

infra-start: ## Start shared infrastructure (MongoDB, Redis, Qdrant, optional Neo4j)
	@echo "🚀 Starting shared infrastructure services..."
	@echo ""
	@# Check if network exists, create if not
	@docker network inspect chronicle-network >/dev/null 2>&1 || docker network create chronicle-network
	@# Check if Neo4j should be started (NEO4J_ENABLED in any environment)
	@if grep -q "^NEO4J_ENABLED=true" environments/*.env 2>/dev/null; then \
		echo "🔗 Neo4j enabled in at least one environment - starting with Neo4j profile..."; \
		docker compose -f docker-compose.infra.yml --profile neo4j up -d; \
	else \
		docker compose -f docker-compose.infra.yml up -d; \
	fi
	@echo ""
	@echo "✅ Infrastructure services started!"
	@echo ""
	@echo "   📊 MongoDB:  mongodb://localhost:27017"
	@echo "   💾 Redis:    redis://localhost:6379"
	@echo "   🔍 Qdrant:   http://localhost:6034"
	@if docker ps --format '{{.Names}}' | grep -q '^neo4j$$'; then \
		echo "   🔗 Neo4j:    http://localhost:7474 (bolt: 7687)"; \
	fi
	@echo ""
	@echo "💡 These services are shared by all environments"
	@echo "   Each environment uses unique database names for isolation"
	@echo ""

infra-stop: ## Stop shared infrastructure
	@echo "🛑 Stopping shared infrastructure..."
	@echo "⚠️  This will affect ALL running environments!"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@docker compose -f docker-compose.infra.yml down
	@echo "✅ Infrastructure stopped"

infra-restart: ## Restart shared infrastructure
	@echo "🔄 Restarting shared infrastructure..."
	@docker compose -f docker-compose.infra.yml restart
	@echo "✅ Infrastructure restarted"

infra-logs: ## View infrastructure logs
	@echo "📋 Viewing infrastructure logs (press Ctrl+C to exit)..."
	@docker compose -f docker-compose.infra.yml logs -f

infra-status: ## Check infrastructure status
	@echo "📊 Infrastructure Status:"
	@echo ""
	@if docker ps --format '{{.Names}}' | grep -qE '(chronicle|friend-lite).*mongo'; then \
		echo "✅ MongoDB is running"; \
		docker ps --format '{{.Names}} {{.Ports}}' | grep mongo | awk '{print "   " $$1}'; \
	else \
		echo "❌ MongoDB is not running"; \
	fi
	@echo ""
	@if docker ps --format '{{.Names}}' | grep -qE '(chronicle|friend-lite).*redis'; then \
		echo "✅ Redis is running"; \
		docker ps --format '{{.Names}} {{.Ports}}' | grep redis | awk '{print "   " $$1}'; \
	else \
		echo "❌ Redis is not running"; \
	fi
	@echo ""
	@if docker ps --format '{{.Names}}' | grep -qE '(chronicle|friend-lite).*qdrant'; then \
		echo "✅ Qdrant is running"; \
		docker ps --format '{{.Names}} {{.Ports}}' | grep qdrant | awk '{print "   " $$1}'; \
	else \
		echo "❌ Qdrant is not running"; \
	fi
	@echo ""
	@if docker ps --format '{{.Names}}' | grep -q '^chronicle-neo4j$$'; then \
		echo "✅ Neo4j is running"; \
		docker ps --format '{{.Names}} {{.Ports}}' | grep neo4j | awk '{print "   " $$1}'; \
	else \
		echo "ℹ️  Neo4j is not running (optional)"; \
	fi
	@echo ""
	@if ! docker ps --format '{{.Names}}' | grep -qE '(chronicle|friend-lite).*(mongo|redis|qdrant)'; then \
		echo "💡 Start infrastructure with: make infra-start"; \
	fi

infra-clean: ## Clean infrastructure data (DANGER: deletes all databases!)
	@echo "⚠️  WARNING: This will delete ALL data from ALL environments!"
	@echo "   This includes:"
	@echo "   • All MongoDB databases"
	@echo "   • All Redis data"
	@echo "   • All Qdrant collections"
	@echo "   • All Neo4j graph databases (if enabled)"
	@echo ""
	@read -p "Type 'DELETE ALL DATA' to confirm: " confirm && [ "$$confirm" = "DELETE ALL DATA" ] || exit 1
	@docker compose -f docker-compose.infra.yml --profile neo4j down -v
	@echo "✅ Infrastructure data deleted"

# ========================================
# CADDY REVERSE PROXY (Shared Service)
# ========================================

caddy-start: ## Start shared Caddy reverse proxy (serves all environments)
	@echo "🚀 Starting Caddy reverse proxy..."
	@echo ""
	@# Check if Caddyfile exists
	@if [ ! -f "caddy/Caddyfile" ]; then \
		echo "⚠️  Caddyfile not found. Generating..."; \
		./scripts/generate-caddyfile.sh; \
		echo ""; \
	fi
	@# Start Caddy
	@docker compose -f compose/caddy.yml up -d
	@echo ""
	@echo "✅ Caddy reverse proxy started!"
	@echo ""
	@# Show access URLs
	@if [ -f "config-docker.env" ]; then \
		source config-docker.env; \
		if [ -n "$$TAILSCALE_HOSTNAME" ]; then \
			echo "🌐 Access your environments at:"; \
			echo "   https://$$TAILSCALE_HOSTNAME/"; \
			echo ""; \
			echo "   Individual environments:"; \
			for env in $$(ls -1 environments/*.env 2>/dev/null | sed 's|environments/||;s|.env$$||'); do \
				echo "     • $$env: https://$$TAILSCALE_HOSTNAME/$$env/"; \
			done; \
			echo ""; \
		fi; \
	fi

caddy-stop: ## Stop shared Caddy reverse proxy
	@echo "🛑 Stopping Caddy reverse proxy..."
	@docker compose -f compose/caddy.yml down
	@echo "✅ Caddy stopped"

caddy-restart: ## Restart shared Caddy reverse proxy
	@echo "🔄 Restarting Caddy reverse proxy..."
	@docker compose -f compose/caddy.yml restart
	@echo "✅ Caddy restarted"

caddy-logs: ## View Caddy logs
	@echo "📋 Viewing Caddy logs (press Ctrl+C to exit)..."
	@docker compose -f compose/caddy.yml logs -f

caddy-status: ## Check if Caddy is running
	@echo "📊 Caddy Status:"
	@echo ""
	@if docker ps --format '{{.Names}}' | grep -qE '^(chronicle|friend-lite)-caddy'; then \
		echo "✅ Caddy is running"; \
		docker ps --format '{{.Names}} {{.Ports}}' | grep caddy | awk '{print "   " $$1}'; \
		echo ""; \
		if [ -f "config-docker.env" ]; then \
			source config-docker.env; \
			if [ -n "$$TAILSCALE_HOSTNAME" ]; then \
				echo "🌐 Access URL: https://$$TAILSCALE_HOSTNAME/"; \
			fi; \
		fi; \
	else \
		echo "❌ Caddy is not running"; \
		echo "   Start with: make caddy-start"; \
	fi
	@echo ""

caddy-regenerate: ## Regenerate Caddyfile from current environments
	@echo "🔧 Regenerating Caddyfile..."
	@./scripts/generate-caddyfile.sh
	@echo ""
	@echo "✅ Caddyfile regenerated"
	@echo ""
	@echo "🔄 Restart Caddy to apply changes:"
	@echo "   make caddy-restart"

