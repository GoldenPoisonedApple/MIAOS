# ファイルの所有者を変更
.PHONY: chown
chown:
	sudo chown -R $(shell whoami):$(shell whoami) .

# OpenAPIの整合性確保
.PHONY: openapi
openapi:
	${MAKE} -C orchestrator frontcmd CMD="make openapi"
	${MAKE} -C worker cmd CMD="make openapi"

