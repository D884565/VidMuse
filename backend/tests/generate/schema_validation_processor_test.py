from backend.v1.app.pipeline.processors.schema_validation_processor import SchemaValidationProcessor


def test_for_product_allows_overrides_without_duplicate_kwargs():
    processor = SchemaValidationProcessor.for_product(
        valid_key="valid_product",
        invalid_key="invalid_product",
        summary_key="product_validation_summary",
        id_field="SKU_ID",
    )

    assert processor.data_key == "product_data"
    assert processor.valid_key == "valid_product"
    assert processor.invalid_key == "invalid_product"
    assert processor.summary_key == "product_validation_summary"
    assert processor.id_field == "SKU_ID"
