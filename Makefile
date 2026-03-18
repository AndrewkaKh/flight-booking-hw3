.PHONY: proto

PROTO_DIR=proto
GENERATED_DIR=shared/generated

proto:
	poetry run python -m grpc_tools.protoc \
		-I $(PROTO_DIR) \
		--python_out=$(GENERATED_DIR) \
		--grpc_python_out=$(GENERATED_DIR) \
		$(PROTO_DIR)/flight/v1/flight_service.proto