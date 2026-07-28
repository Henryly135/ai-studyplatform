from pydantic import BaseModel, ConfigDict, Field


class AIModelCapabilities(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    chat: bool
    json_generation: bool = Field(alias="json")
    embedding: bool
    ragAnswer: bool
    ragIndexing: bool


class AIModelCatalogItem(BaseModel):
    modelId: str
    provider: str
    providerLabel: str
    modelName: str
    displayName: str
    available: bool
    unavailableReason: str | None = None
    backendSupported: bool
    displayOnly: bool
    configured: bool
    capabilities: AIModelCapabilities
    embeddingDimension: int | None = None
    pairedEmbeddingModelId: str | None = None
    pairedEmbeddingModelName: str | None = None
    ragReady: bool | None = None
    indexCoverage: float | None = Field(default=None, ge=0, le=1)
    indexStatus: str | None = None
    isDefaultChat: bool
    isDefaultEmbedding: bool
    isUserSelected: bool


class AIModelCatalogResponse(BaseModel):
    defaultChatModelId: str | None = None
    defaultEmbeddingModelId: str | None = None
    userSelectedChatModelId: str | None = None
    items: list[AIModelCatalogItem]


class AdminAIProviderCredentialItem(BaseModel):
    provider: str
    providerLabel: str
    backendSupported: bool
    configured: bool
    enabled: bool
    apiKeyHint: str | None = None
    baseUrl: str | None = None
    healthStatus: str
    lastCheckedAt: str | None = None
    lastError: str | None = None


class AdminAIProvidersResponse(BaseModel):
    providers: list[AdminAIProviderCredentialItem]
    defaultChatModelId: str | None = None
    defaultEmbeddingModelId: str | None = None


class AdminAIProviderCredentialRequest(BaseModel):
    apiKey: str = Field(..., min_length=1, max_length=5000)
    baseUrl: str | None = Field(default=None, max_length=500)
    enabled: bool = True


class AdminAIProviderCredentialResponse(BaseModel):
    provider: str
    configured: bool
    enabled: bool
    apiKeyHint: str | None = None
    baseUrl: str | None = None
    healthStatus: str


class AdminAIProviderHealthCheckResponse(BaseModel):
    provider: str
    status: str
    message: str


class AdminAIDefaultsRequest(BaseModel):
    defaultChatModelId: str | None = None
    defaultEmbeddingModelId: str | None = None


class AdminAIDefaultsResponse(BaseModel):
    defaultChatModelId: str | None = None
    defaultEmbeddingModelId: str | None = None
