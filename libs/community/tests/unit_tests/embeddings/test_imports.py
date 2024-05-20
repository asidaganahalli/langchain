from langchain_community.embeddings import __all__, _module_lookup

EXPECTED_ALL = [
    "OpenAIEmbeddings",
    "AnyscaleEmbeddings",
    "AzureOpenAIEmbeddings",
    "BaichuanTextEmbeddings",
    "ClarifaiEmbeddings",
    "CohereEmbeddings",
    "DatabricksEmbeddings",
    "ElasticsearchEmbeddings",
    "FastEmbedEmbeddings",
    "HuggingFaceEmbeddings",
    "HuggingFaceInferenceAPIEmbeddings",
    "InfinityEmbeddings",
    "InfinityEmbeddingsLocal",
    "GradientEmbeddings",
    "JinaEmbeddings",
    "LaserEmbeddings",
    "LlamaCppEmbeddings",
    "LlamafileEmbeddings",
    "LLMRailsEmbeddings",
    "HuggingFaceHubEmbeddings",
    "MlflowAIGatewayEmbeddings",
    "MlflowEmbeddings",
    "MlflowCohereEmbeddings",
    "ModelScopeEmbeddings",
    "TensorflowHubEmbeddings",
    "SagemakerEndpointEmbeddings",
    "HuggingFaceInstructEmbeddings",
    "MosaicMLInstructorEmbeddings",
    "SelfHostedEmbeddings",
    "SelfHostedHuggingFaceEmbeddings",
    "SelfHostedHuggingFaceInstructEmbeddings",
    "FakeEmbeddings",
    "DeterministicFakeEmbedding",
    "AlephAlphaAsymmetricSemanticEmbedding",
    "AlephAlphaSymmetricSemanticEmbedding",
    "SentenceTransformerEmbeddings",
    "GooglePalmEmbeddings",
    "MiniMaxEmbeddings",
    "VertexAIEmbeddings",
    "BedrockEmbeddings",
    "DeepInfraEmbeddings",
    "EdenAiEmbeddings",
    "DashScopeEmbeddings",
    "EmbaasEmbeddings",
    "OctoAIEmbeddings",
    "SpacyEmbeddings",
    "NLPCloudEmbeddings",
    "GPT4AllEmbeddings",
    "GigaChatEmbeddings",
    "XinferenceEmbeddings",
    "LocalAIEmbeddings",
    "AwaEmbeddings",
    "HuggingFaceBgeEmbeddings",
    "ErnieEmbeddings",
    "JavelinAIGatewayEmbeddings",
    "OllamaEmbeddings",
    "OracleEmbeddings",
    "QianfanEmbeddingsEndpoint",
    "JohnSnowLabsEmbeddings",
    "VoyageEmbeddings",
    "BookendEmbeddings",
    "VolcanoEmbeddings",
    "OCIGenAIEmbeddings",
    "QuantizedBiEncoderEmbeddings",
    "NeMoEmbeddings",
    "SparkLLMTextEmbeddings",
    "SambaStudioEmbeddings",
    "TitanTakeoffEmbed",
    "QuantizedBgeEmbeddings",
    "PremAIEmbeddings",
    "YandexGPTEmbeddings",
    "OpenVINOEmbeddings",
    "OpenVINOBgeEmbeddings",
    "SolarEmbeddings",
]


def test_all_imports() -> None:
    assert set(__all__) == set(EXPECTED_ALL)
    assert set(__all__) == set(_module_lookup.keys())
