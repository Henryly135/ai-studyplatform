from types import SimpleNamespace

from app.api import module_content as module_content_api


def test_upload_material_issues_response_for_the_authenticated_actor(monkeypatch) -> None:
    """The upload response must use the same user-bound proxy issuer as catalog reads."""

    material = SimpleNamespace(material_id=3)
    observed: dict[str, object] = {}

    class FakeMaterialService:
        def __init__(self, session) -> None:
            observed["service_session"] = session

        def upload_material(self, **kwargs):
            observed["upload_user"] = kwargs["current_user"]
            return material

    class FakeCatalog:
        def __init__(self, session) -> None:
            observed["catalog_session"] = session

        def to_material_response(self, received_material, *, current_user):
            observed["response_user"] = current_user
            assert received_material is material
            return {"resourceUrl": "proxy://material", "downloadUrl": "proxy://material?download=1"}

    monkeypatch.setattr(module_content_api, "ModuleMaterialService", FakeMaterialService)
    monkeypatch.setattr(module_content_api, "CourseCatalogService", FakeCatalog)

    subject = {"id": 7, "identity": "Educator"}
    result = module_content_api.upload_module_material(
        course_uuid="course-public-id",
        module_uuid="module-public-id",
        title="Notes",
        material_type="pdf",
        sort_order=1,
        file=SimpleNamespace(),
        current_user=subject,
        session=SimpleNamespace(),
    )

    assert result["resourceUrl"] == "proxy://material"
    assert observed["upload_user"] is subject
    assert observed["response_user"] is subject


def test_complete_multipart_material_issues_response_for_the_authenticated_actor(monkeypatch) -> None:
    material = SimpleNamespace(material_id=3)
    observed: dict[str, object] = {}

    class FakeMaterialService:
        def __init__(self, _session) -> None:
            pass

        def complete_multipart_upload(self, **kwargs):
            observed["complete_user"] = kwargs["current_user"]
            observed["parts"] = kwargs["completed_parts"]
            return material

    class FakeCatalog:
        def __init__(self, _session) -> None:
            pass

        def to_material_response(self, received_material, *, current_user):
            observed["response_user"] = current_user
            assert received_material is material
            return {"resourceUrl": "proxy://material"}

    monkeypatch.setattr(module_content_api, "ModuleMaterialService", FakeMaterialService)
    monkeypatch.setattr(module_content_api, "CourseCatalogService", FakeCatalog)

    subject = {"id": 7, "identity": "Educator"}
    payload = SimpleNamespace(parts=[SimpleNamespace(partNumber=1, etag="etag-1")])
    result = module_content_api.complete_multipart_module_material_upload(
        course_uuid="course-public-id",
        module_uuid="module-public-id",
        upload_session_uuid="upload-public-id",
        payload=payload,
        current_user=subject,
        session=SimpleNamespace(),
    )

    assert result["resourceUrl"] == "proxy://material"
    assert observed["complete_user"] is subject
    assert observed["response_user"] is subject
    assert observed["parts"] == [(1, "etag-1")]
