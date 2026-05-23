# ------------------------------
# 開発時用
# ------------------------------

# 追跡ファイルツリーを表示
.PHONY: tree
tree:
	git ls-files | tree --fromfile

# docker ps
.PHONY: docker-ps
docker-ps:
	docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"

# ファイルの所有者を変更
.PHONY: chown
chown:
	sudo chown -R $(shell whoami):$(shell whoami) .

# OpenAPIの最新化
.PHONY: openapi-update
openapi-update:
	${MAKE} -C orchestrator generate-openapi
	${MAKE} -C orchestrator reflect-openapi
	${MAKE} -C worker reflect-openapi
