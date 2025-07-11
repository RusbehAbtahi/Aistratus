TOOLS   := 04_scripts/no_priv/tools
ZIP     := $(TOOLS)/zip
STAT    := $(TOOLS)/stat
TERRAFORM := $(TOOLS)/terraform

.PHONY: lambda-package
lambda-package:
	(cd 01_src && $(ZIP) -r ../router.zip tinyllama/router -x '*.pyc' '__pycache__/*')
	@BYTES=$$($(STAT) --printf=%s router.zip 2>/dev/null || wc -c < router.zip); \
	[ $$BYTES -le 5242880 ] || { echo "router.zip too large"; exit 1; }

.PHONY: tf-apply
tf-apply: lambda-package
	cd terraform/10_global_backend && \
	$(TERRAFORM) init -backend-config=../../backend.auto.tfvars && \
	$(TERRAFORM) apply -auto-approve

.PHONY: lambda-rollback
lambda-rollback:
	@[[ -z "$(VERSION)" ]] && { echo "Usage: make lambda-rollback VERSION=n"; exit 1; }
	TLFIF_ENV ?= dev
	bash 04_scripts/no_priv/rollback_router.sh $(VERSION)