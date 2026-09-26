from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_linked_catparts_extract_native_properties_before_document_handle_closes() -> None:
    engine_source = (
        REPOSITORY_ROOT
        / "caa_new"
        / "CadCapture.edu"
        / "CadCapture.m"
        / "src"
        / "engine"
        / "ModelCaptureEngine.cpp"
    ).read_text(encoding="utf-8")

    capture_call = (
        "part_enumerator.CaptureDefinition(linked_handle, ids, definition, package, "
        "capture_error, true)"
    )
    extraction_call = (
        "property_extractors.ExtractNativeFactsForDocument("
        "ids, broker, package, reference.referenced_document_id)"
    )

    assert capture_call in engine_source
    assert extraction_call in engine_source
    assert engine_source.index(capture_call) < engine_source.index(extraction_call)
    assert engine_source.index(extraction_call) < engine_source.index(
        "definitions_by_document[reference.referenced_document_id] = definition"
    )


def test_linked_catpart_bindings_are_discarded_before_document_handle_closes() -> None:
    engine_source = (
        REPOSITORY_ROOT
        / "caa_new"
        / "CadCapture.edu"
        / "CadCapture.m"
        / "src"
        / "engine"
        / "ModelCaptureEngine.cpp"
    ).read_text(encoding="utf-8")

    assert "const size_t binding_count_before = package.native_object_bindings.size();" in engine_source
    assert "package.native_object_bindings.resize(binding_count_before);" in engine_source
