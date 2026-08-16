from __future__ import annotations

import tempfile
from pathlib import Path

from google import genai
from google.genai import types as genai_types
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.providers.credentials import ProviderCredentialService, redact_secret_text
from app.services.providers.model_service import AIModelCatalogService
from app.services.providers.types import ProviderConfigurationError, ProviderInvocationError, ProviderQuotaError
from platform_common.errors import invalid_request_error


class MaterialMediaAnalysisService:
    """Turn bounded image/audio/video assets into text that can enter the RAG index."""

    def __init__(self, session: Session | None = None) -> None:
        self.session = session

    def analyze(
        self,
        *,
        title: str,
        content_type: str,
        filename: str,
        payload: bytes,
    ) -> str:
        if not settings.ai_material_media_analysis_enabled:
            return self._fallback_metadata(title=title, content_type=content_type, filename=filename)
        if self.session is None:
            raise invalid_request_error("A database session is required for media analysis")

        catalog = AIModelCatalogService(self.session)
        catalog.ensure_seeded()
        try:
            resolved = catalog.resolve_chat_model(user_id=None, requested_model_id=None)
            credentials = ProviderCredentialService(self.session).get_credentials_for_provider(
                resolved.provider.provider_key
            )
        except ProviderConfigurationError as exc:
            raise invalid_request_error("媒体 AI 分析需要已配置并通过健康检查的 Gemini 模型。") from exc

        if resolved.provider.provider_key != "gemini":
            raise invalid_request_error("当前媒体 AI 分析需要 Gemini 多模态模型。")

        suffix = Path(filename or "material").suffix[:16]
        temporary_file = tempfile.NamedTemporaryFile(prefix="material-ai-", suffix=suffix, delete=False)
        temporary_path = Path(temporary_file.name)
        temporary_file.write(payload)
        temporary_file.flush()
        temporary_file.close()
        remote_file = None
        try:
            client = genai.Client(api_key=credentials.api_key)
            remote_file = client.files.upload(
                file=str(temporary_path),
                config=genai_types.UploadFileConfig(mime_type=content_type),
            )
            file_uri = getattr(remote_file, "uri", None)
            if not file_uri:
                raise ProviderInvocationError(
                    "Gemini did not return a media file URI.",
                    provider_error_type="invalid_provider_response",
                )
            part = genai_types.Part.from_uri(
                file_uri=file_uri,
                mime_type=getattr(remote_file, "mime_type", None) or content_type,
            )
            response = client.models.generate_content(
                model=resolved.model.model_name,
                contents=[self._prompt(title=title, content_type=content_type), part],
                config=genai_types.GenerateContentConfig(
                    max_output_tokens=settings.ai_material_media_analysis_max_output_tokens,
                    temperature=0.1,
                ),
            )
            text = (getattr(response, "text", None) or "").strip()
            if not text:
                raise ProviderInvocationError(
                    "Gemini returned an empty media analysis.",
                    provider_error_type="invalid_provider_response",
                )
            return text
        except (ProviderConfigurationError, ProviderQuotaError, ProviderInvocationError):
            raise
        except Exception as exc:
            raise invalid_request_error(
                f"媒体 AI 分析失败：{redact_secret_text(exc)}"
            ) from exc
        finally:
            if remote_file is not None:
                remote_name = getattr(remote_file, "name", None)
                if remote_name:
                    try:
                        client.files.delete(name=remote_name)
                    except Exception:
                        pass
            temporary_path.unlink(missing_ok=True)

    def _prompt(self, *, title: str, content_type: str) -> str:
        media_kind = "图片" if content_type.startswith("image/") else "音频" if content_type.startswith("audio/") else "视频"
        return (
            "你是课程资料分析器。请根据提供的"
            f"{media_kind}生成一段适合课程问答检索的中文资料摘要。资料标题：{title}。"
            "保留可确认的文字、概念、步骤、数据、人物、时间点和结论；图片要识别可见文字、图表和公式，"
            "音频/视频要概括讲解内容并列出关键术语，必要时给出简短时间点。不要编造无法确认的内容，"
            "不要输出 JSON、不要讨论你的分析过程。"
        )

    def _fallback_metadata(self, *, title: str, content_type: str, filename: str) -> str:
        return (
            f"资料标题：{title}\n资料文件：{filename}\n资料类型：{content_type}\n"
            "该资料已通过上传校验，但当前未启用媒体 AI 分析。"
        )
